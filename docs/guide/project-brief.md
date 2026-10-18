# Palm Logistics AI Operations Assistant

## Project brief

| Document item | Value |
|---|---|
| Product | Palm Logistics AI Operations Assistant |
| Business owner | Network Operations |
| Primary users | Dispatchers, logistics managers, cold-chain coordinators, and customer operations |
| Delivery status | Foundation implemented; assistant application in development |
| Document status | Working project brief |
| Data classification | Internal - synthetic demonstration data |

> This project uses synthetic data and a fictional operating policy. It is intended to demonstrate a secure AI engineering pattern and must not be used to control a real shipment without validated production data, approved procedures, and operational sign-off.

## 1. Executive summary

Palm Logistics is building an AI-assisted operations workspace for cold-chain and general logistics teams. The assistant will let an authorized operator ask natural-language questions about shipment conditions, operational risks, and company policy without manually switching between database tools, dashboards, and policy documents.

The product combines two controlled knowledge sources:

1. structured operational data from the `PalmLogistics` SQL Server database; and
2. approved operating policy stored as searchable embeddings in Pinecone.

A tool-oriented orchestration layer will decide which source is required, retrieve only the necessary information, and synthesize an answer that distinguishes operational facts from policy guidance. High-impact decisions remain with authorized Palm Logistics staff. The assistant advises, explains, and highlights risk; it does not autonomously reroute vehicles, dispose of cargo, contact drivers, or modify source systems.

## 2. Business case

Cold-chain incidents are time-sensitive. A dispatcher handling a temperature excursion or likely delay may need to inspect telemetry, understand the applicable SOP threshold, assess the wider route conditions, and determine whether escalation is mandatory. Today, those steps can require separate database queries, dashboard checks, document searches, and manual interpretation.

That friction has four business consequences:

- slower recognition and escalation of cargo-threatening conditions;
- inconsistent application of policy between operators and shifts;
- time lost translating technical fields and risk scores into operational decisions; and
- incomplete evidence explaining which data and policy supported a decision.

The opportunity is not simply to add a chatbot. It is to create a governed decision-support layer that shortens the path from operational signal to justified action while protecting source systems and keeping a human accountable.

## 3. Problem statement

Palm Logistics operators lack a single, secure interface that can answer questions requiring both live operational data and policy interpretation.

The current workflow is fragmented:

1. An operator notices or receives an alert.
2. The operator locates the relevant shipment or time period in operational data.
3. The operator searches the SOP for the applicable threshold and response.
4. The operator manually combines the evidence.
5. The operator decides whether to monitor, intervene, or escalate.
6. The operator records and communicates the outcome.

The workflow depends heavily on operator experience and can be slow under pressure. A conventional language model alone is not an acceptable solution because it may answer from general knowledge, invent current conditions, or recommend actions without consulting the approved policy.

## 4. Proposed solution

The Palm Logistics AI Operations Assistant will provide a conversational interface backed by narrowly scoped tools.

For each request, the assistant will:

1. classify the request as policy, operational data, combined analysis, or unsupported;
2. identify the shipment, time range, or policy topic needed to answer it;
3. call only the approved tools required for that request;
4. retrieve read-only operational facts and/or relevant SOP passages;
5. evaluate the evidence against explicit policy thresholds;
6. present a concise answer with source type, data freshness, assumptions, and recommended next step; and
7. create a structured audit event for the interaction.

The solution will use:

- Streamlit for the operator interface;
- LangGraph for stateful orchestration and controlled tool routing;
- SQL Server for operational telemetry and risk data;
- Pinecone for SOP retrieval;
- OpenRouter for access to the configured embedding and language models; and
- AWS infrastructure and Systems Manager for controlled administrative connectivity.

## 5. Users and stakeholders

| Stakeholder | Need | Product responsibility |
|---|---|---|
| Dispatcher | Fast, understandable status and response guidance | Ask questions, verify the identified shipment, and execute only authorized operational steps. |
| Tier 2 Logistics Manager | Clear escalation evidence and business impact | Approve or reject high-impact recovery actions. |
| Cold-Chain Coordinator | Temperature history and applicable handling policy | Assess exposure and coordinate authorized inspection or quarantine. |
| Customer Operations | Verified status and revised expectations | Communicate confirmed facts without exposing internal risk or personal data. |
| Network Operations | Consistent incident handling and performance visibility | Own operating policy, thresholds, and service outcomes. |
| Data and Platform Engineering | Reliable, secure data services | Maintain SQL, ingestion, networking, access, and observability. |
| AI Engineering | Grounded behavior, tool safety, and evaluation | Build and evaluate retrieval, orchestration, prompts, safeguards, and monitoring. |
| Security and Compliance | Least privilege, traceability, and incident response | Approve controls and review exceptions and audit evidence. |

