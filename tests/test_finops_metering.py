"""
Unit Tests for SaaS FinOps & Unit Economics Telemetry
"""

from metering.finops.telemetry import SaaSTelemetryEmitter
from metering.finops.analyzer import TenantCostAnalyzer


def test_telemetry_emf_payload():
    emitter = SaaSTelemetryEmitter()
    payload = emitter.emit_transaction_telemetry(
        tenant_id="tenant-finops-test",
        tier="PRO",
        route="/api/v1/orders",
        status_code=200,
        duration_ms=150.5,
        rcu_consumed=2.0,
        wcu_consumed=1.0,
        s3_bytes=1048576
    )

    assert payload["TenantId"] == "tenant-finops-test"
    assert payload["ExecutionDurationMs"] == 150.5
    assert payload["DynamoDB_RCU"] == 2.0
    assert payload["_aws"]["CloudWatchMetrics"][0]["Namespace"] == "AWS/SaaS/TenantMetrics"


def test_tenant_cost_and_profitability_analysis():
    records = [
        # 1. Profitable Pro Tenant ($99/mo revenue, low infra spend)
        {
            "tenant_id": "tenant-pro-light",
            "tier": "PRO",
            "requests": 50000,
            "total_duration_ms": 50000 * 80.0,
            "memory_mb": 256,
            "total_rcu": 50000,
            "total_wcu": 10000,
            "total_s3_bytes": 1073741824 # 1 GB
        },
        # 2. Unprofitable Free Tenant ($0/mo revenue, heavy usage)
        {
            "tenant_id": "tenant-free-heavy",
            "tier": "FREE",
            "requests": 80000,
            "total_duration_ms": 80000 * 250.0,
            "memory_mb": 512,
            "total_rcu": 80000,
            "total_wcu": 40000,
            "total_s3_bytes": 5368709120 # 5 GB
        }
    ]

    report = TenantCostAnalyzer.generate_profitability_report(records)

    pro_tenant = [t for t in report["tenants"] if t["tenant_id"] == "tenant-pro-light"][0]
    free_tenant = [t for t in report["tenants"] if t["tenant_id"] == "tenant-free-heavy"][0]

    # Pro tenant pays $99, costs < $5 -> Highly profitable!
    assert pro_tenant["is_profitable"] is True
    assert pro_tenant["gross_margin_pct"] > 80.0

    # Free tenant pays $0, incurs infra cost -> Loss maker!
    assert free_tenant["is_profitable"] is False
    assert report["unprofitable_tenants_count"] == 1
