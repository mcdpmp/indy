# Statement of Work: Claims Triage Model and MLOps Platform

**SOW id:** KRS-SOW-2027-031   **Version:** 1.0   **Issue date:** February 19, 2027   **Valid for:** 60 days (through April 20, 2027)

**Between:** Harborline Mutual Insurance Company ("Client") and Kestrel Ridge Solutions ("Kestrel Ridge")

**Governing agreement:** Master Services Agreement HMIC-MSA-2027-02, signed on or before the effective date ("Master Agreement")

## 1. Background and Purpose

The Client issued Request for Proposals HMIC-RFP-2027-02, Machine Learning Claims Triage Model and MLOps Platform, dated December 7, 2026 (the "RFP"). No addenda had been issued at the issue date of this SOW.

The purpose is to give adjusters an advisory triage score at first notice of loss and at 72 hours, and to give Harborline the MLOps capability to run and govern the model. A licensed adjuster remains the decision maker. The effective date is the last signature date in Section 21, planned for April 12, 2027 (A-09).

## 2. Objectives

1. Deliver one triage model assigning each claim one of four handling tracks and a large loss probability, with recall of at least 85 percent on claims later exceeding USD 50,000 on the agreed holdout (D-04).
2. Score claims in production by July 2, 2027, returning a score in 2 seconds or less at the 95th percentile (D-09, D-11).
3. Give Harborline a governable model with fairness results, monitoring thresholds and an accepted inventory entry (D-05, D-06, D-08).
4. Provide a pipeline that retrains, deploys and rolls back without manual steps (D-07, D-13).
5. Transfer operating knowledge, measured by six sessions and a runbook walkthrough (D-12).

## 3. Scope of Work

### 3.1 In Scope

| Id | Work package | Detail and quantity | Produces |
|---|---|---|---|
| S-01 | Initiation | One on site kickoff day in Dunmore, Ohio | D-01 |
| S-02 | Data readiness | Four data sets (claims, policy, adjuster notes, payments); 10 interviews; one Azure architecture | D-02, D-03 |
| S-03 | Model development | One triage model; up to 3 iterations; reason codes | D-04, D-05 |
| S-04 | Model risk | Fairness testing; 80 hours of validation support; one inventory entry | D-06 |
| S-05 | MLOps | One pipeline with registry and rollback in 3 environments in the Client Azure tenant | D-07 |
| S-06 | Monitoring | 4 monitors (data drift, prediction drift, outcome performance, fairness); 3 dashboards | D-08 |
| S-07 | Integration | One real time REST integration with the claims platform | D-09 |
| S-08 | Testing | 3 weeks of shadow mode; 2 weeks of UAT support (SR-13) | D-10 |
| S-09 | Deployment | One production release | D-11 |
| S-10 | Knowledge transfer | Six recorded sessions of up to 3 hours | D-12 |
| S-11 | Hypercare | 90 days from go live; one retraining cycle | D-13 |

### 3.2 Out of Scope

1. Support outside Monday to Friday, 8:00 to 18:00 US Central, and any on site support.
2. On site presence other than kickoff, two key workshops and go live.
3. The RFP phrases "other related services as required" and accuracy "comparable to leading carriers"; only the Section 4 measures apply.
4. Hardware, penetration testing, FedRAMP, CMMC and work needing a clearance.
5. Data cleansing beyond A-02, and integrations other than S-07.
6. Disaster recovery design beyond D-07.
7. Azure consumption and third party licenses.
8. Staff augmentation, permanent placement and offshore delivery.
9. Models other than the triage model.

### 3.3 Exceptions to RFP terms