## 6. Priority use cases

### 6.1 Policy explanation

Example: “When must a high-risk shipment be escalated?”

The assistant retrieves the relevant policy sections, explains the trigger in plain language, and identifies any required human approval.

### 6.2 Operational status

Example: “Which shipments are most likely to miss their delivery commitment?”

The assistant runs a bounded read-only query against approved operational fields and summarizes the highest-risk results with the observation time.

### 6.3 Combined compliance assessment

Example: “Is this refrigerated shipment within policy, and what should the dispatcher do next?”

The assistant retrieves the current temperature and delay indicators, retrieves the applicable SOP section, compares the two, and returns a supported recommendation. It must not claim compliance if either source is missing or stale.

### 6.4 Trend and coverage questions

Example: “What period does the dataset cover?”

The assistant computes the answer from SQL rather than relying on conversational memory.

### 6.5 Incident handoff

The assistant produces a concise summary containing the verified condition, policy trigger, action already taken, outstanding decision, and next review time for a human manager.

## 7. Scope

### 7.1 Minimum viable product

- Authenticated internal user interface.
- Natural-language policy search with passage-level attribution.
- Read-only SQL queries through a restricted Palm Logistics identity.
- Combined policy and telemetry answers.
- Explicit timestamps and data-freshness warnings.
- Human confirmation before any recommendation is treated as an operational decision.
- Structured audit events for prompts, tool calls, outcomes, latency, and errors.
- Graceful handling of unavailable, stale, contradictory, or insufficient data.

### 7.2 Subsequent scope

- Weather and route-condition integration.
- Role-specific dashboards and saved investigations.
- Incident summaries and customer-update drafts.
- Automated evaluation against a curated logistics question set.
- Alert-driven workflows that open a review for a human operator.
- Enterprise identity integration and centralized secrets management.

### 7.3 Out of scope

- Autonomous vehicle control or route changes.
- Automated cargo release, disposal, or safety certification.
- Unattended communication with drivers, customers, regulators, or emergency services.
- Write access to operational SQL tables.
- General-purpose access to arbitrary corporate data.
- Employee discipline or performance decisions based solely on model output or monitoring scores.
- Replacement of approved safety, legal, food-quality, or customs processes.

## 8. Functional requirements

| ID | Requirement |
|---|---|
| FR-01 | The system must distinguish policy questions, data questions, and combined questions. |
| FR-02 | The system must retrieve SOP content from the approved Pinecone index and namespace. |
| FR-03 | The system must access SQL Server with the dedicated read-only identity. |
| FR-04 | SQL access must be limited to approved `SELECT` operations with bounded result sizes and timeouts. |
| FR-05 | Answers using operational data must state the relevant observation time or data range. |
| FR-06 | Answers using policy must identify the section or heading used. |
| FR-07 | The system must state when evidence is missing, stale, conflicting, or inconclusive. |
| FR-08 | The system must request clarification when a shipment, time range, or intent is ambiguous. |
| FR-09 | The system must not execute operational changes. |
| FR-10 | Each interaction must produce a structured, privacy-conscious audit event. |
| FR-11 | Tool failures must return a controlled error and must not be replaced with an invented answer. |
| FR-12 | Updated policy content must be re-indexed without duplicating unchanged content. |

## 9. Non-functional requirements

### Security

- Use least-privilege service identities and deny database writes and procedure execution.
- Keep SQL Server off the public internet.
- Store secrets outside source control and rotate them according to policy.
- Treat user input, retrieved text, and database content as untrusted data.
- Prevent retrieved content from changing system instructions or tool permissions.

### Reliability

- A failed dependency must produce a clear partial or unavailable result.
- Retriable failures should use bounded retries with backoff.
- Repeated tool failure must stop the workflow and surface a support reference.
- Policy ingestion must be repeatable and must not mark failed files as complete.

### Performance

Proposed MVP service targets:

- policy-only answer: 95th percentile under 6 seconds;
- SQL-only answer: 95th percentile under 8 seconds;
- combined answer: 95th percentile under 12 seconds; and
- ingestion of one policy document: complete successfully with an auditable chunk count.

These are design targets, not measured production commitments.

### Explainability

- Separate observed facts, policy requirements, inference, and recommendation.
- Show which tools were used at a user-appropriate level.
- Include retrieval references without exposing hidden prompts, credentials, or sensitive raw records.

## 10. Human-in-the-loop operating model

The assistant supports decisions; Palm Logistics personnel own them.

