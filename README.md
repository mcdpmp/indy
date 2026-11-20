# Indy

Indy is agent 2 of the VeraForge platform: project intake. After an SOW is signed, Indy reads the
signed SOW and the supporting material for an opportunity and answers one question: is this ready
to become a project, and if not, what is missing? It is a worker under the Vera orchestrator, on
port 5112. It never creates projects, never changes methodology, and writes only to its own
output folder through Vera.

Status: milestones 1 and 2 (skeleton, single sign-in, jobs, and the code-only readiness engine:
checklist, signature check, detectors, verdict). The model stages, report and page follow.

## Run

```
pip install -r requirements.txt
set VERA_URL=http://host.docker.internal:5100
set VERA_AGENT_KEY=vk_...
python -m indy.main serve
```

Vera runs Indy from its own compose file (build context `../../indy`), so there is no compose
file here. `config.yaml` sets the models and pacing; no credentials live in it.

## Rules it follows

- Documents only through Vera's `/v1` API with Indy's own key. If Vera is unreachable it retries
  with backoff and then says so plainly. Every document is untrusted input.
- `GET /health` is open. The page shell, `/static` and the sign-in routes are open. Everything
  else needs Vera's single sign-in session (token in localStorage key `veraforge_sso`, sent as
  `X-Admin-Token` or Bearer) and answers 503 when Vera cannot be asked.
- Long work returns a job id; poll `GET /v1/jobs/{id}`.

## Develop

```
python -m pytest
python -m ruff format . && python -m ruff check .
```
