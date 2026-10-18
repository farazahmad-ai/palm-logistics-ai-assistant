# Palm Logistics
## Standard Operating Procedure: Cold-Chain, Transit Risk, and Service Recovery

| Document control | Value |
|---|---|
| Document owner | Palm Logistics — Network Operations |
| Version | 2.5 |
| Status | Synthetic training and demonstration policy |
| Effective date | 18 October 2026 |
| Review cycle | Every 12 months, or after a severity-1 incident |
| Classification | Internal Operations Only |

> **Synthetic-use notice:** Palm Logistics and the operating scenarios in this document are fictional. This SOP is designed for analytics, retrieval, and workflow demonstrations. It must not be treated as regulatory, food-safety, employment, or emergency-response advice for a real shipment.

## 1. Purpose

This SOP defines how Palm Logistics monitors shipments, identifies operational anomalies, protects temperature-sensitive cargo, and restores service after a disruption. It turns signals from the Palm Logistics monitoring dataset into consistent decisions that can be reviewed and audited.

The objectives are to:

- protect cargo, drivers, and the public;
- reduce avoidable delays and spoilage;
- give dispatchers clear response and escalation rules;
- keep customers informed with verified information; and
- preserve a complete incident record for later analysis.

## 2. Scope

This procedure applies to Palm Logistics dispatchers, drivers, warehouse teams, cold-chain coordinators, customer operations, and Tier 2 Logistics Managers handling active road, port, warehouse, or customs movements.

It covers:

- refrigerated and temperature-sensitive cargo;
- traffic, route, port, weather, and customs delays;
- equipment, inventory, supplier, driver, and fatigue signals;
- shipment risk classification and escalation; and
- service recovery, customer communication, and incident closure.

Life safety always takes priority over cargo or schedule recovery. A driver must not read or respond to operational messages while driving. If there is an accident, fire, medical event, security threat, or unsafe road condition, contact the appropriate emergency service first and notify Palm Logistics when safe to do so.

## 3. Roles and responsibilities

| Role | Primary responsibility |
|---|---|
| Driver | Stop safely, confirm conditions, perform only trained checks, and report changes to Dispatch. |
| Dispatcher | Validate alerts, contact the driver or facility, record actions, and coordinate the initial response. |
| Cold-Chain Coordinator | Assess temperature exposure, arrange cold storage or inspection, and determine cargo disposition with the authorized quality contact. |
| Warehouse or Depot Lead | Confirm capacity, labor, equipment availability, chain of custody, and arrival readiness. |
| Tier 2 Logistics Manager | Own major and critical incidents, approve rerouting or recovery expenditure, and coordinate cross-functional decisions. |
| Customer Operations | Issue customer updates using confirmed facts and the cadence in this SOP. |
| Data Operations | Maintain alert quality, field definitions, access controls, and monitoring availability. |

No employee may mark damaged or temperature-exposed cargo as safe for use unless they have the required quality authority.

## 4. Monitoring data and interpretation

The operational source for this synthetic SOP is `Data/raw/dynamic_supply_chain_logistics_dataset.csv`. Scores represented as decimals use a range of 0 to 1; congestion and route-risk scores use a range of 0 to 10. Higher values indicate worse conditions unless stated otherwise.

| Operational signal | Dataset field | Interpretation |
|---|---|---|
| Temperature | `iot_temperature` | Degrees Celsius reported by the shipment sensor. |
| ETA variance | `eta_variation_hours` | Positive values indicate predicted lateness; negative values indicate an early arrival. |
| Traffic congestion | `traffic_congestion_level` | 0–10; higher is more congested. |
| Port congestion | `port_congestion_level` | 0–10; higher is more congested. |
| Route risk | `route_risk_level` | 0–10; higher is riskier. |
| Weather severity | `weather_condition_severity` | 0–1; higher is more severe. |
| Disruption likelihood | `disruption_likelihood_score` | 0–1 probability-like risk score. |
| Delay probability | `delay_probability` | 0–1 probability-like score. |
| Risk class | `risk_classification` | `Low Risk`, `Moderate Risk`, or `High Risk`. |
| Driver behavior | `driver_behavior_score` | 0–1; higher is better. |
| Fatigue status | `fatigue_monitoring_score` | 0–1; higher is better for this SOP. |
| Supplier reliability | `supplier_reliability_score` | 0–1; higher is more reliable. |
| Equipment availability | `handling_equipment_availability` | 0–1; higher means more equipment is available. |

