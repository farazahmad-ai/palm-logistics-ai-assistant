# Palm Logistics AI Engineering Roadmap

Last updated: 2026-10-20

## Roadmap status

| Area | Current position |
|---|---|
| Product and architecture | Established |
| Data, knowledge, and access controls | Working foundation established |
| AI tools and orchestration | Working foundation established |
| User experience and audit trail | Working foundation established |
| Evaluation | Manual validation complete; automated evaluation pending |
| Delivery engineering | Automated GitHub-to-AWS deployment operational |
| Demonstration environment | Running on AWS with temporary public HTTP access |
| Secure demonstration | Planned |
| Production platform | Planned |

Checklist convention:

- `[x]` means implemented and verified.
- `[ ]` means planned or not yet verified. Future work remains unchecked until evidence confirms completion.

## Engineering principles

- Architecture, security boundaries, evidence contracts, and success criteria are defined before production expansion.
- Models may reason about evidence but cannot expand their own permissions.
- Operational facts, policy requirements, external context, inference, and recommendations remain distinguishable.
- Database and IAM permissions are enforcement boundaries; prompts are not security controls.
- Releases use reproducible dependencies, exact commits, automated validation, health checks, and rollback.
- Production promotion requires measurable quality, safety, reliability, security, and cost gates.
- High-impact operational decisions remain with authorized Palm Logistics personnel.

---

## Phase 1 — Product definition, architecture, and risk boundaries

### Product and operating model

- [x] Define the assistant as an evidence-grounded logistics operations product rather than a general-purpose chatbot.
- [x] Define priority workflows covering operational status, policy guidance, combined risk assessment, trend investigation, and incident handoff.
- [x] Identify the primary user groups and their decision responsibilities.
- [x] Preserve human approval for rerouting, cargo disposition, external communication, and other consequential actions.
- [x] Define clarification, refusal, and partial-answer behavior for unsupported or insufficiently evidenced requests.
- [x] Record business goals, scope, success measures, and non-functional requirements in `docs/project-brief.md`.

### Architecture and security design

- [x] Establish the logical application, orchestration, tool, data, model, and control-plane architecture.
- [x] Define the operational SQL path, policy retrieval path, LangGraph flow, request sequence, and tool contracts.
- [x] Define identity, authorization, secret handling, prompt-injection boundaries, failure behavior, observability, and audit requirements.
- [x] Document the current AWS deployment topology and target production topology in `docs/architecture.md`.
- [x] Define read-only operational behavior and narrowly scoped audit writes as core trust boundaries.
- [x] Define initial quality measures for groundedness, retrieval relevance, escalation accuracy, latency, safety, and user trust.
- [ ] Complete a formal threat model covering public ingress, model/tool abuse, data exfiltration, dependency compromise, privilege escalation, and denial of service.
- [ ] Approve measurable production service-level objectives and risk-acceptance criteria.

**Exit outcome:** product authority, system boundaries, architecture, and initial success criteria are explicit before production expansion.

---

## Phase 2 — Data, knowledge, and access foundations

### Operational data contract

- [x] Establish SQL Server as the operational system of record used by the assistant.
- [x] Verify required timestamps, coordinates, temperature, delay, route, cargo, and risk fields.
- [x] Define timestamp ordering rather than physical row position as the basis for “latest” records.
- [x] Configure the application to use the restricted `palm-logistics-reader` identity.
- [x] Deny general data modification and stored-procedure execution to the application identity.
- [x] Permit parameterized inserts only to `dbo.AgentAuditLog` while denying audit reads and changes to that identity.
- [x] Keep SQL Server inaccessible through a public database rule and permit application traffic through the private VPC path.
- [ ] Introduce approved semantic views containing only fields required by supported use cases.
- [ ] Replace broad schema knowledge with a versioned, machine-readable data contract.
- [ ] Define valid ranges, directionality, units, and business meaning for every operational score and measurement.
- [ ] Add automated checks for stale telemetry, invalid coordinates, impossible values, duplicates, and missing timestamps.
- [ ] Add query execution timeouts, workload limits, and database resource controls.

### Policy knowledge foundation

- [x] Establish the maintained Palm Logistics SOP as the authoritative policy source for retrieval.
- [x] Define operating roles, severity levels, response targets, escalation paths, and evidence requirements.
- [x] Define interpretation boundaries for cargo profiles, temperature limits, numeric scores, location, and time alignment.
- [x] Implement format-aware document parsing, heading-aware chunking, metadata retention, and deterministic chunk identifiers.
- [x] Configure OpenRouter embeddings and the Pinecone `policy` namespace with compatible dimensions.
- [x] Implement incremental synchronization using content hashes, changed-file replacement, and removed-file cleanup.
- [x] Return source and section attribution with retrieved passages and handle empty retrieval explicitly.
- [ ] Add policy owner, version, approval status, effective date, review date, and retirement status to retrieval metadata.
- [ ] Add an ingestion manifest covering source hash, chunk count, model, dimension, index, namespace, and ingestion time.
- [ ] Add controlled promotion and rollback for draft, approved, superseded, and retired policy versions.
- [ ] Define backup, export, and recovery procedures for the policy vector corpus.