- X-01 (R-08 ISO 27001): not certified; SR-04 wording is in Section 16. The Client decides acceptability.
- X-02 (R-13 carrier references): no property and casualty references exist. Three SR-10 references are on Form E.
- X-03 (R-23 unlimited revisions): not accepted. Two review cycles per deliverable and the D-13 retrain apply.
- X-04 (R-26 performance bond): not provided. The 15 percent withhold (Section 12) and insurance (Section 19) apply.
- X-05 (Key Terms liability carve outs): liability is not uncapped. The cap is set in the Master Agreement; our position is fees paid in the preceding 12 months.
- X-06 (price validity of 120 days): fees are held for 60 days and re confirmed in writing if signature is after April 20, 2027.

## 4. Deliverables and Acceptance Criteria

Each deliverable has two review cycles included. Further cycles follow Section 14.

| Id | Deliverable | Format | Milestone | Acceptance criteria | Approver |
|---|---|---|---|---|---|
| D-01 | Project Management Plan | Document | M1 | Holds scope, schedule, RACI, risks, communication plan; approved within 5 business days | Client Sponsor |
| D-02 | Data Readiness Assessment | Document | M2 | Profiles all four data sets with issue counts; architecture approved by Client Architect | Product Owner |
| D-03 | Feature and Label Specification | Document | M2 | Defines large loss label (final incurred above USD 50,000), four tracks, fairness thresholds, holdout of the latest 12 months | Product Owner |
| D-04 | Trained model and evaluation report | Model | M3 | Recall of at least 85 percent on claims later exceeding USD 50,000 on the D-03 holdout | Product Owner |
| D-05 | Model documentation package | Document | M3 | Model card, lineage, limitations; each score returns top 5 reason codes | Model Risk Lead |
| D-06 | Model Governance Pack | Document | M5 | Selection rate ratio of at least 0.80 per tested class or documented mitigation; zero open high validation findings; inventory entry | Model Risk Lead |
| D-07 | MLOps pipeline and infrastructure as code | Code | M4 | Commit to registered model with no manual step; rollback in under 30 minutes in test | Client Architect |
| D-08 | Monitoring dashboards and alert runbook | Dashboards | M4 | 4 monitors live; 5 of 5 seeded drift cases alert within 1 hour | Client Architect |
| D-09 | Claims platform integration | Interface | M4 | 40 end to end cases pass; 95th percentile response 2 seconds or less at 40 requests per minute | Client Architect |
| D-10 | Test results and UAT sign off | Document | M5 | At least 90 percent of 100 UAT cases pass; no open Severity 1 defects | Product Owner |
| D-11 | Production deployment | Software | M6 | Go live checklist signed; production smoke tests pass; rollback tested | Client Sponsor |
| D-12 | Training and handover documentation | Sessions | M7 | 6 sessions held, at least 15 attendees; runbook walkthrough done | Operations Lead |
| D-13 | Retrained model and close out report | Model | M8 | Retrain meets D-04 recall on a refreshed holdout; Severity 1 and 2 defects closed | Client Sponsor |

## 5. Assumptions

If an assumption proves false, Kestrel Ridge raises a change request under Section 14.

1. A-01: The Client provides the four data sets and dictionary by April 26, 2027.
2. A-02: If over 5 percent of sampled records fail agreed validation rules, remediation is a change.
3. A-03: The model serves up to 40 scoring requests per minute; more is a change.
4. A-04: The solution runs in the Client Azure tenant in a US region; the Client pays consumption.
5. A-05: Client experts give up to 8 hours per week in Phase 1 and UAT, or the schedule moves.
6. A-06: Protected class data or an approved proxy exists. If not, D-06 reports on available classes.
7. A-07: The Client reviews deliverables within 5 business days and decides blockers within 3.
8. A-08: Work is remote from the United States, except the events in S-01 and S-09.
9. A-09: Signature occurs by April 9, 2027, so work starts April 12. Clarify with the Client: RFP Section 2 gives a March 29 start, before the March 26 award.
10. A-10: "Modern claims platform" (R-24) means one platform with a REST API and sandbox; real time means 2 seconds or less. Clarify with the Client.
11. A-11: R-25 ("industry leading and satisfactory") is replaced by the measures in D-04, D-08 and D-09. Clarify with the Client.
12. A-12: The 25 percent cycle time goal is measured by Harborline and is not a Kestrel Ridge commitment.
13. A-13: Adjuster notes stay in the Client tenant (R-11).

