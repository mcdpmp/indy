# Statement of Work: Student Services Applications on Microsoft Power Platform

**SOW id:** KRS-SOW-2027-044   **Version:** 1.0   **Issue date:** February 12, 2027   **Valid for:** 60 days from the issue date (through April 13, 2027)

**Between:** Northfield State University ("University") and Kestrel Ridge Solutions ("Kestrel Ridge")

**Governing agreement:** Master Services Agreement NSU-MSA-2027-031, signed on or before the effective date ("Master Agreement")

## 1. Background and Purpose

Northfield State University is a public university of about 21,000 students. Student services are delivered through spreadsheets, email inboxes and aging web forms. The Division of Student Affairs has selected Microsoft Power Platform as the standard for student service workflows. The University issued Request for Proposal NSU-2027-031 on January 11, 2027 (the "RFP"). This SOW describes how Kestrel Ridge will respond to it.

The purpose is to give students and staff modern and intuitive service applications on Microsoft Power Platform and to prepare University staff to adopt them. The effective date is the date of the last signature in Section 19.

## 2. Objectives

1. Deliver Release 1 (three applications) by July 30, 2027 and Release 2 (four applications) by October 29, 2027.
2. Prepare about 300 staff in 14 offices to use the applications, measured by completion of the training sessions in D-08.
3. Improve the student experience of University services.
4. Increase staff efficiency in the offices that use the applications.

## 3. Scope of Work

### 3.1 In Scope

| Id | Work package | Detail | Produces |
|---|---|---|---|
| S-01 | Initiation | One on campus kickoff workshop; charter and plan | D-01 |
| S-02 | Design | One solution design per application, 7 in total | D-02 |
| S-03 | Build | Seven Power Apps solutions with Power Automate flows and Dataverse tables as needed: Advising Appointment Scheduler, Financial Aid Document Tracker, Housing Request Manager, Student Case Management, Registrar Request Portal, Career Services Employer Intake, Tutoring Center Check-in | D-03 |
| S-04 | Integration | CampusCore through its REST APIs, with nightly synchronization of student records and real time lookups; Microsoft 365 identity | D-04 |
| S-05 | Dashboards | Power BI dashboards for service managers showing appointment volumes, case aging and service levels by office; further views as needed | D-05 |
| S-06 | Change management | Stakeholder analysis, communications, resistance management and adoption tracking for 14 offices | D-06 |
| S-07 | Training | Role based sessions, job aids, recordings, train the trainer material, etc. for about 300 staff | D-07, D-08 |
| S-08 | Accessibility | WCAG 2.1 AA build and one VPAT | D-09 |
| S-09 | Testing | Test strategy (SR-13) and support for University user acceptance testing | D-03 |
| S-10 | Hypercare | 60 days after each release; handover to the University support team | D-10 |

### 3.2 Out of Scope

1. On campus presence other than the kickoff, key workshops and go live. Training is delivered remotely or at those workshops.
2. Hardware, Microsoft licenses and Dataverse capacity, which are provided by the University.
3. Penetration testing, FedRAMP and CMMC work, and work needing a security clearance.
4. Migration or cleansing of data held in spreadsheets and inboxes.
5. Third party accessibility audits.
6. Staff augmentation, permanent placement and offshore delivery.

## 4. Deliverables and Acceptance Criteria

| Id | Deliverable | Format | Milestone | Acceptance criteria | Approver |
|---|---|---|---|---|---|
| D-01 | Project Charter and Plan | Document | M1 | Approved in writing within 5 business days | Executive Sponsor |
| D-02 | Solution Designs | Documents | M2, M4 | Signed off per application | Product Owner |
| D-03 | Seven Power Apps solutions | Deployed apps | M4, M5 | Pass UAT; modern and intuitive, to the University's satisfaction | Product Owner |
| D-04 | CampusCore Integration | Interfaces | M4, M5 | | |
| D-05 | Power BI Dashboards | Dashboards as needed | M4, M5 | | |
| D-06 | Change Management Plan | Document | M3 | | |
| D-07 | Training Plan | Document | M3 | | |
| D-08 | Training Materials and Recordings | Job aids, recordings, train the trainer kit, etc. | M4, M5 | | |
| D-09 | Accessibility Conformance Report | VPAT | M5 | Lists results against WCAG 2.1 AA; no open critical accessibility defects | Accessibility Resource Center |
| D-10 | Handover Package | Runbooks, support guide | M6 | Walkthrough held with the support team | Product Owner |

## 5. Assumptions

1. The University will cooperate with Kestrel Ridge and provide access to staff and systems.
2. The University will make decisions in a reasonable time.