**Exit outcome:** operational and policy evidence can be retrieved through controlled, attributable, and least-privilege paths.

---

## Phase 3 — AI tools, orchestration, and grounded response behavior

### Tool layer

- [x] Implement bounded SQL retrieval through `query_logistics_db`.
- [x] Restrict SQL tool input to a single read query and block data-changing, schema-changing, permission, execution, backup, restore, and database-switch operations.
- [x] Apply row limits and return column names with query results.
- [x] Implement attributed SOP retrieval through `search_compliance_sop`.
- [x] Implement time-stamped corridor weather retrieval through `fetch_corridor_conditions`.
- [x] Add controlled empty-result and dependency-error behavior for all three tools.
- [x] Reuse the embedding client safely across Streamlit reruns.
- [ ] Replace keyword-only SQL validation with parsed-query validation and an allowlisted schema/view surface.
- [ ] Define structured tool-error categories for unavailable, unauthorized, invalid, stale, and empty results.

### Agent orchestration

- [x] Implement a typed LangGraph state and bounded reasoning/tool execution loop.
- [x] Bind only the approved SQL, SOP, and weather tools to the model.
- [x] Configure deterministic model behavior, bounded output, request timeouts, and retries.
- [x] Keep behavioral instructions versioned separately in `src/prompts/system_prompt.txt`.
- [x] Require SQL for operational facts and retrieved SOP passages for policy claims.
- [x] Prevent unsupported locations, timestamps, thresholds, scores, citations, and tool results from being asserted as facts.
- [x] Separate shipment telemetry from current external weather and require time-aware comparisons.
- [x] Require facts, policy, assessment, recommendations, confidence basis, and evidence gaps to remain distinguishable.
- [x] Treat retrieved passages and tool output as untrusted evidence that cannot override system instructions.
- [ ] Introduce a formal evidence object shared by tools, orchestration, evaluation, rendering, and audit.
- [ ] Add maximum graph-step, repeated-tool-call, and cumulative tool-cost limits.
- [ ] Add contradiction detection between operational evidence, policy assumptions, and external context.
- [ ] Base confidence on source availability, freshness, agreement, and validation rather than model self-assessment.
- [ ] Add a persistent checkpoint store when durable or multi-instance conversations are required.

**Exit outcome:** the assistant routes questions to approved tools and composes answers from traceable evidence within explicit authority limits.

---

## Phase 4 — User experience, human control, and auditability

### Operations interface

- [x] Deliver the Streamlit operations console with conversational history and per-session thread identifiers.
- [x] Show investigation progress, model tool requests, tool results, and final responses as distinct interface events.
- [x] Support clearing a conversation and starting a new thread.
- [x] Surface controlled application errors without silently inventing results.
- [ ] Add guided filters for time range, risk class, vehicle, route, location, and cargo profile.
- [ ] Add role-specific operational views and saved investigations.
- [ ] Add evidence export and incident-handoff generation with an explicit human confirmation step.
- [ ] Add user feedback for correct, incomplete, incorrect, and unsafe responses.
- [ ] Display policy version, observation time, freshness, and evidence gaps consistently.

### Audit and accountability

- [x] Record prompts, tool requests, tool results, final responses, and failures with session and graph context.
- [x] Use parameterized writes to the append-only audit path.
- [x] Require a separately authorized identity to read audit records.
- [x] Avoid storing administrator credentials in application session state or source control.
- [ ] Replace large free-text audit content with structured event types and fields.
- [ ] Add automatic redaction for credentials, personal information, and unnecessary operational detail.
- [ ] Add model, prompt, policy, embedding, tool, and application version identifiers to each audited interaction.
- [ ] Create a dedicated audit-reader role and remove administrator credential entry from the public application.
- [ ] Define audit retention, archival, access review, deletion, and incident-review procedures.

**Exit outcome:** users can inspect evidence and retain decision authority while interactions remain traceable without expanding application privileges.

---

## Phase 5 — Evaluation, testing, and release-quality gates

### Verified foundation