## 6. Dependencies and Client Responsibilities

| Id | Dependency | Client owner | Needed by | Effect if late |
|---|---|---|---|---|
| C-01 | Signed Master Agreement and SOW | Donovan Pruitt, Sourcing Lead | April 9, 2027 | Start moves day for day |
| C-02 | Azure tenant access | Tomas Weir, Enterprise Architect | April 19, 2027 | Day for day |
| C-03 | Data sets and dictionary | Priya Natarajan, Director, Claims Analytics | April 26, 2027 | Day for day; change after 20 business days |
| C-04 | Model risk policy | Raymond Okafor, Model Risk Lead | April 19, 2027 | D-05 and D-06 rework is a change |
| C-05 | Claims platform sandbox and API specification | Tomas Weir, Enterprise Architect | May 3, 2027 | Day for day; Kestrel Ridge will promptly notify the Client of the new date |
| C-06 | Validation team available June 7 to 25, 2027 | Raymond Okafor, Model Risk Lead | June 7, 2027 | M5 moves day for day |
| C-07 | Feedback on deliverables | Approver in Section 4 | Per Section 13 | Deemed acceptance |

## 7. Constraints

1. Hosting: Client Azure tenant in the United States (RFP R-05, R-11).
2. Dates: production by July 2, 2027; hypercare ends September 30, 2027 (RFP Section 3).
3. Governing law: State of Ohio (RFP Section 9).

## 8. Roles and Responsibilities

| Role | Organization | Name |
|---|---|---|
| Client Sponsor | Client | Elaine Marchetti |
| Product Owner | Client | Priya Natarajan |
| Client Architect | Client | Tomas Weir |
| Model Risk Lead | Client | Raymond Okafor |
| Operations Lead | Client | Gwen Aldous |
| Engagement Lead | Kestrel Ridge | Dana Whitfield |
| Project Manager | Kestrel Ridge | Luis Ferreira |
| Technical Lead | Kestrel Ridge | Anika Rao |
| MLOps Architect | Kestrel Ridge | Ben Soriano |

Key personnel are not removed or replaced during the engagement without the client's prior written consent, except in the case of resignation, illness, leave or termination for cause (SR-09). All staff are US based employees.

RACI (R: Responsible, A: Accountable, C: Consulted, I: Informed). Each row has one A.

| Deliverable | Client Sponsor | Product Owner | Client Architect | Model Risk Lead | Engagement Lead | Project Manager | Technical Lead |
|---|---|---|---|---|---|---|---|
| D-01 | A | C | I | I | R | R | I |
| D-02 | I | A | C | C | C | R | R |
| D-03 | I | A | C | C | C | I | R |
| D-04 | I | A | C | C | C | I | R |
| D-05 | I | C | I | A | C | I | R |
| D-06 | I | C | I | A | C | R | R |
| D-07 | I | C | A | I | C | I | R |
| D-08 | I | C | A | C | C | I | R |
| D-09 | I | C | A | I | C | I | R |
| D-10 | I | A | C | C | C | R | R |
| D-11 | A | C | C | I | R | R | R |
| D-12 | I | C | I | I | A | R | R |
| D-13 | A | C | C | C | R | R | R |

## 9. Project Governance and Reporting

Hybrid agile under PMI aligned governance (SR-01), with Azure DevOps, Microsoft Project, Teams, SharePoint and Power BI (SR-02).

1. Weekly status meeting, 30 minutes, Product Owner, Project Manager and Technical Lead.
2. Monthly executive review, 60 minutes, Client Sponsor and Engagement Lead (the steering committee of SR-18).
3. Weekly written status report with a Power BI dashboard.
4. Escalation (SR-18): Level 1 is the project manager and client project lead, who resolve matters within three business days. Level 2 is the engagement director and the client sponsor, who respond within five business days. Level 3 is the Kestrel Ridge chief delivery officer and the client executive sponsor.

