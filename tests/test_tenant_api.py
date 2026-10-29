"""
Unit Tests for Multi-Tenant Core Microservice (TenantAPIService)
"""

from unittest.mock import MagicMock
from botocore.exceptions import ClientError
from services.tenant_api.app import TenantAPIService
from services.token_broker.broker import SaaSTokenBroker


def test_tenant_api_save_and_get_order():
    mock_broker = MagicMock(spec=SaaSTokenBroker)
    mock_broker.vend_tenant_credentials.return_value = {
        "access_key_id": "ASIATEST",
        "secret_access_key": "MOCKSECRET",
        "session_token": "MOCKTOKEN",
        "expiration": "2026-10-29T20:00:00Z"
    }

    mock_emitter = MagicMock()

    service = TenantAPIService(
        token_broker=mock_broker,
        table_name="saas-pooled-datastore-dev",
        bucket_name="saas-pooled-storage-dev",
        emitter=mock_emitter
    )

    # Mock get_scoped_boto3_session
    mock_session = MagicMock()
    mock_dynamodb = MagicMock()
    mock_table = MagicMock()
    mock_session.resource.return_value = mock_dynamodb
    mock_dynamodb.Table.return_value = mock_table
    service.get_scoped_boto3_session = MagicMock(return_value=mock_session)

    # Test save_tenant_order
    save_result = service.save_tenant_order(
        tenant_id="t-acme-corp",
        tier="PRO",
        user_id="user-123",
        order_id="ORD-999",
        amount=149.99,
        items=["item1", "item2"]
    )
    assert save_result["status"] == "SUCCESS"
    assert save_result["order_id"] == "ORD-999"
    assert mock_table.put_item.called
    assert mock_emitter.emit_transaction_telemetry.called

    # Test get_tenant_order
    mock_table.get_item.return_value = {
        "Item": {
            "tenant_id": "t-acme-corp",
            "item_id": "ORDER#ORD-999",
            "amount": "149.99"
        }
    }
    order = service.get_tenant_order(
        tenant_id="t-acme-corp",
        tier="PRO",
        user_id="user-123",
        order_id="ORD-999"
    )
    assert order is not None
    assert order["amount"] == "149.99"


def test_cross_tenant_breach_blocked_by_iam():
    mock_broker = MagicMock(spec=SaaSTokenBroker)
    service = TenantAPIService(
        token_broker=mock_broker,
        table_name="saas-pooled-datastore-dev",
        bucket_name="saas-pooled-storage-dev"
    )

    mock_session = MagicMock()
    mock_dynamodb = MagicMock()
    mock_table = MagicMock()

    # Simulate AWS IAM throwing AccessDeniedException on leading key mismatch
    error_response = {
        "Error": {
            "Code": "AccessDeniedException",
            "Message": "User is not authorized to perform: dynamodb:GetItem with LeadingKey"
        }
    }
    mock_table.get_item.side_effect = ClientError(error_response, "GetItem")
    mock_session.resource.return_value = mock_dynamodb
    mock_dynamodb.Table.return_value = mock_table
    service.get_scoped_boto3_session = MagicMock(return_value=mock_session)

    result = service.simulate_cross_tenant_breach_attempt(
        attacker_tenant_id="t-attacker",
        attacker_tier="FREE",
        attacker_user_id="hacker-1",
        victim_tenant_id="t-victim",
        victim_order_id="CONFIDENTIAL-100"
    )

    assert result["blocked"] is True
    assert result["error_code"] == "AccessDeniedException"
    assert "Dynamic IAM Session Policy" in result["message"]
