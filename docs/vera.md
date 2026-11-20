# What Indy needs from Vera, and what it hands to Project Initiation

Indy never edits Vera. Everything under "PLATFORM ASKs" is a request for Michael to bring to the Vera
thread. Nothing here is worked around in Indy: until it is done, Indy answers 503 or says plainly what
is missing.

## Handoff for Project Initiation (agent 3)

Brief for the Project Initiation thread. Indy writes two outputs per readiness check into its own
folder for the opportunity, `{opportunity}/_opportunity/outputs/indy/`:

| File | Reader | Contents |
|---|---|---|
| **`indy_handoff.json`** | Project Initiation | schema `indy_handoff`, **schema version 1.0** |
| `readiness_report.md` | Michael | the same findings in prose, executive summary first |

- **Find it by name: `indy_handoff.json`.** Renaming it, in Indy or in any Vera output rule, would
  break Project Initiation. A change of shape raises `schema_version` inside the file, never the name.
- **Newest version wins.** Vera never overwrites, so a re-run is stored as `indy_handoff__v2.json`,
  then `__v3`, and so on. Read the newest. The file says this itself in `how_to_read`.
- **Check `schema` is `indy_handoff` and read `schema_version` first.** 1.x only adds optional
  meaning; 2.0 may change fields and would be agreed between the two threads.
- **Schema:** `indy/handoff.schema.json` (JSON Schema 2020-12, strict). Field-by-field description:
  [handoff_schema.md](handoff_schema.md). Indy validates the file before uploading it and fails the job
  rather than store an invalid one.
- **What it carries:** run time; the final verdict and the checklist verdict; the checklist results; the
  exact documents considered (Vera `doc_id`, filename, category, role) and any not read; the findings;
  the suggested project summary (stated or inferred per line); the methodology suggestion (a
  suggestion only); the model's inferred follow-ups; and any model stage that failed.
- **Findings** are the gaps Project Initiation should start from. Each has a stable id (same problem,
  same words, same id across re-runs), category, severity (high, medium, low), basis (stated or
  inferred), a quote that Indy has checked against the source document, the section, why it matters, a
  clarifying question, who should answer (customer, sales, delivery) and a suggested destination
  (`starting_risk`, `starting_issue`, `open_question`). Findings whose quote could not be found are
  never written to the file.
- **Reading it:** Project Initiation needs `can_read_outputs_of: [indy]`. Indy writes at the
  opportunity level before a project exists; after Michael promotes the opportunity, Project Initiation
  reads these outputs through the project.
- **Out of scope on purpose:** Indy flags a missing or inconsistent timeline statement as a finding. It
  does not build or analyse a schedule.

## Wiring (the usual checklist)

Already done per `platform.md` (2026-11-20): compose service on 5112, state bind-mounted, key, scopes
`rfp`/`sow`/`other` plus Scoper's outputs, grants `sso` and `list_projects`, tailnet `/indy`. For
reference, what Indy relies on:

1. **Compose service** `indy`: build context `../../indy`, port 5112, `extra_hosts`, `VERA_URL`,
   `VERA_AGENT_KEY` from `INDY_AGENT_KEY`, `INDY_OLLAMA_ENDPOINT=http://host.docker.internal:11434`.
   Start, not Restart. The image now also needs `jsonschema` (in `requirements.txt`), so rebuild.
2. **State volume** on `/app/state`: the edited checklist, the edited scope-risk rules, the latest run
   per opportunity (a cache; Vera has the outputs) and the audit log.
3. **Read scopes:** `rfp`, `sow`, `other`; **`can_read_outputs_of: [scoper]`** for the draft comparison.
4. **Grants:** `sso` and `list_projects`.
5. **Tailnet** `/indy` on :8445. Never Funnel.

## PLATFORM ASKs

Settled per `platform.md`: outputs carry `source = agent:<name>`, and the opportunity metadata fields
Indy reads (`name`, nested `projects`) exist. The optional `has_project` flag is deferred until an agent
needs it without `list_projects`.

PLATFORM ASK: grant Project Initiation `can_read_outputs_of: [indy]`, and confirm its project-level
listing (`GET /v1/projects/{pid}/documents?include_outputs=true`) includes the opportunity-level outputs
under `{oid}/_opportunity/outputs/indy/`, with `source = agent:indy`.
Why: the handoff is written before a project exists, and Project Initiation runs after one does. If the
project listing does not reach the opportunity folder, the handoff is invisible to it.
Smallest change: none if the project listing already includes the opportunity's outputs; otherwise add
them, or let Project Initiation use the opportunity-level route for its own opportunity.

## Decisions Indy made that Michael can reverse

- **How findings affect the verdict** (agreed 2026-11-20): only stated findings count. A stated
  high-severity finding turns Ready into Ready with conditions; medium, low and every inferred finding
  are listed with no effect; findings never produce Not ready, which stays for missing or unusable
  documents. Set per severity in `findings.verdict_effect` in `config.yaml` (`none`, `conditions` or
  `not_ready`).
- **Severity and categories** (agreed): high, medium, low; ambiguity, acceptance, complexity,
  scope_boundary, assumptions_dependencies, commercial_timeline. The phrase rules and their severities
  are editable on the Gap rules tab.
- **Absences are stated findings.** "There is no out-of-scope list" is measured by code from the
  document structure, quoted on the nearest heading and marked `evidence_kind: absence`.
- **A model outage still produces the report and the handoff file**, with the failed stages listed in
  `model_problems`, because the verdict and the code-found findings do not depend on the model.
- **A partly covered blocker** (for example 5 of 10 deliverables have acceptance criteria) is a
  condition, not a stop. Below half it counts as missing (`readiness.partial_min_share`).
- **Sample SOWs.** Vera's `samples/` SOWs have blank signature blocks, so Indy correctly calls them Not
  ready. The tests fill the signature block in. With it signed: SOW 03 Ready, SOW 06 Ready with
  conditions, SOW 08 Not ready. By code alone, 03 has no high stated finding; 06 finds the unlimited
  revisions ("inclusive of all revisions", "until the University is satisfied"), five deliverables with
  no acceptance criteria, a subjective criterion, thin assumptions and change control; 08 finds the
  open-ended scope, the 24x7 support promise, no out-of-scope list, a price table that does not add up,
  missing change control and assumptions, and marketing language. The SAP configuration commitment and
  the SAP integration starting before its specification need the model, so they are not asserted by the
  offline tests.
