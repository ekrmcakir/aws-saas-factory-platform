# ---------------------------------------------------------------------------------------------------------------------
# TENANT ONBOARDING SAGA (STEP FUNCTIONS & EVENTBRIDGE)
# ---------------------------------------------------------------------------------------------------------------------

variable "environment" {
  type = string
}

resource "aws_cloudwatch_event_bus" "saas_event_bus" {
  name = "saas-events-${var.environment}"

  tags = {
    Environment = var.environment
    Service     = "SaaSControlPlane"
  }
}

# Step Functions Execution Role
resource "aws_iam_role" "step_functions_role" {
  name = "SaaSOnboardingStepFunctionsRole-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "states.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

# State Machine Definition for Silo vs Pool Onboarding
resource "aws_sfn_state_machine" "onboarding_saga" {
  name     = "SaaSTenantOnboardingSaga-${var.environment}"
  role_arn = aws_iam_role.step_functions_role.arn

  definition = <<EOF
{
  "Comment": "AWS SaaS Factory Tenant Onboarding Saga with Silo vs Pool Branching",
  "StartAt": "ValidateRegistration",
  "States": {
    "ValidateRegistration": {
      "Type": "Pass",
      "Next": "DetermineIsolationModel"
    },
    "DetermineIsolationModel": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.tier",
          "StringEquals": "ENTERPRISE",
          "Next": "ProvisionSiloResources"
        }
      ],
      "Default": "ProvisionPooledResources"
    },
    "ProvisionSiloResources": {
      "Type": "Pass",
      "Result": {
        "isolation_model": "SILO",
        "kms_key_provisioned": true,
        "dedicated_dynamodb_provisioned": true
      },
      "ResultPath": "$.silo_details",
      "Next": "ConfigureUsagePlan"
    },
    "ProvisionPooledResources": {
      "Type": "Pass",
      "Result": {
        "isolation_model": "POOLED",
        "shared_partition_allocated": true
      },
      "ResultPath": "$.pool_details",
      "Next": "ConfigureUsagePlan"
    },
    "ConfigureUsagePlan": {
      "Type": "Pass",
      "Next": "RegisterInCatalog"
    },
    "RegisterInCatalog": {
      "Type": "Pass",
      "Next": "SendWelcomeNotification"
    },
    "SendWelcomeNotification": {
      "Type": "Pass",
      "End": true
    }
  }
}
EOF

  tags = {
    Environment = var.environment
    Service     = "SaaSControlPlane"
  }
}

output "event_bus_name" {
  value = aws_cloudwatch_event_bus.saas_event_bus.name
}

output "state_machine_arn" {
  value = aws_sfn_state_machine.onboarding_saga.arn
}