## 6. Dependencies and Client Responsibilities

| Id | Dependency | University owner | Needed by | Effect if late |
|---|---|---|---|---|
| C-01 | Signed Master Agreement and SOW | Marcus Delacroix, Procurement Officer | April 9, 2027 | Start moves day for day |
| C-02 | Microsoft 365 tenant, three environments and Azure DevOps pipelines | Pavel Horvat, IT Director | April 19, 2027 | Schedule moves day for day |
| C-03 | CampusCore API documentation and sandbox | Pavel Horvat, IT Director | April 26, 2027 | Integration moves day for day |
| C-04 | Synthetic data for development and testing | Joyce Ndiaye, Associate Director, Student Affairs | April 26, 2027 | Build moves day for day |
| C-05 | Academic calendar with peak periods | Joyce Ndiaye, Associate Director, Student Affairs | April 23, 2027 | Training dates move |
| C-06 | Written feedback on deliverables | Approver in Section 4 | Per Section 12 | Schedule moves day for day |

## 7. Constraints

1. Technology: Power Apps, Power Automate and Dataverse in the University's three environments, promoted as managed solutions through University pipelines (RFP Appendix B).
2. Dates: Release 1 July 30, 2027, Release 2 October 29, 2027, close January 14, 2028 (RFP Section 5).
3. Public records: the University is subject to state public records law (RFP Section 8).

## 8. Roles and Responsibilities

| Role | Organization | Name | Responsibility |
|---|---|---|---|
| Executive Sponsor | University | Dr. Alan Whitcombe, Vice President for Student Affairs | Chairs steering; approves plan |
| Product Owner | University | Joyce Ndiaye | Day to day decisions; accepts apps |
| Engagement Director | Kestrel Ridge | Marguerite Obi | Accountable for delivery |
| Project Manager | Kestrel Ridge | Sam Kowalczyk | Plan, status, risks |
| Solution Architect | Kestrel Ridge | Hiro Tanabe | Design and build quality |
| Change Management Lead | Kestrel Ridge | Carmen Duarte | Change management and training |

Key personnel are not removed or replaced during the engagement without the client's prior written consent, except in the case of resignation, illness, leave or termination for cause (SR-09). All staff are US based employees. Three higher education references are provided with the proposal.

## 9. Project Governance and Reporting

Kestrel Ridge uses a PMI aligned hybrid agile approach (SR-01) with Azure DevOps, Microsoft Project, Teams, SharePoint and Power BI (SR-02).

1. Weekly status meeting with the Product Owner.
2. Biweekly written status report covering progress, risks, issues and decisions needed.
3. Monthly steering committee with a one page dashboard.
4. Escalation (SR-18): Level 1 is the project manager and client project lead, who resolve matters within three business days. Level 2 is the engagement director and the client sponsor, who respond within five business days. Level 3 is the Kestrel Ridge chief delivery officer and the client executive sponsor.

## 10. Timeline and Milestones

| Id | Milestone | Deliverables | Date | Entry condition |
|---|---|---|---|---|
| M1 | Kickoff and plan approved | D-01 | April 30, 2027 | C-01, C-02 met |
| M2 | Release 1 designs approved | D-02 | May 28, 2027 | M1 accepted |
| M3 | Change management and training plans approved | D-06, D-07 | June 25, 2027 | C-05 met |
| M4 | Release 1 live | D-02 to D-05, D-08 | July 30, 2027 | M2, M3 accepted |
| M5 | Release 2 live | D-03 to D-05, D-08, D-09 | October 29, 2027 | M4 accepted |
| M6 | Project close | D-10 | January 14, 2028 | M5 accepted; Release 2 hypercare ended December 28, 2027 |

Review periods in Section 12 are included in these dates.

## 11. Effort Estimate and Pricing Basis

Pricing model: fixed price, at Kestrel Ridge standard rates in USD per hour. The price is inclusive of all revisions requested before final acceptance. Travel is billed at cost with no markup after advance approval. The price is valid for 90 days from the proposal due date.

| Role | Rate | Hours | Amount (USD) |
|---|---|---|---|
| Principal Consultant | 245 | 600 | 147,000 |
| Senior Consultant | 205 | 2,400 | 492,000 |
| Consultant | 165 | 3,200 | 528,000 |
| Analyst | 125 | 1,480 | 185,000 |
| Project Manager | 185 | 800 | 148,000 |
| Total | | 8,480 | 1,500,000 |

