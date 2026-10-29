"""
Core Multi-Tenant SaaS Microservice
====================================
Demonstrates the secure execution path:
1. Receives authorized request with Tenant Context (tenant_id, tier, user_id).
2. Obtains dynamically scoped credentials from SaaSTokenBroker.
3. Accesses DynamoDB & S3 strictly within the tenant's bounded perimeter.
4. Emits real-time CloudWatch EMF telemetry for FinOps cost accounting.
5. Includes a breach validation route to demonstrate IAM LeadingKeys blocking cross-tenant theft.
"""

import time
import json
import logging
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError

from services.token_broker.broker import SaaSTokenBroker
from metering.finops.telemetry import SaaSTelemetryEmitter

logger = logging.getLogger("SaaSTenantAPI")
logger.setLevel(logging.INFO)


class TenantAPIService:
    def __init__(
        self,
        token_broker: SaaSTokenBroker,
        table_name: str,
        bucket_name: str,
        emitter: Optional[SaaSTelemetryEmitter] = None
    ):
        self.token_broker = token_broker
        self.table_name = table_name
        self.bucket_name = bucket_name
        self.emitter = emitter or SaaSTelemetryEmitter()

    def get_scoped_boto3_session(self, tenant_id: str, tier: str, user_id: str) -> boto3.Session:
        """Obtains scoped session from Token Broker."""
        creds = self.token_broker.vend_tenant_credentials(
            tenant_id=tenant_id,
            tier=tier,
            user_id=user_id
        )
        return boto3.Session(
            aws_access_key_id=creds["access_key_id"],
            aws_secret_access_key=creds["secret_access_key"],
            aws_session_token=creds["session_token"]
        )

    def save_tenant_order(
        self,
        tenant_id: str,
        tier: str,
        user_id: str,
        order_id: str,
        amount: float,
        items: list
    ) -> Dict[str, Any]:
        """
        Saves a business order using the scoped credentials.
        The DynamoDB item has PartitionKey: tenant_id, SortKey: order_id.
        """
        start_time = time.time()
        scoped_session = self.get_scoped_boto3_session(tenant_id, tier, user_id)
        dynamodb = scoped_session.resource("dynamodb")
        table = dynamodb.Table(self.table_name)

        item = {
            "tenant_id": tenant_id,
            "item_id": f"ORDER#{order_id}",
            "amount": str(amount),
            "items": items,
            "created_by": user_id,
            "timestamp": int(time.time())
        }

        table.put_item(Item=item)
        duration_ms = (time.time() - start_time) * 1000

        # Emit FinOps Telemetry
        self.emitter.emit_transaction_telemetry(
            tenant_id=tenant_id,
            tier=tier,
            route="/orders/create",
            status_code=201,
            duration_ms=duration_ms,
            rcu_consumed=0.0,
            wcu_consumed=1.0
        )

        return {"status": "SUCCESS", "order_id": order_id, "tenant_id": tenant_id}

    def get_tenant_order(
        self,
        tenant_id: str,
        tier: str,
        user_id: str,
        order_id: str
    ) -> Optional[Dict[str, Any]]:
        """Reads a tenant's order using scoped credentials."""
        start_time = time.time()
        scoped_session = self.get_scoped_boto3_session(tenant_id, tier, user_id)
        dynamodb = scoped_session.resource("dynamodb")
        table = dynamodb.Table(self.table_name)

        response = table.get_item(
            Key={
                "tenant_id": tenant_id,
                "item_id": f"ORDER#{order_id}"
            }
        )
        duration_ms = (time.time() - start_time) * 1000

        self.emitter.emit_transaction_telemetry(
            tenant_id=tenant_id,
            tier=tier,
            route="/orders/get",
            status_code=200 if "Item" in response else 404,
            duration_ms=duration_ms,
            rcu_consumed=1.0,
            wcu_consumed=0.0
        )

        return response.get("Item")

    def simulate_cross_tenant_breach_attempt(
        self,
        attacker_tenant_id: str,
        attacker_tier: str,
        attacker_user_id: str,
        victim_tenant_id: str,
        victim_order_id: str
    ) -> Dict[str, Any]:
        """
        SECURITY TEST:
        An attacker tenant attempts to read another tenant's order.
        Even if the attacker crafts an exploit with victim_tenant_id,
        the scoped credentials should trigger an IAM AccessDeniedException!
        """
        scoped_session = self.get_scoped_boto3_session(attacker_tenant_id, attacker_tier, attacker_user_id)
        dynamodb = scoped_session.resource("dynamodb")
        table = dynamodb.Table(self.table_name)

        logger.warning(
            f"BREACH ATTEMPT: Attacker={attacker_tenant_id} trying to read Victim={victim_tenant_id}"
        )

        try:
            # Illegal cross-tenant partition read
            table.get_item(
                Key={
                    "tenant_id": victim_tenant_id,
                    "item_id": f"ORDER#{victim_order_id}"
                }
            )
            return {
                "blocked": False,
                "message": "CRITICAL SECURITY FLAW: Cross-tenant access succeeded!"
            }
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code in ("AccessDeniedException", "AccessDenied"):
                logger.info("SECURITY VERIFIED: IAM LeadingKeys blocked cross-tenant read!")
                return {
                    "blocked": True,
                    "error_code": error_code,
                    "message": "AccessDenied: Dynamic IAM Session Policy successfully prevented cross-tenant data leak."
                }
            raise
