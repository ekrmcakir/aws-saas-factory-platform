"""
Unit Tests for Noisy Neighbor Guard & Tiered Rate Limiting
"""

from services.authorizer.lambda_authorizer import TokenBucketRateLimiter, lambda_handler, _TOKEN_BUCKETS


def test_free_tier_burst_throttling():
    tenant_id = "test-free-noisy-tenant"
    tier = "FREE"

    # Reset any cached bucket state
    _TOKEN_BUCKETS.pop(tenant_id, None)

    # Free tier capacity is 20 burst tokens
    successful_requests = 0
    blocked_requests = 0

    # Rapid burst of 30 requests in sub-second
    for _ in range(30):
        allowed, remaining, capacity = TokenBucketRateLimiter.check_and_consume(tenant_id, tier)
        if allowed:
            successful_requests += 1
        else:
            blocked_requests += 1

    assert successful_requests == 20
    assert blocked_requests == 10


def test_enterprise_tier_capacity():
    tenant_id = "test-enterprise-mega-tenant"
    tier = "ENTERPRISE"
    _TOKEN_BUCKETS.pop(tenant_id, None)

    successful_requests = 0
    # Rapid burst of 200 requests (Enterprise capacity is 2500)
    for _ in range(200):
        allowed, remaining, _ = TokenBucketRateLimiter.check_and_consume(tenant_id, tier)
        if allowed:
            successful_requests += 1

    assert successful_requests == 200


def test_lambda_authorizer_allow():
    event = {
        "authorizationToken": "mock.acme-corp.PRO.user-42",
        "methodArn": "arn:aws:execute-api:us-east-1:123456789012:api-id/dev/GET/orders"
    }
    policy = lambda_handler(event, None)

    assert policy["policyDocument"]["Statement"][0]["Effect"] == "Allow"
    assert policy["context"]["tenant_id"] == "acme-corp"
    assert policy["context"]["tier"] == "PRO"
