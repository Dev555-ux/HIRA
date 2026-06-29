# Learning Note 02 — CI & Testing (S1-02)

Date: 2026-06-29

## Concepts covered

- **CI (Continuous Integration)**: automatically run checks on every push so problems are caught early.
- **GitHub Actions**: GitHub's built-in CI; jobs defined in YAML under `.github/workflows/`, run on fresh VMs.
- **YAML**: whitespace-sensitive config format; indentation must be consistent (spaces).
- **Linter (`ruff`)**: flags style/quality issues (e.g. unused imports = `F401`) without running the code; exits non-zero on problems so CI can block.
- **Formatter (`ruff format --check`)**: verifies consistent code style.
- **Tests (`pytest`)**: code that verifies code. Test functions start with `test_` and use `assert`.
- **FastAPI `TestClient`**: calls endpoints in-memory (no running server) for fast tests.
- **Optional dependency groups** (`[project.optional-dependencies] dev`): separate build/test tools from runtime deps; installed with `pip install -e ".[dev]"`.

## Why a real test matters
A green CI checkmark only means something if it tests real behaviour. Our `/health` test asserts both the status code (200) and the body (`{"status":"ok"}`) — so the check proves the endpoint actually works, not just that the code is tidy.

## Beginner mistakes avoided
- YAML indentation errors → kept nesting consistent.
- "CI that tests nothing" → added a behaviour test, not just a linter.
- Version drift → CI Python pinned to 3.14 to match local.
- Polluting `main` to test the failure path → proved ruff rejects bad code locally instead.

## Known minor follow-ups
- GitHub actions still target Node 20 (deprecation annotation) — bump versions later.
- `httpx`/`httpx2` deprecation warning from bleeding-edge starlette — cosmetic for now.

Related: [[01-git-and-project-scaffolding]], `roadmap/SPRINT_1.md` (S1-02), CLAUDE.md Definition of Done (§16).
