# ---------------------------------------------------------------------------------------------------------------------
# MULTI-TENANT DATA ISOLATION MODULE (DYNAMODB LEADINGKEYS & S3 PREFIXES)
# ---------------------------------------------------------------------------------------------------------------------

variable "environment" {
  type        = string
  description = "Environment name (e.g. dev, staging, prod)"
}

# 1. Central Tenant Catalog Table (Tracks metadata & isolation model for each tenant)
resource "aws_dynamodb_table" "tenant_catalog" {
  name         = "saas-tenant-catalog-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "tenant_id"

  attribute {
    name = "tenant_id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Environment = var.environment
    Service     = "SaaSControlPlane"
  }
}

# 2. Shared Multi-Tenant Data Store (Pooled Model)
# Partition Key = tenant_id, Sort Key = item_id
resource "aws_dynamodb_table" "multi_tenant_data" {
  name         = "saas-pooled-datastore-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "tenant_id"
  range_key    = "item_id"

  attribute {
    name = "tenant_id"
    type = "S"
  }

  attribute {
    name = "item_id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Environment    = var.environment
    IsolationModel = "POOLED"
    Service        = "SaaSDataPlane"
  }
}

# 3. Multi-Tenant S3 Bucket (Partitioned logically by tenant_id prefix)
resource "aws_s3_bucket" "multi_tenant_storage" {
  bucket        = "saas-pooled-storage-${var.environment}-${formatdate("YYYYMMDD", timestamp())}"
  force_destroy = false

  tags = {
    Environment    = var.environment
    IsolationModel = "POOLED"
  }
}

resource "aws_s3_bucket_public_access_block" "block_public" {
  bucket = aws_s3_bucket.multi_tenant_storage.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "sse" {
  bucket = aws_s3_bucket.multi_tenant_storage.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# 4. SaaS Base Tenant Data Access Role
# Used by STS AssumeRole to enforce runtime session policies with LeadingKeys
resource "aws_iam_role" "saas_data_access_role" {
  name = "SaaSTenantDataAccessRole-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
          AWS     = "arn:aws:iam::123456789012:root"
        }
        Action = ["sts:AssumeRole", "sts:TagSession"]
      }
    ]
  })

  tags = {
    Environment = var.environment
    Service     = "SaaSTokenBroker"
  }
}

# Base permissions for the role (runtime session policy will intersect and restrict this)
resource "aws_iam_policy" "saas_base_data_policy" {
  name        = "SaaSBaseDataPolicy-${var.environment}"
  description = "Base access policy for tenant operations. Dynamically restricted at runtime."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DynamoDBBaseAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:BatchGetItem",
          "dynamodb:BatchWriteItem"
        ]
        Resource = [
          aws_dynamodb_table.multi_tenant_data.arn,
          "${aws_dynamodb_table.multi_tenant_data.arn}/index/*"
        ]
      },
      {
        Sid    = "S3BaseAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.multi_tenant_storage.arn,
          "${aws_s3_bucket.multi_tenant_storage.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "attach_base_policy" {
  role       = aws_iam_role.saas_data_access_role.name
  policy_arn = aws_iam_policy.saas_base_data_policy.arn
}

output "tenant_catalog_table_name" {
  value = aws_dynamodb_table.tenant_catalog.name
}

output "multi_tenant_table_arn" {
  value = aws_dynamodb_table.multi_tenant_data.arn
}

output "multi_tenant_table_name" {
  value = aws_dynamodb_table.multi_tenant_data.name
}

output "multi_tenant_bucket_arn" {
  value = aws_s3_bucket.multi_tenant_storage.arn
}

output "multi_tenant_bucket_name" {
  value = aws_s3_bucket.multi_tenant_storage.id
}

output "saas_data_access_role_arn" {
  value = aws_iam_role.saas_data_access_role.arn
}
