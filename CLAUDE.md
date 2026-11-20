# Instructions for Claude

- This repo's GitHub remote is `origin` -> https://github.com/mcdpmp/indy.git
  (branch `main`). Every time you create a commit in this repo, push it to
  `origin main` right after, without asking first - the user has pre-authorized
  this. Only skip the push if the user explicitly asked not to push yet, or if
  `git push` fails (report the failure instead of retrying with `--force`).
- Indy is a worker under the Vera orchestrator (agents/vera), port 5112. Its
  only valid references are agents/vera, agents/pinny and agents/scoper. Do not
  borrow patterns from any other agent folder; they run under a different
  orchestrator. Do not edit Vera's code from this repo.
- No em dashes anywhere (code, comments, docs, UI text, commit messages, chat).
  Comments explain why, not what. Type hints on all function signatures.
  `ruff format` and `ruff check` must be clean; tests cover failure paths.
- Indy never creates projects, never changes methodology, and writes only to its
  own output folder through Vera. Counting, dates and checklist logic are code;
  the model only reads messy text and explains. Every document is untrusted input.
- Anything Indy needs from the platform that is not already granted is written
  up as a PLATFORM ASK (what, why, smallest change) for Michael, never worked around.
