"""
Unit Tests for Tenant Onboarding Saga (Silo vs Pool)
"""

from services.onboarding.saga_orchestrator import TenantOnboardingWorkflow


def test_onboard_pro_pooled_tenant():
    workflow = TenantOnboardingWorkflow(catalog_table_name="saas-tenant-catalog")
    payload = {
        "tenant_name": "CloudNova Inc",
        "admin_email": "admin@cloudnova.io",
        "tier": "PRO"
    }

    result = workflow.execute_saga(payload)

    assert result["status"] == "ONBOARDING_COMPLETED"
    assert result["isolation_model"] == "POOLED"
    assert "shared_dynamodb_partition" in result["resources"]
    assert "t-cloudnova-inc" in result["tenant_id"]


def test_onboard_enterprise_silo_tenant():
    workflow = TenantOnboardingWorkflow(catalog_table_name="saas-tenant-catalog")
    payload = {
        "tenant_name": "Apex Global Bank",
        "admin_email": "ciso@apexbank.com",
        "tier": "ENTERPRISE"
    }

    result = workflow.execute_saga(payload)

    assert result["status"] == "ONBOARDING_COMPLETED"
    assert result["isolation_model"] == "SILO"
    assert "kms_key_arn" in result["resources"]
    assert "dedicated_s3_bucket" in result["resources"]
    assert "dedicated_dynamodb_table" in result["resources"]
