"""
Dynamic STS Token Broker for AWS SaaS Factory
================================================
Implements Attribute-Based Access Control (ABAC) and Dynamic Session Policies.
Vendors short-lived (15-60 min) AWS credentials dynamically scoped to the calling tenant's identity.

Enforces:
1. DynamoDB LeadingKeys isolation: Tenant can only read/write items where Partition Key == tenant_id.
2. S3 Prefix isolation: Tenant can only access objects under s3://bucket/{tenant_id}/*
3. KMS Key isolation: Enterprise tenants get scoped access to their dedicated KMS CMK.
"""

import json
import logging
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger("SaaSTokenBroker")
logger.setLevel(logging.INFO)


class SaaSTokenBroker:
    def __init__(
        self,
        base_role_arn: str,
        dynamodb_table_arn: str,
        s3_bucket_arn: str,
        sts_client: Optional[Any] = None,
    ):
        self.base_role_arn = base_role_arn
        self.dynamodb_table_arn = dynamodb_table_arn
        self.s3_bucket_arn = s3_bucket_arn
        self.sts_client = sts_client or boto3.client("sts")

    def generate_scoped_session_policy(
        self,
        tenant_id: str,
        tier: str,
        kms_key_arn: Optional[str] = None,
    ) -> str:
        """
        Generates an IAM Session Policy dynamically at runtime.
        Session policies cannot grant permissions beyond the base role,
        they can only further intersect/restrict them.
        """
        statements = [
            # 1. DynamoDB Isolation via LeadingKeys
            {
                "Sid": "DynamoDBLeadingKeysIsolation",
                "Effect": "Allow",
                "Action": [
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                    "dynamodb:Query",
                    "dynamodb:BatchGetItem",
                    "dynamodb:BatchWriteItem"
                ],
                "Resource": [
                    self.dynamodb_table_arn,
                    f"{self.dynamodb_table_arn}/index/*"
                ],
                "Condition": {
                    "ForAllValues:StringEquals": {
                        "dynamodb:LeadingKeys": [tenant_id]
                    }
                }
            },
            # 2. S3 Object Prefix Isolation
            {
                "Sid": "S3TenantPrefixIsolation",
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket"
                ],
                "Resource": [
                    f"{self.s3_bucket_arn}/{tenant_id}/*"
                ]
            },
            {
                "Sid": "S3TenantPrefixListing",
                "Effect": "Allow",
                "Action": ["s3:ListBucket"],
                "Resource": [self.s3_bucket_arn],
                "Condition": {
                    "StringLike": {
                        "s3:prefix": [f"{tenant_id}/*", f"{tenant_id}"]
                    }
                }
            }
        ]

        # 3. Dedicated KMS CMK if Enterprise Silo Tier
        if kms_key_arn:
            statements.append({
                "Sid": "DedicatedTenantKMSKey",
                "Effect": "Allow",
                "Action": [
                    "kms:Decrypt",
                    "kms:GenerateDataKey",
                    "kms:DescribeKey"
                ],
                "Resource": [kms_key_arn]
            })

        policy_doc = {
            "Version": "2012-10-17",
            "Statement": statements
        }
        return json.dumps(policy_doc)

    def vend_tenant_credentials(
        self,
        tenant_id: str,
        tier: str,
        user_id: str,
        duration_seconds: int = 900,
        kms_key_arn: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Assumes the SaaS Data Access Role with an inline runtime session policy
        and session tags for ABAC.
        """
        session_policy = self.generate_scoped_session_policy(tenant_id, tier, kms_key_arn)
        session_name = f"tenant-{tenant_id}-{user_id}"[:64]

        logger.info(
            f"Vending scoped credentials for Tenant={tenant_id}, Tier={tier}, User={user_id}"
        )

        try:
            response = self.sts_client.assume_role(
                RoleArn=self.base_role_arn,
                RoleSessionName=session_name,
                Policy=session_policy,
                DurationSeconds=duration_seconds,
                Tags=[
                    {"Key": "TenantId", "Value": tenant_id},
                    {"Key": "TenantTier", "Value": tier},
                    {"Key": "UserId", "Value": user_id}
                ],
                TransitiveTagKeys=["TenantId", "TenantTier"]
            )

            credentials = response["Credentials"]
            return {
                "access_key_id": credentials["AccessKeyId"],
                "secret_access_key": credentials["SecretAccessKey"],
                "session_token": credentials["SessionToken"],
                "expiration": credentials["Expiration"].isoformat(),
                "tenant_id": tenant_id,
                "tier": tier
            }
        except ClientError as e:
            logger.error(f"Failed to assume role for tenant {tenant_id}: {str(e)}")
            raise
