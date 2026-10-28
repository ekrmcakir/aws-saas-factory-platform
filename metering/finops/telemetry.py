"""
SaaS FinOps & Metering Engine - Telemetry Emitter
==================================================
Emits CloudWatch Embedded Metric Format (EMF) & Data Lake events for:
- API Request counts per tenant
- Compute duration (ms) & memory allocation
- DynamoDB RCU/WCU consumption
- S3 Storage & Transfer bytes

Enables precision Cost-Per-Tenant (Unit Economics) calculation.
"""

import json
import time
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("SaaSMeteringEmitter")
logger.setLevel(logging.INFO)


class SaaSTelemetryEmitter:
    """
    Structured telemetry emitter using CloudWatch Embedded Metric Format (EMF).
    Zero network overhead: outputs to stdout, CloudWatch asynchronously extracts metrics.
    """

    def __init__(self, service_name: str = "SaaSPlatform", namespace: str = "AWS/SaaS/TenantMetrics"):
        self.service_name = service_name
        self.namespace = namespace

    def emit_transaction_telemetry(
        self,
        tenant_id: str,
        tier: str,
        route: str,
        status_code: int,
        duration_ms: float,
        memory_mb: int = 256,
        rcu_consumed: float = 1.0,
        wcu_consumed: float = 0.0,
        s3_bytes: int = 0
    ) -> Dict[str, Any]:
        """
        Builds and logs an EMF payload conforming to AWS specifications.
        """
        timestamp = int(time.time() * 1000)

        emf_payload = {
            "_aws": {
                "Timestamp": timestamp,
                "CloudWatchMetrics": [
                    {
                        "Namespace": self.namespace,
                        "Dimensions": [["TenantId", "Tier"], ["TenantId"], ["Tier"]],
                        "Metrics": [
                            {"Name": "RequestCount", "Unit": "Count"},
                            {"Name": "ExecutionDurationMs", "Unit": "Milliseconds"},
                            {"Name": "DynamoDB_RCU", "Unit": "Count"},
                            {"Name": "DynamoDB_WCU", "Unit": "Count"},
                            {"Name": "S3BytesTransferred", "Unit": "Bytes"}
                        ]
                    }
                ]
            },
            # Metric Values
            "RequestCount": 1,
            "ExecutionDurationMs": round(duration_ms, 2),
            "DynamoDB_RCU": rcu_consumed,
            "DynamoDB_WCU": wcu_consumed,
            "S3BytesTransferred": s3_bytes,
            # Dimensions & Context
            "TenantId": tenant_id,
            "Tier": tier.upper(),
            "Route": route,
            "StatusCode": status_code,
            "MemoryAllocatedMB": memory_mb,
            "ServiceName": self.service_name
        }

        # Print JSON to stdout for CloudWatch agent extraction
        log_line = json.dumps(emf_payload)
        print(log_line)
        return emf_payload
