# Indy

Indy is agent 2 of the VeraForge platform: project intake. After an SOW is signed, Indy reads the
signed SOW and the supporting material for an opportunity and answers one question: is this ready
to become a project, and if not, what is missing? It is a worker under the Vera orchestrator, on
port 5112. It never creates projects, never changes methodology, and writes only to its own
output folder through Vera. The project ID and the methodology stay Michael's decision in Vera.

## What it does

- **Readiness check.** Runs an editable checklist over the signed SOW (and supporting documents) and
  gives a verdict: Ready, Ready with conditions, or Not ready. Statuses, counts, dates, the signature
  check and the verdict are computed in code. The model never decides them.
- **Report.** One Markdown report per run, executive summary first, stored through Vera as
  `readiness_report.md` (Vera versions repeats). A Word copy can be downloaded from the page.
- **Suggested project summary.** Customer, scope, deliverables, key dates, commercial terms,
  assumptions, dependencies and named people, each marked "stated" (the model's quote was found in
  the document) or "inferred" (it was not). For Michael to confirm in Vera.
- **Scope-risk review.** Reads the SOW for ambiguity, missing acceptance criteria, hidden complexity,
  scope boundary problems, risky assumptions and commercial or timeline statements that look wrong.
  Code finds what it can and the model proposes the rest; every finding quotes the SOW and the quote
  is checked against the document, or the finding is set aside. Stated findings and inferred ones are
  kept apart, and only stated high-severity findings can move the verdict.
- **Handoff file.** `indy_handoff.json` (schema 1.0, validated) next to the report, for Project
  Initiation. See [docs/handoff_schema.md](docs/handoff_schema.md). Renaming it would break the next agent.
- **Suggested methodology.** Waterfall or scrum with reasoning, clearly a suggestion only.
- **Questions.** Ask about the documents; answers cite the passage they came from, and an answer
  that cites nothing is flagged as unverified.
- **Draft versus signed.** When Scoper's outputs are readable, amounts, dates and deliverable ids that
  changed between Scoper's draft and the signed SOW are listed.

How the verdict works: any enabled blocker that is missing or unclear gives Not ready. Otherwise any
enabled item that is not fully present gives Ready with conditions. Partly covered blockers are
conditions. Edit the checklist (on or off, blocker or warning, your own keyword items) on the page.

## Run

```
pip install -r requirements.txt
set VERA_URL=http://host.docker.internal:5100
set VERA_AGENT_KEY=vk_...
python -m indy.main serve
```

Vera runs Indy from its own compose file (build context `../../indy`), so there is no compose file
here. `config.yaml` sets the models (local Ollama, same approach as Scoper), pacing and thresholds;
no credentials live in it. What Indy needs from Vera is in [docs/vera.md](docs/vera.md).

## API

Open: `GET /health` (`status`, `agent`, `version`, `busy`), the page shell, `/static`, and the sign-in
routes. Everything else needs a Vera single sign-in session (token in localStorage key
`veraforge_sso`, sent as `X-Admin-Token` or Bearer) and answers 503 when Vera cannot be asked.

| Route | Purpose |
|---|---|
| `POST /v1/check` | start a readiness check for `{opportunity_id}`; returns a job id |
| `GET /v1/jobs`, `GET /v1/jobs/{id}` | poll jobs; nothing holds a request open |
| `GET /v1/runs/{opportunity_id}` | the latest run (checks, facts, report text) |
| `/ui/api/*` | what the page uses: opportunities, checklist, gap rules, ask, downloads (report, Word, handoff) |

## Rules it follows

- Documents only through Vera's `/v1` API with Indy's own key. If Vera is unreachable it retries with
  backoff and then says so plainly. A document Vera refuses or that cannot be read is listed as not
  read, never guessed at. Every document is untrusted input: text reaches the model fenced as data,
  and the model's answers are validated into fixed shapes in code.
- The page works under a Tailscale mount at `/indy` with or without the trailing slash and installs
  as a PWA (`<base>` set in a head script, relative URLs, manifest scope `../`).

## Develop

```
python -m pytest
python -m ruff format . && python -m ruff check .
```

Tests use three fictional sample SOWs (copied from Vera's `samples/`, with the signature block filled
in where a test needs a signed copy) and a fake Vera and fake model, so no network is needed.
