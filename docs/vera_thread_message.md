# Message for the Vera thread: Indy wiring and PLATFORM ASKs

From the Indy thread (agent 2, `indy`, port 5112). Indy is built and pushed
(https://github.com/mcdpmp/indy, 109 tests passing, Docker image builds, `/health` answers). It has
not run against a live Vera yet. Full detail is in `agents/indy/docs/vera.md`. Nothing below is worked
around in Indy: until it is done, guarded routes answer 503 and the page says what is missing.

## Wiring

1. Compose service `indy` in `workers/docker-compose.yml`:
   - build context `../../indy`, port 5112
   - `extra_hosts: host.docker.internal:host-gateway`
   - `VERA_URL`, and `VERA_AGENT_KEY` from `INDY_AGENT_KEY` in `workers/.env`
   - `INDY_OLLAMA_ENDPOINT=http://host.docker.internal:11434`
   - Start, not Restart.
2. Bind-mount a host folder to `/app/state` (edited checklist, latest run cache, audit log). Without it
   a rebuild resets the checklist to the defaults.
3. Issue the key: `python -m vera.cli issue-key indy`.
4. Read scopes: `rfp`, `sow`, `other`.
5. `can_read_outputs_of: [scoper]`. Without it the draft-versus-signed item shows Skipped and nothing
   else breaks.
6. Grants: `sso` (sign-in) and `list_projects` (opportunity picker; without it the page asks for a
   typed id).
7. Tailnet entry `/indy` on :8445, `ui_url` set, Open button. Not Funnel.

## PLATFORM ASK 1: how outputs appear in the document list

- **Need:** confirm that `GET /v1/opportunities/{oid}/documents?include_outputs=true` marks each output
  row with `source` such as `agent:scoper` (the field Scoper's own code relies on).
- **Why:** Indy keeps only Scoper's outputs, recognised by that field, and ignores every other agent's.
  A different marker would silently skip the draft comparison.
- **Smallest change:** none if `source` is present on output rows; otherwise add it or name the field
  to read.

## PLATFORM ASK 2: opportunity metadata fields

- **Need:** confirm Indy may read `name` (falling back to `title`) from `GET /v1/opportunities/{oid}`,
  and a nested `projects` list from `GET /v1/opportunities`.
- **Why:** the page and report titles use `name`, and the picker shows "project exists" from
  `projects`. Without them Indy shows the opportunity id.
- **Smallest change:** none if those exist; otherwise name the right fields.

## PLATFORM ASK 3 (optional, later): has-project signal

- **Need:** a way to know whether an opportunity already has a project, without the `list_projects`
  grant.
- **Why:** Indy runs before a project exists. If one exists, a check is mostly moot and the page should
  say so.
- **Smallest change:** add `has_project: true|false` to the opportunity metadata.

## For platform.md

Indy status: built, awaiting wiring. Indy reads Scoper's `sow_draft.md` output by filename prefix, so
a rename in Scoper would break the comparison.
