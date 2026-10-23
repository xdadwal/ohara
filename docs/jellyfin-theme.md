# Abyss for Jellyfin

The operator selected [Abyss](https://github.com/AumGupta/abyss-jellyfin) for the
official Jellyfin container. Ohara vendors release **v1.2.3**, commit
`97f872d6e940be224d7a84cbc8a736f42fdd2edd`, under `configs/jellyfin/abyss/` with
its MIT license and SHA-256 asset manifest. The implementation follows upstream's
manual CSS, Dark-theme and Spotlight instructions, adapted to persistent Compose
mounts. It does not run the upstream interactive/root installer or modify the image.

## Install

Keep a valid Jellyfin administrator API key in the private `.env` as
`HOMEPAGE_VAR_JELLYFIN_API_KEY` (the existing Homepage widget key). The key is read
only by the local API client and is never placed in theme assets or Docker command
arguments. Setup does not reset passwords or create accounts/API keys.

```sh
scripts/jellyfin-theme prepare  # optional: files only, no branding change
scripts/jellyfin-theme install
scripts/jellyfin-theme check
```

Install validates API access, generates the overlay from the exact digest-pinned
image in versions.env, recreates only Jellyfin, and applies branding/preferences
through supported APIs. It briefly interrupts Jellyfin playback during recreation.
Open https://tv.xdadwal.in and hard-refresh the browser after installation.

The full integration includes:

- Abyss CSS served from the existing Jellyfin origin at `/web/ui/abyss.css`.
- The pinned Enhanced compatibility stylesheet follows the core import; see
  [Enhanced QoL setup](jellyfin-enhanced.md) for the installed plugin integration.
- Spotlight files served from `/web/ui/`, loaded through exactly one marked
  script in the web entry page.
- Dark client/dashboard base themes for existing users, preserving every other
  preference, including the home-section order and playback settings.
- Existing Custom CSS, logo styling, login disclaimer and splash setting kept.
  A marked CSS import is prepended so existing overrides still apply.
- Private pre-change branding and display-preference snapshots under
  `local/jellyfin-theme-backups/`. Libraries/accounts/media files are preserved.

The upstream font declarations use Google Fonts and a versioned jsDelivr icon
font. Spotlight also checks GitHub for release notices. Core theme CSS/JS/HTML
are served locally from the reviewed vendored files, with no runtime download
of a mutable `main` script. Authentication tokens are not embedded in assets.

## Persistence and upgrades

Generated files live under `DATA_ROOT/jellyfin-theme/`: the patched `index.html`,
reviewed `ui/` assets and `manifest.json` (enabled state, base-image pin and hashes).
Normal check/up/status commands retain `compose.jellyfin-theme.yaml` when enabled.
The two web mounts are read-only; image, user, port bindings and existing config,
cache and media mounts retain their configuration. Preparing files alone does not
enable the overlay on a fresh host.

An image change causes lifecycle commands to fail clearly instead of serving an
old entry page over a new web bundle. Run `scripts/jellyfin-theme install` to
rebuild against the new pin. Reinstallation updates only files matching recorded
managed hashes; manual edits are rejected for review. Put custom styling in the
Custom CSS field rather than changing vendor files. Back up generated theme state
and private snapshots with application state.

## Remove / recover

```sh
scripts/jellyfin-theme remove
```

This removes only the marked CSS block, disables the overlay and recreates only
Jellyfin. It retains theme files/backups and users' Dark preferences. Users may
select a different base theme after removal; original preference JSON is in the
private backups if needed. No libraries or media are removed.

Branding/display update failures attempt to restore changes already applied.
A failed first activation disables the overlay and recreates the prior service
configuration. Inspect private backups for a failed API rollback; do not reset
accounts or delete persistent Jellyfin state to recover styling.

## Verification scope

Unit checks cover CSS preservation/idempotence, single script injection, private
backups, unrelated preference preservation and rejection of stale/tampered
overlays. The disposable Docker smoke test applies the theme with fixture
accounts, checks served assets and retained libraries, and recreates Jellyfin
again to verify persistence. Neither this nor HTTP checks establish visual
appearance or playback on every native/mobile/TV client; upstream primarily
targets the web client. The separate Jellyfin 12 admin app may not load custom CSS.
