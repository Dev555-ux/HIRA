# Learning Note 01 — Git & Project Scaffolding (S1-01)

Date: 2026-06-29

## Concepts covered

- **Git repository**: a folder where Git tracks full history via a hidden `.git/`. `git init` creates it.
- **Commit**: a saved snapshot + a message explaining *why*. History is a chain of commits.
- **Three areas**: working directory (your files) → staging area (`git add`) → repository (`git commit`).
- **`.gitignore`**: patterns Git must never track. Create it FIRST to avoid leaking secrets / committing junk.
- **Remote & GitHub**: a hosted copy; `git push` uploads, `git pull` downloads. Backup + portfolio.
- **Virtual environment (`venv`)**: a per-project isolated Python + packages, never committed (regenerable).
- **Dependency declaration (`pyproject.toml`)**: commit the *list* of needed libraries, not the libraries themselves.
- **FastAPI vs uvicorn**: uvicorn = the web server that listens for HTTP; FastAPI = the framework that decides what each request does. Separate jobs.
- **Endpoint**: a URL the server responds to. `/health` = conventional "is the server up?" check.
- **Conventional Commits**: `chore:`, `docs:`, `feat:` prefixes — an industry-standard commit message format.

## Beginner mistakes avoided

- Committing secrets / `.venv` / `node_modules` → prevented by `.gitignore` created before the first `git add`.
- One giant "initial commit" → used three small, focused commits instead.
- Force-pushing over a remote without checking what's there → surfaced the placeholder repo and got consent first.

## Real-world judgment

Found a pre-existing **public** placeholder repo when expecting none. Correct move was to stop, inspect it, and ask before changing visibility or force-pushing — not assume.

Related: [[CLAUDE.md §18 three-stage workflow]], `roadmap/SPRINT_1.md` (S1-01).