Price by RFP category in USD: seven applications 820,000 (Advising Appointment Scheduler 110,000; Financial Aid Document Tracker 120,000; Housing Request Manager 105,000; Student Case Management 190,000; Registrar Request Portal 130,000; Career Services Employer Intake 85,000; Tutoring Center Check-in 80,000); integration and dashboards 200,000; change management 150,000; training 130,000; hypercare 90,000; project management 110,000; total 1,500,000.

## 12. Payment Schedule and Acceptance

Invoices are due net 45 from receipt of an accepted invoice, under approved exception EXC-2027-022 (Kestrel Ridge Finance Director) to match RFP Section 8.

| Invoice | Trigger | Percent | Amount (USD) |
|---|---|---|---|
| 1 | Acceptance of M1 | 20 | 300,000 |
| 2 | Acceptance of M4 | 30 | 450,000 |
| 3 | Acceptance of M5 | 35 | 525,000 |
| 4 | Acceptance of M6 | 15 | 225,000 |
| Total | | 100 | 1,500,000 |

Acceptance process: Kestrel Ridge submits each deliverable to the approver in Section 4. The approver reviews it within 10 business days and reports any issues. Kestrel Ridge makes revisions to the applications and training materials until the University is satisfied. Acceptance of a milestone triggers the related invoice.

## 13. Change Control

Changes to scope, schedule or cost will be handled through the change control process.

## 14. Risks

| Id | Risk | Likelihood | Impact |
|---|---|---|---|
| K-1 | CampusCore APIs do not support a needed function | Medium | High |
| K-2 | University staff are not available for workshops and testing | Medium | Medium |
| K-3 | Staff do not adopt the new applications | Medium | High |
| K-4 | Schedule slips because of University decisions | Medium | Medium |
| K-5 | Requirements grow during the project | High | Medium |
| K-6 | Training falls in peak academic periods | Medium | Medium |

## 15. Security and Data Handling

1. Client data remains in the client's environment. Client data is never used to train, fine-tune or improve any foundation model, ours or a third party's (SR-07). University data stays in the University Microsoft tenant.
2. Data in transit is encrypted with TLS 1.2 or higher, and we disable older protocols and weak cipher suites. Data at rest is encrypted with AES-256 using the cloud provider's managed encryption (SR-05).
3. Kestrel Ridge Solutions holds a SOC 2 Type II report covering the Security, Availability and Confidentiality trust services criteria. The full report is confidential and is provided on request under a mutual non-disclosure agreement (SR-03).
4. Kestrel Ridge Solutions is not currently certified to ISO/IEC 27001. A Stage 1 and Stage 2 certification audit with an accredited certification body is planned for the second half of 2027 (SR-04).
5. Working copies are deleted within 30 days of close, with written confirmation.

## 16. Warranty and Support

1. Kestrel Ridge Solutions warrants delivered software for 90 days after client acceptance of each release (SR-14). The warranty does not cover changes requested by the client, defects caused by modifications made by others, third-party platform changes or misuse.
2. Support is provided remotely Monday to Friday, 8:00 to 18:00 US Central, excluding US federal holidays, through a ticket queue. We do not provide 24x7 support or on-site support.
3. Initial response targets: four business hours for critical issues, one business day for high priority and two business days for normal requests.
4. Support after the warranty runs under a separate support schedule for the term in the RFP, to March 31, 2028, with up to two one year extensions.

## 17. Intellectual Property and Confidentiality

The University owns all custom applications, flows, tables and documentation produced for it, upon payment in full. Kestrel Ridge retains pre-existing materials, tools and methods and grants the University a perpetual, non-exclusive, royalty-free license to use them as embedded in the deliverables (SR-19). Each party keeps the other's confidential information confidential for the term and 3 years after.

## 18. Termination and Dispute Resolution

Termination, liability and disputes are governed by the Master Agreement. The Kestrel Ridge position on liability is a cap at fees paid in the preceding 12 months, to be agreed with the University and the State Attorney General office in the Master Agreement. Insurance (SR-11): cyber liability USD 5,000,000; professional liability USD 5,000,000; general liability USD 2,000,000 per occurrence; workers compensation as required by law.

## 19. Definitions and Signatures

Business Day means Monday to Friday, excluding US federal holidays. Go Live means release to production use by University staff. Acceptance means written approval under Section 12.

By signing, each party agrees to this SOW, id KRS-SOW-2027-044, version 1.0, subject to the Master Agreement.

| | University | Kestrel Ridge Solutions |
|---|---|---|
| Legal name | Northfield State University | Kestrel Ridge Solutions |
| Signature | | |
| Name | Marcus Delacroix | Marguerite Obi |
| Title | Procurement Officer | Engagement Director |
| Date | | |
