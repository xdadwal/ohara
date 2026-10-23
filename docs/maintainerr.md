# Maintainerr

Maintainerr 3.31.0 is an optional media-maintenance service for Jellyfin, Seerr,
Radarr and Sonarr. It runs as the independent `ohara-maintainerr` Compose project
on the existing `ohara_default` network. The eleven main applications and optional
Immich/AdGuard projects retain their lifecycles. The official release image is
pinned by registry index digest in `versions.maintainerr.env`.

## Setup and access

Start the existing main stack first, then:

```sh
scripts/maintainerr prepare
scripts/maintainerr up
scripts/maintainerr connect
scripts/maintainerr artwork
scripts/maintainerr homepage
scripts/maintainerr dns
sudo scripts/lan-proxy --apply
scripts/maintainerr status
```

The proxy command applies the reviewed **existing xdadwal.in host** baseline,
backing up the previous file, validating Nginx and reloading with rollback on
failure. It is not a generic installer for other domains/certificates/subnets.
For another host, adapt and verify the proxy and certificate before activation.
The expected URL here is **https://maintainerr.xdadwal.in**, restricted to the
verified 192.168.1.0/24 LAN and loopback on HTTP and HTTPS. Public access is denied;
no public DNS change or extra router port forward is needed. AdGuard adds one
exact local rewrite; it does not change router/client DNS or other rewrites.

Maintainerr has **no built-in authentication**. Its UI/API expose stored connection
keys to anyone who can reach them. Treat LAN access as administrator access; this
is why the backend binds only 127.0.0.1:6246 and Nginx restricts its source subnet.
Its application-generated internal key is not login protection. No owner/signup
or new password is required. Remote access can use the existing ordinary SSH
forwarding workflow; do not expose this hostname publicly without separately
approved authentication. Shared authentication remains deferred.

The Homepage command adds an absent Maintainerr card to **Media administration**
(alongside Seerr and the Arr services), preserves other
cards/widgets, and saves a private pre-change snapshot. If needed, reload only
Homepage through the normal main-stack lifecycle. Verify its authenticated
`/api/services` response rather than relying on the seed file alone.

## Connections and rules

`connect` uses only existing private `.env` keys:
HOMEPAGE_VAR_JELLYFIN_API_KEY, HOMEPAGE_VAR_SEERR_API_KEY, RADARR_API_KEY and
SONARR_API_KEY. They are read literally by a host API client, never passed through
Compose/container environment or committed. Maintainerr stores connection keys in
its private SQLite state. Docker URLs are `http://jellyfin:8096`,
`http://seerr:5055`, `http://radarr:7878` and `http://sonarr:8989`.
Exactly one active Jellyfin administrator is inferred; otherwise select one
manually in Maintainerr. A different existing media server or primary connection
is rejected. Existing Arr instances, names, tags, rules and collections are
preserved. All four connection tests run before saving. Private connection
snapshots are saved under `local/maintainerr-backups/`; on partial failure, review
the UI and rerun. No destructive rollback or account reset is attempted.

**No cleanup rules or collections are created or executed by setup.** In the UI,
review Settings and the connected libraries, then choose Rules/Collections,
exclusions, a grace period and exact actions deliberately. Connecting API keys
allows Maintainerr to perform actions later selected in its UI, including deletion
through Jellyfin/Arr APIs. The absence of a media bind mount does not prevent API
deletion. Owner retention policy is separate from initial integration.
Do not change the existing qBittorrent seeding/removal policy for Maintainerr.
No download-client password or external metadata/source key is assumed.

## Storage, updates and recovery

Dedicated state is `DATA_ROOT/maintainerr` (here `/ohara/maintainerr`), mounted as
`/opt/data` with RUN_UID:RUN_GID. Prepare creates/checks only that directory;
symlinks are rejected and existing ownership/content are preserved. There is no
media-library bind mount, Docker socket, privileged container or extra database
service. Telemetry is disabled explicitly. Check the actual host filesystem and
free space before preparation; this host uses its existing root filesystem.

```sh
scripts/maintainerr check --static
scripts/maintainerr check
scripts/maintainerr stop
```

