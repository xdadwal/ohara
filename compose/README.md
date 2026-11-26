# Compose definitions

Each project is `PROJECT.yaml`, paired with public pins in `../versions/PROJECT.env`
and operated only through its script. See
[layout, migration, verification and rollback](../docs/deployment-layout.md).

## Grouping rule

Services that call each other share a file; a service that calls nothing else has
its own.

| File | Project | Services | Why they are together |
|---|---|---|---|
| `stack/media.yaml` | `ohara` | Jellyfin, Seerr, Radarr, Sonarr, Lidarr, Bazarr, Prowlarr, qBittorrent | Seerr uses Jellyfin, Radarr and Sonarr; the Arr applications use Prowlarr and qBittorrent; Bazarr uses Radarr and Sonarr |
| `stack/navidrome.yaml` | `ohara` | Navidrome | Reads the music library; calls no service |
| `stack/homepage.yaml` | `ohara` | Homepage | Widgets read other applications, but it runs without them |
| `stack/speedtest.yaml` | `ohara` | OpenSpeedTest | Calls no service |
| `immich.yaml` | `ohara-immich` | Immich server, PostgreSQL, Redis | The server needs both |
| `adguard.yaml` | `ohara-dns` | AdGuard Home | Calls no service |
| `ntfy.yaml` | `ohara-ntfy` | ntfy | Calls no service |
| `bambuddy.yaml` | `ohara-bambuddy` | Bambuddy | Runs without the slicer |
| `orcaslicer.yaml` | `ohara-orcaslicer` | OrcaSlicer | Optional add-on on Bambuddy's network |
| `maintainerr.yaml` | `ohara-maintainerr` | Maintainerr | Optional add-on on the main stack's network |

`stack.yaml` is the main project (`ohara`, eleven applications): it only names the
project and includes the four files under `stack/`. `scripts/up` starts them
together, and they share one network and one pin file.

The optional projects stay separate from the main one even where they depend on
it (OrcaSlicer on Bambuddy, Maintainerr on the media group), because each is
installed, pinned, checked and stopped on its own.

The two files under `overrides/` are main-stack overlays that the scripts add when
the media pool or the Jellyfin theme is enabled.

## Rules

- Use the scripts. They pass the repository root as the project directory and
  only validated values; do not run Compose from this folder or load the private
  `.env`.
- Keep every `include` entry in `stack.yaml` in the `path` plus
  `env_file: /dev/null` form. Compose otherwise reads a `.env` beside the included
  file, and `project_directory` would point it at the private one.
  `tests/test_stack.py` checks this.
- Anchors (`x-defaults`, `x-linuxserver`) do not cross files. A single-service
  file writes its restart and logging settings inline.
- A new main-stack service goes into the group file of the service it calls, or
  into a new file under `stack/` plus an `include` entry.
