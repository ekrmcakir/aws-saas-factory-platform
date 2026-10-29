# Architecture Blueprint: Enterprise Multi-Tenant SaaS Platform

## 1. Executive Summary

This reference architecture implements the **AWS SaaS Factory** paradigm for mission-critical multi-tenant applications. It establishes enterprise-grade tenant isolation, tier-aware quality of service (Noisy Neighbor Guard), automated onboarding lifecycle management (Silo vs. Pool), and granular FinOps unit economics (Cost-per-Tenant telemetry).

---

## 2. Architecture Overview & Core Pillars

```
                                      ┌────────────────────────────────────────────────────────┐
                                      │              AWS SaaS Control Plane                    │
                                      │                                                        │
[ Tenant User ] ────── JWT Token ────▶│  [ API Gateway (Usage Plans: Free, Pro, Enterprise) ]  │
                                      │                        │                               │
                                      │           [ Lambda Custom Authorizer ]                 │
                                      │           - Token Bucket Rate Limiter                  │
                                      │           - Tenant Claim Extraction                    │
                                      └────────────────────────┼───────────────────────────────┘
                                                               │ Context: {tenant_id, tier}
                                                               ▼
                                      ┌────────────────────────────────────────────────────────┐
                                      │               AWS SaaS Data Plane                      │
                                      │                                                        │
                                      │             [ SaaS Tenant API / Microservice ]         │
                                      │                        │                               │
                                      │            [ Dynamic STS Token Broker ]                │
                                      │            - Generates Runtime Session Policy          │
                                      │            - Injects dynamodb:LeadingKeys Condition    │
                                      │            - Injects s3:prefix Condition               │
                                      │                        │ Scoped AWS Session Credentials│
                                      │         ┌──────────────┴──────────────┐                │
                                      │         ▼                             ▼                │
                                      │  [ DynamoDB ]                      [ S3 ]              │
                                      │  LeadingKeys: [tenant_id]   s3://bucket/{tenant_id}/*  │
                                      └────────────────────────────────────────────────────────┘
                                                               │
                                                               ▼ CloudWatch EMF Telemetry
                                      ┌────────────────────────────────────────────────────────┐
                                      │               SaaS FinOps Engine                       │
                                      │  - CloudWatch EMF -> Kinesis -> S3 Data Lake           │
                                      │  - Athena SQL Unit Economics Query                     │
                                      │  - Gross Margin per Tenant Breakdown                   │
                                      └────────────────────────────────────────────────────────┘
```

---

## 3. Deep Dive: Architectural Mechanisms

### Pillar 1: Attribute-Based Access Control (ABAC) & Dynamic STS Session Policies
* **The Vulnerability**: Hardcoding tenant filtering logic (`WHERE tenant_id = 'acme'`) in application code creates severe data leakage risks if developers miss a query.
* **The Solution**: The application assumes a baseline data access role via `sts:AssumeRole` while dynamically passing an inline **IAM Session Policy** during runtime:
  ```json
  {
    "Version": "2012-10-17",
    "Statement": [
      {
        "Sid": "DynamoDBLeadingKeysIsolation",
        "Effect": "Allow",
        "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query"],
        "Resource": "arn:aws:dynamodb:*:*:table/MultiTenantDataStore",
        "Condition": {
          "ForAllValues:StringEquals": {
            "dynamodb:LeadingKeys": ["${aws:PrincipalTag/TenantId}"]
          }
        }
      }
    ]
  }
  ```
* **Security Guarantee**: Even with an active SQL injection or faulty code querying another partition, AWS IAM enforces cryptographic boundary rejection (`AccessDeniedException`).

---

### Pillar 2: Tiered API Gateway & Noisy Neighbor Guard
* **The Vulnerability**: A misconfigured script or bad actor in a low-cost tier saturates shared compute and database capacity, degrading performance for paying enterprise customers.
* **The Solution**: Multi-layered token bucket rate limiting calibrated by tier:
  * **Free**: 10 req/s, Burst: 20 tokens, Daily quota: 1,000.
  * **Pro**: 100 req/s, Burst: 250 tokens, Daily quota: 100,000.
  * **Enterprise**: 1,000 req/s, Burst: 2,500 tokens, Daily quota: 10,000,000.
* Evaluated at the API Gateway Lambda Authorizer before reaching downstream compute, shedding unwanted traffic with `HTTP 429 Too Many Requests`.

---

### Pillar 3: Tenant Onboarding Saga (Silo vs. Pool Matrix)
* **Pooled Model (Free / Pro)**: Tenants share compute and database instances, achieving maximum cost efficiency through logical partition separation.
* **Silo Model (Enterprise / Regulated)**: Highly regulated clients (HIPAA, SOC2, PCI-DSS) receive dedicated AWS KMS Customer Managed Keys, dedicated S3 buckets, and dedicated DynamoDB tables.
* **Saga Orchestration**: AWS Step Functions state machine coordinates tenant validation, resource provisioning, API key configuration, and metadata registration with compensating rollback actions.

---

### Pillar 4: SaaS FinOps & Unit Economics Telemetry
* **Cost Allocation**: Every request emits CloudWatch Embedded Metric Format (EMF) logs capturing `ExecutionDurationMs`, `DynamoDB_RCU`, `DynamoDB_WCU`, and `S3BytesTransferred` tagged by `TenantId`.
* **Profitability Analytics**: Computes precise infrastructure cost per tenant:
  $$\text{Tenant Cost} = \text{Lambda Cost} + \text{DynamoDB Cost} + \text{S3 Transfer Cost} + \text{API Gateway Cost}$$
* Calculates Net Margin and Gross Margin %, flagging unprofitable or abusive accounts.

---

## 4. Alignment with AWS Well-Architected SaaS Lens

| SaaS Lens Pillar | Architectural Implementation |
| :--- | :--- |
| **Security** | IAM ABAC, Dynamic STS Session Policies, DynamoDB `LeadingKeys`, S3 prefix isolation, dedicated KMS CMK for Silo. |
| **Reliability** | Noisy Neighbor Guard, Token Bucket rate limiting, Multi-AZ DynamoDB with Point-in-Time Recovery. |
| **Performance Efficiency** | Tiered usage plans, in-memory token bucket fast path, dedicated reserved concurrency for enterprise. |
| **Cost Optimization** | Pooled multi-tenancy for high density, CloudWatch EMF telemetry for tenant-level unit economics. |
| **Operational Excellence** | Automated Step Functions onboarding saga, event-driven catalog synchronization, zero-downtime tier upgrades. |
