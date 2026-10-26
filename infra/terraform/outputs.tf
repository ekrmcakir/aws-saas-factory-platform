output "cognito_user_pool_id" {
  value       = module.auth.user_pool_id
  description = "Cognito User Pool ID with tenant custom claims"
}

output "multi_tenant_table_name" {
  value       = module.isolation.multi_tenant_table_name
  description = "Shared DynamoDB table partitioned by tenant_id"
}

output "saas_data_access_role_arn" {
  value       = module.isolation.saas_data_access_role_arn
  description = "Base IAM role assumed dynamically via STS for scoped tenant operations"
}

output "api_gateway_id" {
  value       = module.api.api_id
  description = "REST API Gateway ID"
}

output "onboarding_state_machine_arn" {
  value       = module.onboarding.state_machine_arn
  description = "Step Functions State Machine ARN for tenant onboarding"
}

output "finops_data_lake_bucket" {
  value       = module.metering.finops_data_lake_bucket
  description = "S3 bucket storing SaaS tenant telemetry for unit economics"
}
