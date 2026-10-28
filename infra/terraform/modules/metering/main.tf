# ---------------------------------------------------------------------------------------------------------------------
# SAAS FINOPS & METERING ENGINE (CLOUDWATCH EMF & ATHENA UNIT ECONOMICS)
# ---------------------------------------------------------------------------------------------------------------------

variable "environment" {
  type = string
}

resource "aws_cloudwatch_log_group" "saas_emf_telemetry" {
  name              = "/aws/saas/tenant-metrics-${var.environment}"
  retention_in_days = 90

  tags = {
    Environment = var.environment
    Service     = "FinOpsTelemetry"
  }
}

resource "aws_s3_bucket" "finops_data_lake" {
  bucket        = "saas-finops-telemetry-${var.environment}-${formatdate("YYYYMMDD", timestamp())}"
  force_destroy = false

  tags = {
    Environment = var.environment
    Service     = "FinOpsDataLake"
  }
}

resource "aws_athena_workgroup" "finops_analytics" {
  name = "saas_finops_${var.environment}"

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true

    result_configuration {
      output_location = "s3://${aws_s3_bucket.finops_data_lake.bucket}/athena_query_results/"
    }
  }
}

# Pre-configured Athena Named Query to compute Monthly Gross Margin per Tenant
resource "aws_athena_named_query" "cost_per_tenant_query" {
  name      = "ComputeMonthlyCostPerTenant"
  workgroup = aws_athena_workgroup.finops_analytics.id
  database  = "saas_telemetry_${var.environment}"
  description = "Aggregates Lambda duration, DynamoDB RCU/WCU, and S3 bytes to compute cost per tenant"

  query = <<EOF
SELECT 
    tenant_id,
    tier,
    COUNT(*) as total_requests,
    SUM(execution_duration_ms) as total_execution_ms,
    ROUND(SUM(execution_duration_ms) / 1000.0 * (256.0 / 1024.0) * 0.0000166667, 4) as lambda_compute_cost,
    ROUND(SUM(dynamodb_rcu) * 0.00000025 + SUM(dynamodb_wcu) * 0.00000125, 4) as dynamodb_cost,
    ROUND(SUM(s3_bytes_transferred) / (1024.0 * 1024.0 * 1024.0) * 0.09, 4) as s3_data_transfer_cost,
    ROUND(
        (SUM(execution_duration_ms) / 1000.0 * (256.0 / 1024.0) * 0.0000166667) +
        (SUM(dynamodb_rcu) * 0.00000025 + SUM(dynamodb_wcu) * 0.00000125) +
        (COUNT(*) * 0.000001), 4
    ) as total_aws_cost_usd
FROM saas_request_telemetry
GROUP BY tenant_id, tier
ORDER BY total_aws_cost_usd DESC;
EOF
}

output "finops_log_group_name" {
  value = aws_cloudwatch_log_group.saas_emf_telemetry.name
}

output "finops_data_lake_bucket" {
  value = aws_s3_bucket.finops_data_lake.bucket
}

output "athena_workgroup_name" {
  value = aws_athena_workgroup.finops_analytics.name
}
