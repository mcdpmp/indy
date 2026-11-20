# What Indy needs from Vera

Indy never edits Vera. Everything below is a request for Michael to bring to the Vera thread. Nothing
here is worked around in Indy: until it is done, Indy answers 503 or says plainly what is missing.

## Wiring (the usual checklist)

1. **Compose service** `indy` in `workers/docker-compose.yml`: build context `../../indy`, port 5112,
   `extra_hosts: host.docker.internal:host-gateway`, `VERA_URL`, `VERA_AGENT_KEY` from
   `INDY_AGENT_KEY` in `workers/.env`, and `INDY_OLLAMA_ENDPOINT=http://host.docker.internal:11434`.
   Start, not Restart, so the environment is re-read.
2. **State volume.** Bind-mount a host folder to `/app/state`. It holds the edited checklist, the latest
   run per opportunity (a cache; Vera has the report) and the audit log. Without it a rebuild resets
   the checklist to the defaults.
3. **Agent key** (`python -m vera.cli issue-key indy`).
4. **Read scopes:** `rfp`, `sow`, `other`.
5. **`can_read_outputs_of: [scoper]`** so Indy can compare Scoper's draft SOW with the signed one.
   Without it that checklist item shows "Skipped" and nothing else breaks.
6. **Grants:** `sso` (the page's sign-in) and `list_projects` (the opportunity picker; without it the
   page asks for a typed opportunity id).
7. **Tailnet** entry `/indy` on :8445, `ui_url` set in the access dialog, the Open button. Never Funnel.

## PLATFORM ASKs

PLATFORM ASK: confirm how an agent's own and other agents' outputs appear in
`GET /v1/opportunities/{oid}/documents?include_outputs=true`.
Why: Indy keeps only Scoper's outputs, recognised by `source == "agent:scoper"` (the same field
Scoper's own code relies on) and ignores every other agent's outputs. If outputs carry a different
marker, Indy would silently skip the draft comparison.
Smallest change: none if `source` is present on output rows; otherwise add it, or tell Indy which
field to read.

PLATFORM ASK: confirm the opportunity metadata fields Indy may read from `GET /v1/opportunities/{oid}`.
Why: the page and report title use `name` (falling back to `title`) and the picker also reads a nested
`projects` list from `GET /v1/opportunities`. Indy shows the opportunity id if neither name exists.
Smallest change: none if those fields exist; otherwise name the right ones.

PLATFORM ASK (optional, for later): a way to learn whether an opportunity already has a project and its
methodology, without the `list_projects` grant.
Why: Indy runs before a project exists. If one already exists, a readiness check is mostly moot and the
page should say so. Today it only knows this when `list_projects` is granted.
Smallest change: include `has_project: true|false` in the opportunity metadata.

## Decisions Indy made that Michael can reverse

- A model outage still produces the report, with a banner, because the verdict and checklist are
  computed in code. If he prefers the job to fail instead, it is a one-line change in `workflows.py`.
- A partly covered blocker (for example 5 of 10 deliverables have acceptance criteria) is a condition,
  not a stop. Below half it counts as missing (`readiness.partial_min_share` in `config.yaml`).
- The sample SOWs in Vera's `samples/` have blank signature blocks, as unsigned documents do, so Indy
  correctly calls them Not ready. The tests fill the signature block in to check the intended verdicts:
  SOW 03 Ready, SOW 06 Ready with conditions, SOW 08 Not ready.