- [x] Manually verify SQL schema discovery, recent-record ordering, required operational fields, SOP retrieval, and current weather retrieval.
- [x] Verify embedding configuration compatibility with the Pinecone index.
- [x] Verify tool selection and grounded responses for representative natural-language questions.
- [x] Correct unsupported geographic inference, score interpretation, missing-field claims, and incomplete operational answers found during testing.
- [x] Verify restricted audit writes and separately authorized audit reads.
- [x] Verify Streamlit startup, cached resources, deployment health, SQL, embeddings, and Pinecone connectivity.

### Automated evaluation program

- [ ] Build a version-controlled golden set spanning SQL-only, policy-only, weather-only, combined, ambiguous, stale-data, dependency-failure, and refusal cases.
- [ ] Add assertions for tool selection, SQL validity, evidence attribution, answer groundedness, required escalation, and refusal behavior.
- [ ] Measure retrieval precision, recall, ranking quality, and correct-section coverage.
- [ ] Add deterministic test doubles for SQL, Pinecone, OpenRouter, and Open-Meteo.
- [ ] Add adversarial tests for prompt injection, data exfiltration, unauthorized SQL, tool misuse, and denial-of-service patterns.
- [ ] Establish latency, token, cost, groundedness, safety, and escalation thresholds for release approval.
- [ ] Require regression evaluation before model, embedding, prompt, policy, chunking, or tool-contract changes are promoted.
- [ ] Add online quality monitoring and sampled human review after production launch.

**Exit outcome:** releases are promoted using repeatable evidence rather than manual confidence alone.

---

## Phase 6 — Software delivery and deployment engineering

### Reproducible application delivery

- [x] Manage dependencies through `pyproject.toml` and `uv.lock` with a pinned Python 3.12 runtime.
- [x] Keep secrets, local environment files, caches, and local-only material out of source control.
- [x] Add Python compilation, shell syntax, dependency synchronization, and deployment smoke checks.
- [x] Maintain the systemd unit, SSM deployment document, IAM policies, bootstrap payload, deployment runner, and recovery behavior as source-controlled infrastructure artifacts.
- [x] Remove one-off diagnostic and repair payloads after their operational purpose was complete.

### Continuous delivery

- [x] Establish the public GitHub repository and `main` delivery branch.
- [x] Configure GitHub Actions validation and exact-commit deployment.
- [x] Configure repository/environment-scoped GitHub OIDC without permanent AWS keys.
- [x] Restrict the GitHub deployment role to one SSM document and one application instance.
- [x] Deploy through AWS Systems Manager with no inbound SSH.
- [x] Restart through systemd and automatically verify application health plus SQL, embeddings, and Pinecone.
- [x] Roll back to the previous verified commit when deployment validation fails.
- [x] Complete the first green GitHub-to-SSM deployment.
- [ ] Add unit tests for configuration, SQL validation, chunking, ingestion state, audit events, and response formatting.
- [ ] Add formatting, linting, type checking, secret scanning, dependency vulnerability scanning, and software bill-of-materials generation.
- [ ] Configure branch protection, pull-request review, and required quality/security checks for `main`.
- [ ] Define dependency, prompt, model, and embedding upgrade procedures with rollback criteria.

**Exit outcome:** application releases are reproducible, identity-federated, observable, and recoverable.

---

## Phase 7 — AWS demonstration environment

### Implemented environment

- [x] Provision the application EC2 instance with encrypted storage and IMDSv2 enforcement.
- [x] Attach a restricted EC2 role for Systems Manager administration.
- [x] Keep inbound SSH closed.
- [x] Install the Python runtime, ODBC driver, application dependencies, protected runtime configuration, deployment runner, and systemd service.
- [x] Connect the application to SQL Server through its private VPC address.
- [x] Restrict database port `1433` to the application security group.
- [x] Verify application health and SQL, OpenRouter, and Pinecone dependencies from the deployed instance.
- [x] Expose the current demonstration temporarily over public HTTP port `8501` without requiring an SSM tunnel.
- [x] Record the deployed and target topologies in `docs/architecture.md`.

### Remaining demonstration acceptance checks

- [ ] Verify a representative SQL-backed telemetry question through the deployed UI.
- [ ] Verify a representative SOP-backed policy question through the deployed UI.
- [ ] Verify a representative weather-backed corridor question through the deployed UI.
- [ ] Verify the expected `dbo.AgentAuditLog` event sequence through an authorized audit identity.
- [ ] Independently confirm that SQL Server is not reachable publicly on port `1433`.

**Exit outcome:** the deployed demonstration is functionally accepted across every evidence path and its audit trail.

---

## Phase 8 — Secure single-instance demonstration

All work in this phase is planned and remains unchecked.

