"""
SaaS FinOps Unit Economics & Profitability Analyzer
===================================================
Calculates:
1. Exact AWS Infrastructure Cost per Tenant (Lambda + DynamoDB + S3 + API Gateway)
2. Revenue vs Cost (Gross Margin per Tenant)
3. Identification of unprofitable tenants ("Loss-Maker Tenants")
"""

from typing import Dict, Any, List


# AWS Pricing Constants (us-east-1 standard baseline)
PRICING = {
    "LAMBDA_GB_SECOND": 0.0000166667,       # per GB-sec
    "LAMBDA_REQUEST": 0.0000002,            # $0.20 per 1M requests
    "API_GATEWAY_REQUEST": 0.000001,        # $1.00 per 1M requests
    "DYNAMODB_READ_REQUEST_UNIT": 0.00000025, # $0.25 per 1M RRUs
    "DYNAMODB_WRITE_REQUEST_UNIT": 0.00000125, # $1.25 per 1M WRUs
    "S3_STORAGE_PER_GB_MONTH": 0.023,
    "S3_DATA_TRANSFER_PER_GB": 0.09
}

# Standard Subscription Plans Monthly Revenue (ARR / 12)
SUBSCRIPTION_PLANS = {
    "FREE": 0.0,
    "PRO": 99.0,          # $99 / month
    "ENTERPRISE": 999.0   # $999 / month
}


class TenantCostAnalyzer:
    """
    Analyzes aggregated usage records and computes financial unit economics per tenant.
    """

    @staticmethod
    def calculate_single_tenant_cost(
        requests: int,
        total_duration_ms: float,
        memory_mb: int,
        total_rcu: float,
        total_wcu: float,
        total_s3_bytes: int
    ) -> Dict[str, float]:
        """Calculates granular component costs for a single tenant."""
        # 1. Lambda Cost
        total_gb_seconds = (total_duration_ms / 1000.0) * (memory_mb / 1024.0)
        compute_cost = (total_gb_seconds * PRICING["LAMBDA_GB_SECOND"]) + (requests * PRICING["LAMBDA_REQUEST"])

        # 2. API Gateway Cost
        api_gw_cost = requests * PRICING["API_GATEWAY_REQUEST"]

        # 3. DynamoDB Cost
        db_cost = (total_rcu * PRICING["DYNAMODB_READ_REQUEST_UNIT"]) + (total_wcu * PRICING["DYNAMODB_WRITE_REQUEST_UNIT"])

        # 4. S3 Data Transfer Cost
        s3_gb = total_s3_bytes / (1024.0 ** 3)
        storage_transfer_cost = s3_gb * PRICING["S3_DATA_TRANSFER_PER_GB"]

        total_aws_cost = compute_cost + api_gw_cost + db_cost + storage_transfer_cost

        return {
            "compute_cost": round(compute_cost, 6),
            "api_gateway_cost": round(api_gw_cost, 6),
            "database_cost": round(db_cost, 6),
            "storage_cost": round(storage_transfer_cost, 6),
            "total_aws_cost": round(total_aws_cost, 4)
        }

    @classmethod
    def generate_profitability_report(cls, tenant_usage_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Takes raw usage batches and computes tenant profitability and gross margin.
        """
        summary = []
        for record in tenant_usage_records:
            tenant_id = record["tenant_id"]
            tier = record.get("tier", "FREE").upper()
            cost_breakdown = cls.calculate_single_tenant_cost(
                requests=record.get("requests", 0),
                total_duration_ms=record.get("total_duration_ms", 0.0),
                memory_mb=record.get("memory_mb", 256),
                total_rcu=record.get("total_rcu", 0.0),
                total_wcu=record.get("total_wcu", 0.0),
                total_s3_bytes=record.get("total_s3_bytes", 0)
            )

            monthly_revenue = SUBSCRIPTION_PLANS.get(tier, 0.0)
            total_cost = cost_breakdown["total_aws_cost"]
            net_margin_dollars = monthly_revenue - total_cost
            gross_margin_pct = (net_margin_dollars / monthly_revenue * 100) if monthly_revenue > 0 else -100.0

            is_profitable = net_margin_dollars >= 0 and monthly_revenue > 0

            summary.append({
                "tenant_id": tenant_id,
                "tier": tier,
                "requests": record.get("requests", 0),
                "monthly_revenue": monthly_revenue,
                "total_infra_cost": total_cost,
                "net_margin_dollars": round(net_margin_dollars, 2),
                "gross_margin_pct": round(gross_margin_pct, 1),
                "is_profitable": is_profitable,
                "breakdown": cost_breakdown
            })

        return {
            "tenants": summary,
            "total_revenue": sum(t["monthly_revenue"] for t in summary),
            "total_infra_spend": sum(t["total_infra_cost"] for t in summary),
            "unprofitable_tenants_count": sum(1 for t in summary if not t["is_profitable"])
        }
