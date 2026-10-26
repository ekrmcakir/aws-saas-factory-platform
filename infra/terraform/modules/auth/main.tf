# ---------------------------------------------------------------------------------------------------------------------
# MULTI-TENANT AUTHENTICATION MODULE (AWS COGNITO USER POOL & CLAIMS)
# ---------------------------------------------------------------------------------------------------------------------

variable "environment" {
  type = string
}

resource "aws_cognito_user_pool" "saas_pool" {
  name = "saas-user-pool-${var.environment}"

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length    = 10
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
    require_uppercase = true
  }

  # Custom attributes to embed tenant identity into JWT ID/Access tokens
  schema {
    attribute_data_type      = "String"
    developer_only_attribute = false
    mutable                  = false
    name                     = "tenant_id"
    required                 = false
    string_attribute_constraints {
      min_length = "1"
      max_length = "64"
    }
  }

  schema {
    attribute_data_type      = "String"
    developer_only_attribute = false
    mutable                  = true
    name                     = "tier"
    required                 = false
    string_attribute_constraints {
      min_length = "1"
      max_length = "32"
    }
  }

  schema {
    attribute_data_type      = "String"
    developer_only_attribute = false
    mutable                  = true
    name                     = "role"
    required                 = false
    string_attribute_constraints {
      min_length = "1"
      max_length = "32"
    }
  }

  tags = {
    Environment = var.environment
    Service     = "SaaSAuth"
  }
}

resource "aws_cognito_user_pool_client" "saas_client" {
  name         = "saas-web-app-client-${var.environment}"
  user_pool_id = aws_cognito_user_pool.saas_pool.id

  generate_secret                      = false
  explicit_auth_flows                  = ["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
  prevent_user_existence_errors        = "ENABLED"
  id_token_validity                    = 60
  access_token_validity                = 60
  token_validity_units {
    id_token     = "minutes"
    access_token = "minutes"
  }
}

# Standard Tenant Role Groups
resource "aws_cognito_user_group" "system_admins" {
  name         = "SystemAdmins"
  user_pool_id = aws_cognito_user_pool.saas_pool.id
  description  = "Super-admins managing SaaS platform control plane"
  precedence   = 1
}

resource "aws_cognito_user_group" "tenant_admins" {
  name         = "TenantAdmins"
  user_pool_id = aws_cognito_user_pool.saas_pool.id
  description  = "Company admins managing their company account"
  precedence   = 10
}

resource "aws_cognito_user_group" "tenant_users" {
  name         = "TenantUsers"
  user_pool_id = aws_cognito_user_pool.saas_pool.id
  description  = "Standard team members"
  precedence   = 20
}

output "user_pool_id" {
  value = aws_cognito_user_pool.saas_pool.id
}

output "user_pool_arn" {
  value = aws_cognito_user_pool.saas_pool.arn
}

output "user_pool_client_id" {
  value = aws_cognito_user_pool_client.saas_client.id
}