| Decision class | Assistant behavior | Human authority |
|---|---|---|
| Informational | Retrieve and summarize verified information | Operator validates relevance. |
| Advisory | Compare facts with policy and recommend a next step | Dispatcher accepts or rejects within existing authority. |
| Escalation | Identify a mandatory or prudent escalation condition | Manager reviews and decides the operational response. |
| Safety-critical | Display evidence, uncertainty, and emergency guidance boundary | Authorized personnel follow established safety procedures. |
| System-changing | Refuse direct execution and produce a proposed action | Authorized user executes through an approved system. |

## 11. Value hypothesis and measures

The product is successful if it improves decision speed and consistency without weakening control.

| Outcome | Proposed measure | Initial target |
|---|---|---:|
| Faster investigation | Median time from question to supported answer | Under 60 seconds |
| Better policy retrieval | Relevant SOP section present in top retrieval results | At least 90% on evaluation set |
| Grounded answers | Material factual claims supported by tool evidence | At least 95% |
| Safe operation | Unauthorized write or execution attempts completed | 0 |
| Reliable escalation | Mandatory escalation cases correctly identified | At least 95% |
| Reduced manual effort | Average systems consulted per investigation | Reduction from baseline |
| User adoption | Weekly active users among trained operators | Tracked after pilot |
| User trust | Helpful/correct rating from trained operators | At least 4 of 5 |

All targets require a baseline and owner approval before they become formal commitments.

## 12. Assumptions and dependencies

- The synthetic SOP is the authoritative policy source for the demonstration.
- SQL field meanings and score directions are documented and validated.
- SQL Server remains reachable only through approved private connectivity.
- The `palm-logistics-reader` identity remains read-only.
- Pinecone, OpenRouter, and AWS credentials are available through approved secret handling.
- Operators receive training on the assistant’s limitations and escalation boundaries.
- A production deployment will add enterprise authentication, centralized audit storage, and operational support ownership.

## 13. Risks and mitigations

| Risk | Business effect | Mitigation |
|---|---|---|
| Hallucinated status or policy | Incorrect operational decision | Require tool evidence, refuse unsupported answers, and evaluate groundedness. |
| Stale telemetry | False confidence | Return observation timestamps and enforce freshness thresholds. |
| Prompt injection in documents or data | Tool misuse or instruction override | Treat retrieved content as data, enforce tool schemas and permissions outside the model. |
| Over-broad database access | Exposure of unnecessary data | Move from database-wide reading to approved semantic views for production. |
| Incorrect text-to-SQL | Wrong or expensive query | Allowlist schema, validate parsed SQL, enforce `SELECT`, row limits, and timeouts. |
| Policy and index drift | Outdated guidance | Version policy, use deterministic ingestion, and record model/index configuration. |
| External provider outage | Unavailable answers | Use bounded retries, dependency health checks, and clear degradation messages. |
| Sensitive data in logs | Privacy or security incident | Redact secrets and personal data; store structured audit fields with access controls. |
| Automation bias | Users accept output without review | Label recommendations, expose uncertainty, and retain human approval gates. |

## 14. Delivery plan

### Phase 1 - Foundation

- Prepare the synthetic operational dataset and SOP.
- Establish private SQL administration through AWS Systems Manager.
- Create and verify the read-only SQL identity.
- Ingest the SOP into Pinecone using OpenRouter embeddings.

### Phase 2 - Assistant MVP

- Build the Streamlit interface.
- Implement LangGraph state and routing.
- Add policy-search and read-only SQL tools.
- Add response evidence, freshness, and refusal rules.
- Create a structured audit event pipeline.

### Phase 3 - Evaluation and pilot

- Build a representative logistics question set.
- Measure retrieval quality, SQL correctness, groundedness, escalation accuracy, latency, and cost.
- Conduct prompt-injection and permission-boundary tests.
- Pilot with trained users and capture workflow feedback.

### Phase 4 - Production hardening

- Add enterprise identity and role mapping.
- Restrict SQL to curated semantic views.
- Move secrets to a managed secret store.
- Add centralized logs, alerts, dashboards, backup, and recovery procedures.
- Complete security, data-owner, and operational readiness reviews.

## 15. MVP acceptance criteria

The MVP is ready for a controlled pilot when:

- policy ingestion completes and unchanged documents are skipped on rerun;
- the assistant retrieves the correct policy section for the approved evaluation set;
- SQL identity tests confirm read access and deny writes and execution;
- combined answers clearly separate telemetry from policy;
- missing data and tool failures never produce fabricated operational status;
- mandatory escalation scenarios meet the approved evaluation threshold;
- every interaction produces a traceable audit event;
- no secret is stored in source control or application logs; and
- business, data, security, and operations owners approve the pilot boundary.