To update, review the upstream release/migrations, change the digest pin, back up
state, then run `scripts/maintainerr up`. Image updates do not change other stacks.
For a consistent backup, stop Maintainerr and copy its entire private state
outside the machine before restarting. The SQLite database (`maintainerr.sqlite`)
and connection snapshots contain plaintext service keys; keep them private and
encrypt off-host backups. Restore only with Maintainerr stopped, preserving
ownership and using a compatible application version. Independent backups and
restore tests are not established by startup or connection checks.

To roll back this addition, stop its separate project and remove only its Nginx
route, Homepage card and exact DNS rewrite after review. Retain state. No command
here deletes media, databases, Docker volumes or the network shared by the main
stack.

Validation distinguishes static/model/unit checks, disposable container/proxy/DNS
tests, actual backend/integration checks, trusted HTTPS and owner/client access.
No successful connection test proves that a cleanup rule is correct; deletion
behavior is intentionally untested against production media.

Sources: [installation](https://docs.maintainerr.info/installation/),
[configuration](https://docs.maintainerr.info/configuration/),
[security](https://docs.maintainerr.info/security/),
[reverse proxy](https://docs.maintainerr.info/reverseproxy/).

## Current host verification (2026-10-23)

The host route is deployed and matches the tracked Nginx baseline. Trusted HTTPS
returns 200 through loopback and the host LAN address; HTTP redirects to HTTPS.
A Docker-network client outside the permitted LAN receives 403 on HTTP and HTTPS,
including with forged forwarding headers. Existing six public routes retain their
expected responses. The four stored service connections, authenticated Homepage
card and exact AdGuard UDP/TCP rewrite are verified. The initial integration contained no rules or collections; the owner has since
created maintenance collections. Access from a separate physical LAN device and independent
backup/restore are not established by these checks.

## Collection covers and overlays

Run `scripts/maintainerr artwork` after connecting the media server. This explicitly
turns on global overlays and sets an hourly artwork schedule only when no schedule
exists. Existing styles, default templates and custom schedules remain intact.
It never invokes the collection handler, changes retention/actions or creates rules.
Each collection still needs its own overlay switch and eligible file-deletion
policy; metadata-only or Do Nothing actions do not get leaving-soon countdowns.

In the UI, use **Overlays → Settings → Enable overlays**, configure the schedule,
and use **Run Now** for an immediate artwork pass. Templates are under
**Overlays → Existing Templates**; choose a poster default and, for episodes, a
separate title-card default. A collection with no template override inherits the
matching default. Refresh Jellyfin clients after processing if they cache old art.
Overlays are drawn into member movie/show/episode artwork; they are not a default
cover design for the collection itself. Original artwork is preserved under
`/opt/data/overlays/originals` for supported restoration.

For a persistent collection cover, edit its rule group and use the poster picker
once the collection exists. JPEG/PNG/WebP uploads must be at most 500 KB. Maintainerr
stores the poster and pushes it to Jellyfin immediately and on collection recreation.
Do not assume it generates an automatic collage: the upstream Jellyfin adapter
expects a locked collection for native fallback artwork, while later metadata
updates can leave it unlocked. Changing metadata locks can affect descendants;
this setup does not force those locks. Custom poster upload avoids that behavior.

The owner's existing collection was repaired with a member's original poster
through Maintainerr's supported poster upload; Jellyfin confirmed a Primary image.
A recent overlay run reported 10 applied, zero errors, and a downloaded member
poster was visually verified to contain the leaving-soon countdown. The missing
hourly overlay schedule was added. Collection membership, deletion actions and
retention settings were preserved; no collection handling was triggered.

### Collections home tile

Jellyfin's My Media → Collections tile is a separate `CollectionFolder` image from
an individual `BoxSet` collection cover. If the collection itself has artwork but
the home tile is blank, refresh the **Collections library's metadata/images** with
missing images only; do not replace all images or recurse into its members.
After the first collection cover was available, a non-recursive default image/
metadata refresh generated the native home tile. All three current users' Views
responses now contain its Primary image and its image endpoint returns 200.
Refresh clients to load the new image tag. This repair does not change Maintainerr
rules, collection membership, deletion schedules or individual media artwork.
