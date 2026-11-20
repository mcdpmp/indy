# Indy handoff file (schema 1.0)

Indy writes two outputs for every readiness check, both into Indy's own folder for the opportunity
(`{opportunity}/_opportunity/outputs/indy/`) through Vera:

| File | For | Notes |
|---|---|---|
| `indy_handoff.json` | Project Initiation (agent 3) | machine-readable, described here |
| `readiness_report.md` | Michael | the human report, same findings |

**The file name `indy_handoff.json` is part of the contract.** Project Initiation finds it by name.
Renaming it, in Indy or in Vera's output rules, breaks Project Initiation. Change the content shape by
raising `schema_version`, never the name.

**Versions.** Vera never overwrites, so a re-run is stored as `indy_handoff__v2.json`, then `__v3`, and
so on. The newest version is the one to read. The file says so itself in `how_to_read`.

**Validation.** Indy checks the file against [`indy/handoff.schema.json`](../indy/handoff.schema.json)
(JSON Schema 2020-12, `additionalProperties: false` throughout) before it uploads anything. If it does
not validate, the job fails with the first problem named and nothing is stored. Readers should still
check `schema` is `indy_handoff` and read `schema_version` before relying on a field.

**Schema versions.** `1.0` is the first. A minor bump (1.1) only adds optional meaning and keeps every
1.0 field. A major bump (2.0) may change or remove fields, and Indy and Project Initiation are
updated together.

## What is in it

| Field | Meaning |
|---|---|
| `schema`, `schema_version`, `generated_at`, `indy_version` | what this is, which shape, when (UTC), which Indy |
| `how_to_read` | the reading rules above, in words |
| `opportunity` | `id`, `name` |
| `verdict` | final verdict: `ready`, `ready_with_conditions` or `not_ready` |
| `checklist_verdict` | the verdict from the checklist alone, before findings |
| `verdict_reasons` | ids of the stated findings that moved the verdict, if any |
| `checklist` | each item: `id`, `label`, `kind` (blocker or warning), `status` (present, partial, missing, unclear, skipped), `detail`, `basis` (stated or computed) |
| `documents.signed_sow` | the SOW Indy checked: `doc_id`, `filename`, `signature_state`; null if none |
| `documents.considered` | every document Indy read: Vera `doc_id`, `filename`, `category`, `role` (sow, rfp, supporting, scoper_output). This is the approved package the findings refer to |
| `documents.not_read` | documents that could not be read, with the reason. Nothing relies on them |
| `findings` | see below |
| `project_summary` | suggested customer, scope, deliverables, key_dates, commercial_terms, assumptions, dependencies, people. Each item has `text`, `basis`, `quote`, `document`. Null when no SOW was read |
| `methodology_suggestion` | `suggestion` (waterfall, scrum or null), `reasoning`, counted `signals`, and a note. A suggestion only |
| `inferred_followups` | model-written `customer_questions`, `delivery_questions`, `risks`, `later_agents_need`. All inferred. Null if the model did not run |
| `model_problems` | model stages that failed or were cut short, so a reader knows what is missing |

## Findings

Each finding is a gap in the SOW found by reading it for scope risk.

| Field | Meaning |
|---|---|
| `id` | `F-` plus six hex characters, a hash of category and quote. The same problem in the same words keeps its id across re-runs |
| `category` | `ambiguity`, `acceptance`, `complexity`, `scope_boundary`, `assumptions_dependencies`, `commercial_timeline` |
| `severity` | `high`, `medium`, `low` |
| `basis` | `stated`: the quoted text is the problem, or code measured a gap in the document. `inferred`: Indy is reading between the lines |
| `title`, `why` | what is wrong, and why it matters |
| `quote` | text copied from the source document, at least 8 characters. Indy checks it is really in the document; a finding whose quote is not found is dropped and never written here |
| `source_document`, `where` | the document (`doc_id`, `filename`) and the section heading |
| `evidence_kind` | `text`, or `absence` when something is missing and the quote is the nearest heading |
| `question`, `asked_of` | a clarifying question, and who should answer: `customer`, `sales` or `delivery` |
| `destination` | where Project Initiation should start it: `starting_risk`, `starting_issue` or `open_question` |
| `origin` | `code` (a rule or measurement) or `model` (a proposal that passed the quote check) |

Only stated findings can move the verdict, by the configured effect for their severity
(`findings.verdict_effect` in `config.yaml`). Defaults: a stated high finding turns Ready into Ready
with conditions; everything else is listed without effect. Findings never make a deal Not ready by
default, because Not ready is for missing or unusable documents.

## Out of scope on purpose

Indy flags a missing or inconsistent timeline statement as a finding. It does not build or analyse a
project schedule.
