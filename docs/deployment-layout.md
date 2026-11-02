# Deployment file layout

Versioned deployment files are grouped by purpose. Private `.env` stays at the
repository root, `configs/` keeps application/host templates, and `local/` stays
ignored/private. The scripts resolve their repository root themselves.

| Project | Compose definition | Public image pins | Lifecycle helper |
|---|---|---|---|
| Eleven-app main stack | `compose/stack.yaml` | `versions/stack.env` | `scripts/check`, `scripts/up`, `scripts/status` |
| LAN DNS | `compose/adguard.yaml` | `versions/adguard.env` | `scripts/adguard` |
| Photos | `compose/immich.yaml` | `versions/immich.env` | `scripts/immich` |
| Headless slicing | `compose/orcaslicer.yaml` | `versions/orcaslicer.env` | `scripts/orcaslicer` |
| Printer management | `compose/bambuddy.yaml` | `versions/bambuddy.env` | `scripts/bambuddy` |
| Media maintenance | `compose/maintainerr.yaml` | `versions/maintainerr.env` | `scripts/maintainerr` |
| Notifications | `compose/ntfy.yaml` | `versions/ntfy.env` | `scripts/ntfy` |
| Short links | `compose/kutt.yaml` | `versions/kutt.env` | `scripts/kutt` |

Reusable main-stack overrides live in `compose/overrides/media-pool.yaml` and
`compose/overrides/jellyfin-theme.yaml`. Their helpers include them only when the
existing media-pool/theme policy enables them. They do not define standalone
projects or require separate pin manifests.

Image tags/digests and all seven normalized project models were preserved by the
move. AdGuard's existing pin was moved out of the main manifest into its own
manifest; it was not upgraded. There is one canonical copy of each pin. No
production container, application directory, volume, account, private input,
network, port or host service needs to move or restart for this layout change.
Historical private Kutt backup archives retain the filename `versions.kutt.env`
inside each backup for compatibility; that is not an active deployment manifest.

## Fresh setup

Follow [agent setup](agent-setup.md), [operations](operations.md) and the selected
service guides. Inspect the actual machine, filesystems, DNS/TLS, accounts and
private inputs before provisioning. The support prerequisites and privileged
commands are unchanged. Keep `.env` mode 0600 and never source it, hand it to
Compose, print resolved configuration or create duplicate pin files.

```sh
scripts/setup --help
scripts/check --static
scripts/immich check --static
scripts/bambuddy check --static
scripts/ntfy check --static
scripts/kutt check --static
```

`--static` is inspection, not preparation/deployment or proof of host/Internet
readiness. Do not run `up` merely to validate a repository-only refactor. Optional
projects still require their documented independent prepare/up/onboarding steps.
The helper commands and service-specific owner inputs remain the entry points.
AdGuard and Maintainerr retain their existing CLI/validation behavior; their
unit/disposable smoke tests cover their moved files independently.

Every helper passes `--project-directory` pointing to the repository root and an
explicit absolute `-f` path. This is essential after nesting YAML: relative bind
paths still resolve from the original project root, and project/network/container
identities remain stable. Helpers continue using `--env-file /dev/null` and
narrow validated interpolation environments, not the private dotenv. Do not use
plain `docker compose up` from the root or the new folders as a replacement.

## Existing checkouts and installed state

Merge/pull this change on a clean checkout, then use the same helper commands.
No privileged live application is required just for these file moves. Do not
relocate data or recreate containers to make labels display new filenames.
Docker labels may retain the file path used at container creation; explicit
helper calls use the new files with the same project name. A later deliberately
authorized normal recreation can refresh that metadata.

External operator scripts, if any, must update their hardcoded paths using this
mapping; prefer the stable helpers instead. The repository, CI and test fixtures
are updated. Out-of-repository cron jobs or scripts are not implicitly audited
or modified by this change.

| Previous root file | New canonical file |
|---|---|
| `compose.yaml` | `compose/stack.yaml` |
| `versions.env` | `versions/stack.env` (main images only) |
| Main manifest's AdGuard pin | `versions/adguard.env` |
| `compose.SERVICE.yaml` | `compose/SERVICE.yaml` |
| `versions.SERVICE.env` | `versions/SERVICE.env` |
| `compose.media-pool.yaml` | `compose/overrides/media-pool.yaml` |
| `compose.jellyfin-theme.yaml` | `compose/overrides/jellyfin-theme.yaml` |

Installed `/etc` and `/usr/local/lib/ohara` files remain installed runtime state,
not moved repository templates. Storage-watchdog recovery continues to call the
same guarded units/helpers, which resolve the current checkout's new paths. The
standalone alert worker needs no reinstall for this source layout alone. Existing
certificates, exact Nginx baselines and private service configurations are untouched.

## Verification and rollback

```sh
python3 -m unittest discover -s tests -v
tests/test_setup.sh
tests/test_cli.sh
tests/static.sh
tests/smoke.sh
python3 tests/smoke_immich.py
python3 tests/smoke_bambuddy.py
python3 tests/smoke_kutt.py
```

The disposable tests copy the new directory structure into isolated roots and
start only their own fixture projects. Compare static models/pins before and
after a future layout change; do not log private resolved configurations. Static
checks, disposable runtimes and actual Linux provisioning are separate claims.
This reorganization is not a fresh-machine provisioning or public reachability test.

To roll back, revert the layout change as a complete reviewed Git change (or
restore its previous clean checkout), including helpers, manifests, fixture paths
and docs together. Do not move only YAML back while leaving helpers on new paths.
Keep private `.env`/`local/`, application filesystems and running services intact.
No data restore, ownership rewrite, Nginx reload or container recreation is needed
for source-layout rollback. Re-run the static checks and helper status commands
before any later deliberately authorized deployment.