## 10. Timeline and Milestones

Dates are planned acceptance dates; deliverables are submitted 5 business days earlier.

| Id | Milestone | Deliverables | Planned date | Entry condition |
|---|---|---|---|---|
| M1 | Plan approved | D-01 | April 23, 2027 | C-01, C-02 met |
| M2 | Phase 1 complete | D-02, D-03 | May 7, 2027 | C-03, C-04 met |
| M3 | Model delivered | D-04, D-05 | May 28, 2027 | M2 accepted |
| M4 | Pipeline, monitoring, integration in test | D-07, D-08, D-09 | June 4, 2027 | C-05 met |
| M5 | Shadow mode, validation, UAT complete | D-06, D-10 | June 25, 2027 | M3, M4 accepted; C-06 met |
| M6 | Production deployment | D-11 | July 2, 2027 | M5 accepted |
| M7 | Training and handover complete | D-12 | August 27, 2027 | M6 accepted |
| M8 | Hypercare ends | D-13 | September 30, 2027 | 90 days after M6 |

The critical path is M3 to M6 with 3 business days of float. A second review cycle takes up to 8 business days and uses the float; beyond that Section 14 applies.

## 11. Effort Estimate and Pricing Basis

Pricing model: fixed price per phase, at Kestrel Ridge standard rates in USD per hour. No rate exceptions apply.

| Role | Rate | Phase 1 h | Phase 2 h | Phase 3 h | Phase 4 h | Total h | Amount |
|---|---|---|---|---|---|---|---|
| Principal Consultant | 245 | 120 | 200 | 120 | 40 | 480 | 117,600 |
| Senior Consultant | 205 | 240 | 520 | 480 | 200 | 1,440 | 295,200 |
| Consultant | 165 | 160 | 480 | 560 | 160 | 1,360 | 224,400 |
| Analyst | 125 | 120 | 200 | 240 | 60 | 620 | 77,500 |
| Project Manager | 185 | 80 | 100 | 100 | 60 | 340 | 62,900 |
| Total | | 720 | 1,500 | 1,500 | 520 | 4,240 | 777,600 |

Phase fixed fees in USD: Phase 1 134,800; Phase 2 278,300; Phase 3 268,700; Phase 4 95,800; total 777,600. The fee changes only through Section 14. Travel is included. Taxes are excluded. Work outside this SOW is priced at these rates; an additional retraining cycle is USD 32,560 fixed.

## 12. Payment Schedule

Invoices are due net 45 days from receipt, under approved exception EXC-2027-018 (Kestrel Ridge Finance Director) to match RFP Section 9. Fifteen percent of each phase fee is withheld until the end of hypercare.

| Invoice | Trigger | Percent of price | Amount (USD) |
|---|---|---|---|
| 1 | Acceptance of M2 (85 percent of Phase 1) | 14.7 | 114,580 |
| 2 | Acceptance of M5 (85 percent of Phase 2) | 30.4 | 236,555 |
| 3 | Acceptance of M6 (85 percent of Phase 3) | 29.4 | 228,395 |
| 4 | Acceptance of M8 (85 percent of Phase 4) | 10.5 | 81,430 |
| 5 | Acceptance of M8 (withheld 15 percent) | 15.0 | 116,640 |
| Total | | 100 | 777,600 |

Disputes are notified in writing within 15 days of the invoice date. Late payment follows the Master Agreement.

## 13. Acceptance Process

1. Kestrel Ridge submits a deliverable with written notice to the approver in Section 4.
2. The approver has 5 business days to accept in writing or report defects against the acceptance criteria.
3. Kestrel Ridge corrects within 5 business days; the second review period is 3 business days. Two review cycles are included.
4. If the approver does not respond within the review period, the deliverable is deemed accepted.
5. A third and later cycle is a change request under Section 14.
6. Acceptance triggers the invoice in Section 12.

