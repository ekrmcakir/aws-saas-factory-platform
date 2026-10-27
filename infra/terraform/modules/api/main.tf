# ---------------------------------------------------------------------------------------------------------------------
# API GATEWAY & TIERED USAGE PLANS (NOISY NEIGHBOR GUARD)
# ---------------------------------------------------------------------------------------------------------------------

variable "environment" {
  type = string
}

variable "authorizer_lambda_arn" {
  type = string
}

resource "aws_api_gateway_rest_api" "saas_api" {
  name        = "saas-core-api-${var.environment}"
  description = "Enterprise SaaS Multi-Tenant Gateway with Noisy Neighbor Throttling"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

# 1. Custom Lambda Authorizer for Token Validation & Dynamic Context
resource "aws_api_gateway_authorizer" "jwt_authorizer" {
  name                   = "SaaSTenantAuthorizer"
  rest_api_id            = aws_api_gateway_rest_api.saas_api.id
  authorizer_uri         = var.authorizer_lambda_arn
  authorizer_result_ttl_in_seconds = 0 # 0 for real-time per-request token bucket evaluation
  identity_source        = "method.request.header.Authorization"
  type                   = "TOKEN"
}

# 2. Tiered Usage Plans for Noisy Neighbor Isolation
resource "aws_api_gateway_usage_plan" "free_tier_plan" {
  name        = "SaaS-UsagePlan-Free-${var.environment}"
  description = "Restricted usage plan for Free tier tenants"

  throttle_settings {
    rate_limit  = 10
    burst_limit = 20
  }

  quota_settings {
    limit  = 1000
    period = "DAY"
  }
}

resource "aws_api_gateway_usage_plan" "pro_tier_plan" {
  name        = "SaaS-UsagePlan-Pro-${var.environment}"
  description = "Standard usage plan for Pro tier tenants"

  throttle_settings {
    rate_limit  = 100
    burst_limit = 250
  }

  quota_settings {
    limit  = 100000
    period = "DAY"
  }
}

resource "aws_api_gateway_usage_plan" "enterprise_tier_plan" {
  name        = "SaaS-UsagePlan-Enterprise-${var.environment}"
  description = "High-performance usage plan for Enterprise tier tenants"

  throttle_settings {
    rate_limit  = 1000
    burst_limit = 2500
  }

  quota_settings {
    limit  = 10000000
    period = "DAY"
  }
}

output "api_id" {
  value = aws_api_gateway_rest_api.saas_api.id
}

output "free_usage_plan_id" {
  value = aws_api_gateway_usage_plan.free_tier_plan.id
}

output "pro_usage_plan_id" {
  value = aws_api_gateway_usage_plan.pro_tier_plan.id
}

output "enterprise_usage_plan_id" {
  value = aws_api_gateway_usage_plan.enterprise_tier_plan.id
}