- [ ] Associate a stable Elastic IP with the application instance.
- [ ] Install and harden Nginx as the only internet-facing application endpoint.
- [ ] Return Streamlit to `127.0.0.1:8501` and remove public access to port `8501`.
- [ ] Permit only HTTP `80` for certificate validation and redirect, and HTTPS `443` for application traffic.
- [ ] Obtain a publicly trusted IP-address TLS certificate and verify unattended renewal.
- [ ] Add front-door authentication without placing plaintext credentials in Git or shell history.
- [ ] Protect or remove the administrator/audit interface from the public application.
- [ ] Configure request throttling, safe proxy headers, request-size limits, timeouts, and security headers.
- [ ] Add AWS Budgets and billing alerts for compute, storage, public IPv4, model, and vector usage.
- [ ] Add availability, CPU, memory, disk, service, certificate-renewal, and application-error monitoring.
- [ ] Run an external exposure review and close every unneeded inbound rule.
- [ ] Remove temporary public rule `sgr-0cfb02a8327b4e741` after the secure endpoint is verified.

**Exit outcome:** the single-instance demonstration has stable addressing, encrypted transport, authentication, bounded exposure, and basic operational monitoring.

---

## Phase 9 — Production platform, security, and resilience

All work in this phase is planned and remains unchecked.

### Network and runtime platform

- [ ] Register and govern a production domain and DNS zone.
- [ ] Create public load-balancer subnets and private application subnets across at least two Availability Zones.
- [ ] Deploy an Application Load Balancer with an ACM certificate and HTTPS-only listener.
- [ ] Allow application traffic only from the load-balancer security group.
- [ ] Remove public IPv4 addresses from application instances.
- [ ] Run multiple application instances with health-based routing and controlled autoscaling.
- [ ] Externalize checkpoint and session state for multi-instance operation.
- [ ] Provide controlled outbound access through approved egress infrastructure.

### Identity, secrets, and data protection

- [ ] Integrate enterprise authentication through Cognito or the approved identity provider.
- [ ] Enforce role-based authorization using verified identity claims.
- [ ] Add AWS WAF protections and application-level abuse controls.
- [ ] Move production credentials and API keys to AWS Secrets Manager or an approved equivalent.
- [ ] Configure trusted SQL Server TLS and require certificate validation.
- [ ] Rotate service credentials and document ownership and rotation intervals.
- [ ] Replace temporary provisioning access with least-privilege operational and break-glass roles.
- [ ] Detach `AdministratorAccess`, delete `PalmLogisticsProvisioner`, and remove its trust-policy artifact after provisioning is complete.

### Reliability and operations

- [ ] Centralize application, deployment, access, audit, and dependency logs.
- [ ] Define dashboards and alarms for availability, latency, errors, saturation, dependency health, quality, safety, and spend.
- [ ] Implement backup, restore, disaster-recovery, and recovery-testing procedures.
- [ ] Define deployment promotion, rollback, incident response, on-call ownership, and operational runbooks.
- [ ] Perform load, resilience, failover, security, and recovery testing before production launch.

**Exit outcome:** the service meets approved production requirements for identity, confidentiality, availability, recoverability, observability, and operational ownership.

---

## Phase 10 — Continuous AI governance and improvement

All work in this phase is planned and remains unchecked.

- [ ] Assign owners and review cycles for models, prompts, tools, policies, data contracts, evaluations, and infrastructure.
- [ ] Track model, prompt, policy, retrieval, tool, and application versions for every release and audited interaction.
- [ ] Monitor groundedness, retrieval quality, escalation accuracy, refusals, user feedback, latency, cost, and safety events.
- [ ] Establish controlled model and embedding change management with offline evaluation, staged rollout, and rollback.
- [ ] Establish policy publication governance with approval, promotion, expiry, conflict handling, and re-index verification.
- [ ] Review database permissions, IAM roles, secrets, dependencies, network exposure, and audit access on a defined schedule.
- [ ] Conduct incident reviews for incorrect, unsafe, unauthorized, or materially incomplete assistant behavior.
- [ ] Maintain a prioritized improvement backlog driven by evaluation results, operational telemetry, security findings, and user outcomes.

**Exit outcome:** quality, security, cost, policy, and model behavior remain governed throughout the system lifecycle.

---

## Immediate execution order

1. Complete the five remaining deployed-UI and database-exposure acceptance checks in Phase 7.
2. Execute Phase 8 to replace temporary public HTTP access with stable HTTPS and authentication.
3. Build the automated evaluation and test gates in Phase 5 before any production promotion.
4. Complete the CI quality and security gates in Phase 6.
5. Implement Phase 9 production infrastructure and security controls.
6. Retire temporary provisioning privileges after the final AWS setup task.
7. Operate Phase 10 as an ongoing governance program.