## 14. Change Control

All changes to baselined scope, schedule, cost or deliverables go through a written change control process (SR-12). Either party may raise a change request. Within five business days, the project manager and solution architect prepare an impact analysis covering scope, effort, schedule, cost, risk, dependencies and any effect on acceptance criteria. No work on the change begins until it is approved in writing by authorized signatories of both parties. Section 3.2 items, false assumptions and cycles beyond Section 13 are changes. The change register is reported weekly.

## 15. Risks

| Id | Risk | Likelihood | Impact | Mitigation | Owner | Trigger |
|---|---|---|---|---|---|---|
| RK-01 | The 12 week build slips from late data or reviews | Medium | High | Early profiling; review calendar; float in Section 10 | Project Manager | C-03 late |
| RK-02 | Holdout recall falls below 85 percent | Medium | High | Baseline in week 3; 3 iterations; change request if data cannot support it | Technical Lead | Recall under 80 percent in week 5 |
| RK-03 | Bias or unexplained output (SR-06) | Medium | High | Fairness metrics in D-03; reason codes; human review | Technical Lead | Ratio under 0.80 |
| RK-04 | Claims platform interface is unstable | Medium | High | Early spike; mock service | MLOps Architect | Failed spike |
| RK-05 | Personal data in notes is exposed | Low | High | Notes stay in tenant; access reviews (SR-07) | MLOps Architect | Access anomaly |
| RK-06 | Adjusters do not use scores | Medium | Medium | Training in D-12; adoption metrics | Operations Lead | Low usage after 30 days |

## 16. Security and Data Handling

1. Client data remains in the client's environment. Client data is never used to train, fine-tune or improve any foundation model, ours or a third party's (SR-07). Policyholder data is not copied to Kestrel Ridge systems except as approved in writing.
2. Data in transit is encrypted with TLS 1.2 or higher, and we disable older protocols and weak cipher suites. Data at rest is encrypted with AES-256 using the cloud provider's managed encryption, with customer managed keys in Azure Key Vault or AWS KMS where the client requires them (SR-05).
3. Kestrel Ridge Solutions holds a SOC 2 Type II report covering the Security, Availability and Confidentiality trust services criteria. The full report is confidential and is provided on request under a mutual non-disclosure agreement (SR-03).
4. Kestrel Ridge Solutions is not currently certified to ISO/IEC 27001. We have completed an ISO 27001 gap assessment against the full control set. A Stage 1 and Stage 2 certification audit with an accredited certification body is planned for the second half of 2027. We will not describe ourselves as ISO 27001 certified, or as compliant with the standard, until a certificate has been issued (SR-04).
5. Each delivered model or generative AI solution includes a model card describing intended use, training and evaluation data, known limitations and performance metrics. Solutions that influence decisions about people or carry material risk are designed with human review, so that a person can inspect, override and record the outcome of the model's output (SR-06).
6. Kestrel Ridge Solutions maintains a documented business continuity and disaster recovery plan for its own operations, which is reviewed and tested every year (SR-17).
7. No subcontractors are planned. Where one is needed, we disclose the subcontractor's name, the scope of work and the proportion of effort in advance of the SOW, and we obtain the client's written consent before the subcontractor begins work (SR-16).
8. Working copies are deleted within 30 days of close, with written confirmation. Confirmed security incidents are notified within 24 hours.

## 17. Warranty and Support

1. Kestrel Ridge Solutions warrants delivered software and data pipelines for 90 days after client acceptance of D-11. During the warranty period we correct defects, meaning failures to conform to the accepted requirements, at no additional charge (SR-14). This is the hypercare period.
2. Warranty excludes changes requested after acceptance, defects from Client modifications or third party changes, and misuse.
3. Support is provided remotely Monday to Friday, 8:00 to 18:00 US Central, excluding US federal holidays, through a ticket queue. We do not provide 24x7 support or on-site support, and out of hours coverage is not included.
4. Response targets: Severity 1 within 4 business hours, Severity 2 within 1 business day, Severity 3 within 2 business days.
5. Severity 1: no user can use the core function. Severity 2: a core function is impaired and a workaround exists. Severity 3: any other defect.

