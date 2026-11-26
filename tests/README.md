# Tests

| Run | What it covers | Needs |
|---|---|---|
| `tests/verify.sh` | Everything below except the container tests. CI's `configuration` job runs exactly this | ruff, ShellCheck, PyYAML, bcrypt |
| `tests/lint.sh` | Ruff lint and format check (`--fix` applies them); rules in `ruff.toml` | ruff |
| `python3 -m unittest discover -s tests` | `test_*.py`: library behaviour against fixtures and fakes | PyYAML, bcrypt |
| `tests/test_cli.sh` | Every command answers `--help` from any directory; first-run and argument handling | |
| `tests/static.sh` | Shell syntax and ShellCheck for the bash and POSIX `sh` scripts | ShellCheck |
| `tests/smoke.sh` | `smoke_*.py`: real containers from the pinned images, in disposable projects with dummy data | Docker |
| `python3 tests/smoke_immich.py`, `python3 tests/smoke_bambuddy.py` | The same for those two projects; CI runs them as separate jobs | Docker |

Install the pinned tools once with
`python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt`;
`tests/lint.sh` uses `.venv/bin/ruff` when it exists. `tests/ci_pull_images.py`
pulls the pinned images before the container jobs.

## Conventions

- A test file starts by putting `scripts/lib` on `sys.path`, then imports the
  module under test by bare name.
- Tests never read the real `.env` and never touch the host: they build a
  temporary root, write fixture credentials with `credential_fixtures.write(root)`
  and copy only the deployment files they need with
  `deployment_fixtures.copy_deployment(root, name)`, which also copies the group
  files a project file includes (`compose/stack/` with `compose/stack.yaml`).
- Replace network and process calls by patching the module attribute the code
  looks up at call time (`patch.object(runtime, 'run')`,
  `patch.object(media, 'Client', ...)`). Keep those names importable when
  refactoring.
- A new library function gets a unit test. A new command is picked up by
  `tests/test_cli.sh` automatically.
- These tests show that the code behaves; they do not show that a real host, DNS
  or public HTTPS works. Report those separately ([AGENTS.md](../AGENTS.md)).
