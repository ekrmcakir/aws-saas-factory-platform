"""
Unit Tests for Dynamic STS Token Broker
"""

import json
import unittest
from unittest.mock import MagicMock
from services.token_broker.broker import SaaSTokenBroker


def test_session_policy_generation():
    broker = SaaSTokenBroker(
        base_role_arn="arn:aws:iam::123456789012:role/SaaSBaseRole",
        dynamodb_table_arn="arn:aws:dynamodb:us-east-1:123456789012:table/SaaSTable",
        s3_bucket_arn="arn:aws:s3:::saas-storage"
    )

    policy_str = broker.generate_scoped_session_policy(
        tenant_id="tenant-finans-101",
        tier="PRO"
    )
    policy = json.loads(policy_str)

    # Validate DynamoDB LeadingKeys
    ddb_stmt = [s for s in policy["Statement"] if s["Sid"] == "DynamoDBLeadingKeysIsolation"][0]
    assert ddb_stmt["Condition"]["ForAllValues:StringEquals"]["dynamodb:LeadingKeys"] == ["tenant-finans-101"]

    # Validate S3 Prefix
    s3_stmt = [s for s in policy["Statement"] if s["Sid"] == "S3TenantPrefixIsolation"][0]
    assert s3_stmt["Resource"] == ["arn:aws:s3:::saas-storage/tenant-finans-101/*"]


def test_session_policy_enterprise_kms():
    broker = SaaSTokenBroker(
        base_role_arn="arn:aws:iam::123456789012:role/SaaSBaseRole",
        dynamodb_table_arn="arn:aws:dynamodb:us-east-1:123456789012:table/SaaSTable",
        s3_bucket_arn="arn:aws:s3:::saas-storage"
    )

    kms_arn = "arn:aws:kms:us-east-1:123456789012:key/cmk-tenant-999"
    policy_str = broker.generate_scoped_session_policy(
        tenant_id="tenant-enterprise-999",
        tier="ENTERPRISE",
        kms_key_arn=kms_arn
    )
    policy = json.loads(policy_str)

    kms_stmt = [s for s in policy["Statement"] if s["Sid"] == "DedicatedTenantKMSKey"][0]
    assert kms_stmt["Resource"] == [kms_arn]


def test_vend_credentials():
    mock_sts = MagicMock()
    mock_sts.assume_role.return_value = {
        "Credentials": {
            "AccessKeyId": "ASIA_MOCK_KEY",
            "SecretAccessKey": "MOCK_SECRET",
            "SessionToken": "MOCK_TOKEN",
            "Expiration": MagicMock(isoformat=lambda: "2026-10-27T18:00:00Z")
        }
    }

    broker = SaaSTokenBroker(
        base_role_arn="arn:aws:iam::123456789012:role/SaaSBaseRole",
        dynamodb_table_arn="arn:aws:dynamodb:us-east-1:123456789012:table/SaaSTable",
        s3_bucket_arn="arn:aws:s3:::saas-storage",
        sts_client=mock_sts
    )

    creds = broker.vend_tenant_credentials("tenant-acme", "PRO", "user-01")
    assert creds["access_key_id"] == "ASIA_MOCK_KEY"
    assert creds["tenant_id"] == "tenant-acme"
    assert creds["tier"] == "PRO"
    assert mock_sts.assume_role.called