## 18. Intellectual Property and Confidentiality

1. The Client owns the deliverables, including trained models, upon payment in full. Kestrel Ridge retains ownership of pre-existing materials, tools, accelerators, frameworks, templates and methods. Where pre-existing materials are embedded in a deliverable, we grant the client a perpetual, non-exclusive, royalty-free, worldwide license to use, copy and modify them as part of the deliverable for its internal business purposes. Models trained on client data are not reused for other clients (SR-19).
2. Open source components keep their own licenses and are listed with D-07.
3. Each party keeps the other's confidential information confidential during the term and for 3 years after.

## 19. Termination and Dispute Resolution

Termination, liability and disputes are governed by the Master Agreement; this SOW does not change them, except as stated in X-04 and X-05. Insurance (SR-11): cyber liability USD 5,000,000; professional liability USD 5,000,000; general liability USD 2,000,000 per occurrence; workers compensation as required by law.

## 20. Definitions and Glossary

| Term | Meaning |
|---|---|
| Acceptance | Written approval under Section 13, or deemed acceptance |
| Business Day | Monday to Friday, excluding US federal holidays |
| Defect | A failure to meet acceptance criteria |
| Go Live | Release to production use, evidenced by the D-11 checklist |
| Severity | The rating in Section 17 |
| UAT | User acceptance testing by the Client |
| SR-nn | Kestrel Ridge standard response with that number |

## 21. Signatures

By signing, each party agrees to this SOW, id KRS-SOW-2027-031, version 1.0, subject to the Master Agreement.

| | Client | Kestrel Ridge Solutions |
|---|---|---|
| Legal name | Harborline Mutual Insurance Company | Kestrel Ridge Solutions |
| Signature | | |
| Name | Elaine Marchetti | Dana Whitfield |
| Title | Vice President, Claims Operations | Partner |
| Date | | |

## Appendix A: RFP traceability matrix

| RFP id | Summary | Maps to | Reference |
|---|---|---|---|
| R-01 | PM methodology | Standard response | SR-01, Section 9 |
| R-02 | PM tools | Standard response | SR-02, Section 9 |
| R-03 | Status and escalation | Standard response | SR-18, Section 9 |
| R-04 | Triage model | Deliverable | D-04 |
| R-05 | MLOps pipeline | Deliverable | D-07 |
| R-06 | Monitoring | Deliverable | D-08 |
| R-07 | Model risk | Deliverable | D-05, D-06 |
| R-08 | ISO 27001 | Exception | X-01 |
| R-09 | SOC 2 Type II | Standard response | SR-03, Section 16 |
| R-10 | Encryption | Standard response | SR-05, Section 16 |
| R-11 | Data in tenant | Standard response | SR-07, A-13 |
| R-12 | Responsible AI | Standard response | SR-06, D-05, D-06 |
| R-13 | Carrier references | Exception | X-02 |
| R-14 | Named staff | Standard response | SR-09, Section 8 |
| R-15 | Insurance | Standard response | SR-11, Section 19 |
| R-16 | Change control | Standard response | SR-12, Section 14 |
| R-17 | Test strategy | Deliverable | D-10 |
| R-18 | Warranty, support | Standard response | SR-14, Section 17 |
| R-19 | Training | Deliverable | D-12 |
| R-20 | Ownership | Standard response | SR-19, Section 18 |
| R-21 | Subcontractors | Standard response | SR-16, Section 16 |
| R-22 | BCP and DR | Standard response | SR-17, Section 16 |
| R-23 | Unlimited revisions | Exception | X-03 |
| R-24 | Real time integration | Deliverable | D-09, A-10 |
| R-25 | Industry leading performance | Assumption | A-11 |
| R-26 | Performance bond | Exception | X-04 |
