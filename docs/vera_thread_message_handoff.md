# Message for the Vera thread: handoff file for Project Initiation, and one PLATFORM ASK

From the Indy thread. Indy 0.2.0 is pushed (https://github.com/mcdpmp/indy, 183 tests passing). It now
does the scope-risk review of the SOW and writes a machine-readable handoff file for Project
Initiation next to its human report. Full brief: `agents/indy/docs/vera.md`; field-by-field schema:
`agents/indy/docs/handoff_schema.md`.

## What Project Initiation can rely on

- **File name:** `indy_handoff.json`, in `{oid}/_opportunity/outputs/indy/`, with `readiness_report.md`
  beside it. The name is part of the contract: renaming it in Indy or in any Vera output rule would
  break Project Initiation. A change of shape raises `schema_version` inside the file, never the name.
- **Version:** schema `indy_handoff`, `schema_version` 1.0. Read `schema` and `schema_version` first.
  1.x only adds optional meaning; 2.0 would be agreed between the two threads.
- **Newest wins:** Vera never overwrites, so a re-run is `indy_handoff__v2.json`, then `__v3`. Read the
  newest. The file says so in `how_to_read`.
- **Validated:** Indy checks the file against `indy/handoff.schema.json` (strict JSON Schema 2020-12)
  before uploading, and fails the job rather than store an invalid one.
- **Contents:** run time, final verdict and checklist verdict, checklist results, the exact documents
  considered (Vera `doc_id`, filename, category, role) and any not read, the findings, the suggested
  project summary, the methodology suggestion (a suggestion only), the model's inferred follow-ups, and
  any failed model stages.
- **Findings:** each has a stable id (same problem in the same words keeps its id across re-runs),
  category, severity, basis (stated or inferred), a quote checked against the source document, the
  section, why it matters, a clarifying question, who should answer (customer, sales, delivery), and a
  suggested destination (`starting_risk`, `starting_issue`, `open_question`). Findings whose quote
  cannot be found are never written.
- **Out of scope on purpose:** Indy flags a missing or inconsistent timeline statement as a finding. It
  does not build or analyse a schedule.

## PLATFORM ASK: Project Initiation reading Indy's opportunity-level outputs

- **Need:** grant Project Initiation `can_read_outputs_of: [indy]`, and confirm that
  `GET /v1/projects/{pid}/documents?include_outputs=true` includes the opportunity-level outputs under
  `{oid}/_opportunity/outputs/indy/`, with `source = agent:indy`.
- **Why:** the handoff is written before a project exists, and Project Initiation runs after Michael
  promotes the opportunity. If the project listing does not reach the opportunity folder, the handoff
  is invisible to it.
- **Smallest change:** none if the project listing already includes the opportunity's outputs.
  Otherwise add them, or let Project Initiation use the opportunity-level route for its own
  opportunity.

## Wiring note

The Indy image now needs `jsonschema` (in `requirements.txt`), so rebuild before starting. Start, not
Restart.

## For platform.md

Indy is 0.2.0, with the scope-risk review and handoff file added. Indy reads Scoper's `sow_draft`
output by filename prefix, so a rename in Scoper would break the draft comparison.
