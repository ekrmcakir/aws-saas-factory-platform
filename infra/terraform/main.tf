# ---------------------------------------------------------------------------------------------------------------------
# ENTERPRISE SAAS FACTORY PLATFORM - ROOT TERRAFORM CONFIGURATION
# ---------------------------------------------------------------------------------------------------------------------

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "AWS-SaaS-Factory-Platform"
      ManagedBy   = "Terraform"
      Repository  = "https://github.com/ekrmcakir/aws-saas-factory-platform"
      Environment = var.environment
    }
  }
}

# Module 1: Cognito Multi-Tenant Authentication & Custom Claims
module "auth" {
  source      = "./modules/auth"
  environment = var.environment
}

# Module 2: Data Isolation Layer (DynamoDB LeadingKeys & S3 Tenant Prefixes & STS Base Role)
module "isolation" {
  source      = "./modules/isolation"
  environment = var.environment
}

# Module 3: Multi-Tenant API Gateway & Tiered Usage Plans (Noisy Neighbor Guard)
module "api" {
  source                = "./modules/api"
  environment           = var.environment
  authorizer_lambda_arn = "arn:aws:lambda:${var.aws_region}:123456789012:function:saas-lambda-authorizer"
}

# Module 4: Tenant Onboarding Saga (Step Functions & EventBridge)
module "onboarding" {
  source      = "./modules/onboarding"
  environment = var.environment
}

# Module 5: SaaS FinOps & Unit Economics Telemetry Engine
module "metering" {
  source      = "./modules/metering"
  environment = var.environment
}
