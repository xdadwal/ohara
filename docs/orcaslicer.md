# Headless OrcaSlicer for Bambuddy

Optional `ohara-orcaslicer` project, using the upstream sidecar matched to
Bambuddy 1.2.5.7 (OrcaSlicer 2.4.2), pinned in `versions/orcaslicer.env`.
Native Linux x86-64 only. It has no desktop/web UI or account login. Bambuddy's
existing authenticated UI supplies the slicing controls. No new hostname,
Homepage card, AdGuard rewrite, proxy or public port is needed.

## Fresh setup and existing installations

First provision and onboard Bambuddy using [bambuddy.md](bambuddy.md). Discover
its real BAMBUDDY_ROOT, BAMBUDDY_MOUNT, RUN_UID and RUN_GID through the validated
private root .env; do not source it. Verify local storage and available RAM/disk.
This sidecar uses BAMBUDDY_ROOT/orcaslicer on the same verified local filesystem,
separate from SQLite and archives. Existing files and ownership are preserved.
No additional credentials are required. On this host the root is
/ohara/bambuddy/orcaslicer; never copy this identity blindly to a new host.

```sh
scripts/orcaslicer check --static
sudo scripts/orcaslicer prepare
sudo scripts/orcaslicer up
scripts/orcaslicer status
```

Bambuddy must already have created its owned `ohara-bambuddy_default` bridge.
The helper validates that bridge rather than creating a new one. The sidecar
joins it with the DNS name `orcaslicer`; no host ports are published. It runs
with the configured unprivileged UID/GID, all capabilities dropped, no-new-privileges,
a 2 GiB memory limit, two CPUs and a 256-process limit. Uploads are bounded to
128 MB; temporary files have a 512 MiB tmpfs. Complex models can exceed these
limits; review capacity before deliberately raising them. State persists in the
separate directory; the container root filesystem is writable for upstream
compatibility. No Docker socket, printer devices or other host state is mounted.

In the existing owner session at https://bambuddy.DOMAIN, open Settings → Slicer:

- Preferred Slicer: OrcaSlicer.
- Use Slicer API: enabled.
- OrcaSlicer sidecar URL: `http://orcaslicer:3000`.

Alternatively, an agent can apply exactly these three fields through native owner
login. Fill the optional BAMBUDDY_USERNAME and BAMBUDDY_PASSWORD entries in the
private root .env with the existing owner login (never in chat), then run:

```sh
scripts/orcaslicer configure
```

The helper validates private-file permissions, uses the local authenticated API,
backs up only the previous three fields in local/bambuddy-backups/*-slicer/slicer.json,
and verifies persisted values. It never creates/resets accounts or forwards
owner credentials to containers/Homepage. Missing login or MFA requirements stop
configuration; complete MFA in the UI instead. Remove these optional entries
when no longer needed. Other lifecycle commands do not require them. For rollback,
use the owner UI to restore the three values from that private backup; preserve
all other settings and accounts.

These settings persist in Bambuddy's existing database. Do not use localhost:
it refers to the Bambuddy container. The existing Homepage Read Status key cannot
change settings; never broaden it or edit the live SQLite database to bypass login.
Review printer/nozzle/filament/process profiles for the actual printer before
slicing. Advanced painting/model editing still needs desktop OrcaSlicer.
Bambu-authored/MakerWorld 3MFs may hit documented Orca CLI compatibility problems.
No Bambu cloud login or Bambu Studio sidecar is enabled.

## Upload, slice, then print

The Print upload action expects an already sliced file; enabling a sidecar does
not make it automatically slice project .3mf uploads. For an unsliced model:

1. Upload the .3mf through Bambuddy File Manager (not the Print upload action).
2. Use the file's Slice action, available in its action/menu controls.
3. Select the actual A1 mini printer, nozzle, filament and process profiles.
4. Run Slice and review the resulting .gcode.3mf and its preview/settings.
5. Use Print on that generated file only when the owner is ready to print.

If Slice opens desktop OrcaSlicer, recheck Use Slicer API. If it reports an error,
record the exact slicing message separately from Print upload rejection; Bambu-
authored projects may encounter Orca CLI compatibility issues. A healthy sidecar
alone does not prove that a particular project can be sliced. Never rename an
unsliced .3mf to .gcode.3mf as a workaround.

## Verification, upgrades and recovery

```sh
scripts/orcaslicer check
scripts/orcaslicer status
python3 -m unittest discover -s tests -v
tests/test_setup.sh
tests/test_cli.sh
tests/static.sh
tests/smoke.sh
```

Verify health from inside the actual Bambuddy container (discover its ID):

```sh
docker ps --filter label=com.docker.compose.project=ohara-bambuddy \
  --filter label=com.docker.compose.service=bambuddy --format '{{.ID}}'
# Substitute the discovered ID, not a sample container name.
docker exec CONTAINER_ID python -c 'import urllib.request; print(urllib.request.urlopen("http://orcaslicer:3000/health", timeout=10).read().decode())'
```

In the UI, slice a small owner-selected model for the actual A1 mini profile,
review the result/preview and settings. Actual slicing and printer dispatch are
separate checks: deployment must not start or queue a print. Health alone does
not prove model compatibility or successful slicing. The owner confirmed UI activation on 2026-11-03. A representative model slice
remains pending until explicitly verified.

Before upgrades, review both Bambuddy and sidecar releases, architecture and CLI
compatibility; update the matching digest in a PR, take Bambuddy's supported
backup, and stop the sidecar before copying its state to a private backup.
A same-host copy is not independent backup/restore evidence. Apply with
`sudo scripts/orcaslicer up`; no image build is required. Keep the previous pin
and stopped-state copy for rollback. Stop only this backend with
`sudo scripts/orcaslicer stop`, disable Use Slicer API in the owner UI, and retain
all data. Revert the pin and restart only the backend for an image rollback;
restore state only under explicit recovery scope. Do not stop or recreate
Bambuddy to install/remove this backend.

Sources: [upstream sidecar](https://github.com/maziggy/bambuddy/tree/v1.2.5.7/slicer-api),
[slicing guide](https://wiki.bambuddy.cool/features/slicer-api/).

## Verified on the current host

On 2026-11-01 the release-matched image was pulled and the production backend
started independently, with UID/GID 1000:1000, a 2 GiB memory limit and no host
port bindings. Health from the existing Bambuddy container reported OrcaSlicer
2.4.2 and accessible data storage. Existing Bambuddy was not recreated. The owner
confirmed UI activation on 2026-11-03; an actual model slice remains unverified. No printer operation was
performed. All 255 repository unit tests, setup/CLI/static checks and the full main-stack
disposable smoke suite passed; these do not establish
fresh Linux provisioning or public reachability of a new endpoint.