An automated score is a decision-support signal, not proof of an incident. Dispatch must compare an alert with the latest sensor time, location, shipment profile, driver report, and facility status before selecting a response. Missing, stale, impossible, or contradictory readings must be treated as a data-quality issue and verified through a second source.

## 5. Severity and response targets

| Severity | Definition | Acknowledge | Escalate | Update cadence |
|---|---|---:|---:|---:|
| S1 — Critical | Immediate safety concern, confirmed cargo integrity threat, loss of vehicle control, or multiple simultaneous critical triggers. | 5 minutes | Immediately | Every 30 minutes |
| S2 — Major | High probability of SLA failure, sustained cold-chain excursion, severe congestion, or blocked route requiring intervention. | 15 minutes | Within 15 minutes | Every 60 minutes |
| S3 — Moderate | Degrading condition that can likely be recovered through normal dispatch action. | 30 minutes | If unresolved after 60 minutes | At material change |
| S4 — Advisory | Early warning with no current service or cargo impact. | 60 minutes | Not required unless conditions worsen | At closure |

The response clock starts when the alert is generated or when a Palm Logistics employee first becomes aware of the condition, whichever occurs first.

## 6. Standard triage procedure

For every alert, the dispatcher must:

1. Confirm the shipment identifier, vehicle or container, cargo profile, current location, and last sensor timestamp.
2. Check whether the same shipment has another open alert. Related alerts must be managed under one incident record.
3. Validate the signal against at least one independent source, such as the driver, telematics history, port notice, weather report, or facility contact.
4. Assign a severity using Section 5 and apply the relevant playbook in Sections 7–10.
5. Record the owner, action, time, next checkpoint, and expected customer impact.
6. Escalate when a threshold is met or when safe recovery is uncertain.
7. Continue monitoring until the closure conditions in Section 13 are satisfied.

## 7. Cold-chain control and spoilage prevention

Unless the shipment profile specifies a narrower band, refrigerated fresh perishables must remain between **0.0°C and 4.0°C**.

### 7.1 Alert rules

- **Advisory:** a single reading is outside the approved band but returns to range within 10 minutes.
- **Major breach:** temperature remains outside the approved band for more than 10 minutes, or two consecutive readings are outside the band.
- **Critical breach:** temperature exceeds **8.0°C**, cargo condition is visibly compromised, the refrigeration unit fails, or the exposure duration cannot be established.

### 7.2 Response

1. Confirm the reading timestamp and compare it with the previous three readings.
2. Ask the driver to stop in a safe location before inspecting the refrigeration unit, doors, seals, and sensor placement.
3. Instruct the driver to restart or adjust the auxiliary cooling unit only if trained and safe to do so.
4. Keep cargo doors closed unless an authorized inspection or transfer requires access.
5. If the excursion persists, or the predicted delay exceeds one hour, route the load to an approved cold-storage facility with confirmed capacity.
6. Quarantine affected cargo on arrival. Preserve temperature history and obtain a disposition decision from the authorized quality contact.

Dispatchers and drivers must never discard cargo or declare it safe solely from the IoT reading.

## 8. Congestion, route, weather, and delay response

A major transit-risk review is required when any of the following occurs:

- `port_congestion_level` is greater than **7.0**;
- `traffic_congestion_level` is greater than **8.0** and `eta_variation_hours` is greater than **2.0**;
- `route_risk_level` is greater than **8.0**;
- `weather_condition_severity` is greater than **0.80**; or
- `delay_probability` is greater than **0.75** and the expected delay threatens the customer commitment.

The dispatcher must compare holding, rerouting, cross-docking, and appointment-rescheduling options. A diversion is permitted only after confirming route safety, receiving-facility capacity, operating hours, equipment, cargo compatibility, and the revised ETA.

For shipments affected by congestion at the Ports of Los Angeles or Long Beach, the preferred synthetic recovery location is the **Palm Logistics Inland Empire Overflow Depot, San Bernardino**. It is a planning option, not an automatic destination. The depot lead must confirm acceptance before dispatch issues rerouting instructions.

## 9. Driver safety and fatigue

If `fatigue_monitoring_score` is below **0.30** or `driver_behavior_score` is below **0.35**:

1. instruct the driver to stop at the next safe location;
2. do not pressure the driver to continue in order to protect an ETA;
3. assess hours, rest status, weather, and road conditions using approved operational records;
4. arrange relief, rest, or a safe handoff as appropriate; and
5. classify the event as at least S2 when the signal is confirmed or accompanied by unsafe driving behavior.

These scores must not be used alone for discipline, pay decisions, or adverse employment action. Suspected sensor error must be sent to Data Operations for review.

## 10. Facility, supplier, and customs exceptions

- If `handling_equipment_availability` is below **0.25**, the warehouse lead must reserve alternate equipment, labor, or a nearby facility before arrival.
- If `warehouse_inventory_level` conflicts with the planned order quantity, the warehouse team must verify the stock count before promising fulfillment.
- If `supplier_reliability_score` is below **0.40**, Procurement or the responsible planner must confirm the pickup before dispatching capacity.
- If `customs_clearance_time` exceeds **4.0 hours**, confirm document completeness and contact the approved customs representative. Do not bypass customs controls or submit unverified information.

## 11. Combined high-risk escalation

An incident must be escalated to the Tier 2 Logistics Manager when:

- `risk_classification` is `High Risk` and `delay_probability` is greater than **0.65**;
- `disruption_likelihood_score` is greater than **0.85** and one other major threshold is met;
- two or more S2 triggers affect the same shipment; or
- the dispatcher cannot confirm a safe and compliant recovery path.

The manager decides whether to reroute, transfer cargo, use expedited capacity, notify an insurer or security contact, or activate a broader incident team. These actions must be documented with the reason, approver, time, and expected cost or service impact.

## 12. Customer communication

Customer Operations must use verified facts only. Each update should include:

- shipment reference and current status;
- confirmed cause, or “under investigation” if not yet verified;
- cargo condition when known;
- revised ETA or the time of the next ETA review;
- recovery action underway; and
- time of the next update.

Do not expose driver personal data, internal risk scores, security details, or unconfirmed causes. An S1 or S2 event requires proactive notice when the delivery commitment or cargo integrity may be affected.

## 13. Incident closure and records

An incident may be closed only when the shipment is stable, the responsible team has confirmed the next movement or final disposition, required customer communication is complete, and no alert remains unassigned.

The incident record must contain:

- alert values and timestamps;
- validation sources;
- contacts and decisions;
- approvals, reroutes, transfers, and revised ETAs;
- temperature history or cargo inspection evidence when applicable;
- customer notifications; and
- final outcome, cause category, and follow-up owner.

For this synthetic project, retain incident records for **24 months**. Access must follow least-privilege principles; credentials, personal data, and customer-sensitive information must not be copied into analytics prompts, source code, or public repositories.

## 14. Post-incident review and policy maintenance

Network Operations must review every S1 incident and recurring S2 pattern. The review should identify the initiating condition, response effectiveness, avoidable delay, data-quality problems, customer impact, and corrective action. Threshold changes require approval from the document owner and must be tested against historical synthetic data before release.

Material policy changes increment the major or minor version. Typographical or formatting corrections increment the patch version. Superseded copies should remain available for audit but must be clearly marked as obsolete.

## Appendix A — Quick decision matrix

| Condition | Trigger | Minimum action |
|---|---|---|
| Refrigerated temperature breach | Above 4.0°C for more than 10 minutes or two readings | Validate, contact driver safely, restore cooling, assess diversion, preserve history. |
| Critical temperature breach | Above 8.0°C, equipment failure, or unknown exposure | Declare S1, escalate immediately, arrange cold storage and quarantine. |
| Port congestion | Above 7.0 | Review hold/divert options and confirm capacity before rerouting. |
| Traffic delay | Traffic above 8.0 and ETA variance above 2 hours | Find a safe alternate route or reset the appointment. |
| High-risk shipment | High Risk and delay probability above 0.65 | Escalate to Tier 2 Logistics Manager. |
| Driver or fatigue concern | Fatigue below 0.30 or behavior below 0.35 | Safe stop, verify, and arrange rest or relief. |
| Equipment constraint | Availability below 0.25 | Reserve alternate equipment, labor, or facility. |

## Appendix B — Document approval

| Approval role | Name | Date |
|---|---|---|
| Network Operations owner | Synthetic / not assigned | — |
| Cold-Chain representative | Synthetic / not assigned | — |
| Safety representative | Synthetic / not assigned | — |
