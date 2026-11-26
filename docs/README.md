# Guide index

Rules for every change are in [AGENTS.md](../AGENTS.md); the project overview is
the root [README](../README.md). Commands are listed in
[scripts/README.md](../scripts/README.md), config files in
[configs/README.md](../configs/README.md) and tests in
[tests/README.md](../tests/README.md).

## Set up and run

| Guide | Read it to |
|---|---|
| [agent-setup](agent-setup.md) | Set up a new host with an agent: what to inspect, what to ask the owner, optional host policies (SSH keys, lid, unused services) |
| [operations](operations.md) | Run the host day to day: preparation, checks, startup, public DNS and HTTPS, backups, upgrades, migrations |
| [replication](replication.md) | Reproduce this deployment on another machine, or move the existing server |
| [credentials](credentials.md) | Fill and validate the private `.env`; which values are setup-only |
| [deployment-layout](deployment-layout.md) | Find Compose files, image pins and overlays |
| [adding-services](adding-services.md) | Add a new service end to end |

## What is deployed

| Guide | Read it to |
|---|---|
| [stack](stack.md) | See every component, its port and hostname |
| [network](network.md) | Understand this host's routers, addresses, DNS path and the OpenWrt device |
| [decisions](decisions.md) | Learn why the deployment looks the way it does |

## One guide per service

| Area | Guides |
|---|---|
| Main stack | [media](media.md) (Seerr, Jellyfin, Arr applications, qBittorrent, Navidrome, Bazarr), [homepage-widgets](homepage-widgets.md), [storage-pool](storage-pool.md) |
| Jellyfin add-ons | [jellyfin-theme](jellyfin-theme.md), [jellyfin-enhanced](jellyfin-enhanced.md), [jellyfin-letterboxd](jellyfin-letterboxd.md) |
| LAN access | [lan-services](lan-services.md), [adguard](adguard.md), [tailscale](tailscale.md) |
| Photos | [immich](immich.md), [immich-google-oauth](immich-google-oauth.md), [immich-next](immich-next.md) (this host's status and follow-up work) |
| 3D printing | [bambuddy](bambuddy.md), [orcaslicer](orcaslicer.md) |
| Notifications | [ntfy](ntfy.md), [alerts](alerts.md) |
| Maintenance | [maintainerr](maintainerr.md) |

## Records

History, kept for evidence. They describe what was true on their date and are
not instructions; when a record and a guide disagree, the guide is current.

- [verification](verification.md): dated log of what was checked on the real host and in CI. Append new entries at the end.
- [storage-incident-2026-10-31](storage-incident-2026-10-31.md): one investigated outage.
- [superpowers/plans](superpowers/plans/): approved implementation plans.

## Where each topic lives

State a fact once, in its home, and link to it from elsewhere. A short summary
with a link is fine; a second full explanation drifts.

| Topic | Home |
|---|---|
| Rules for agents, owner decisions that restrict changes | [AGENTS.md](../AGENTS.md) |
| Components, ports, hostnames | [stack](stack.md) |
| Supported systems, host preparation, public DNS, TLS, backups | [operations](operations.md) |
| Private inputs and their validation | [credentials](credentials.md) |
| Media setup, storage, seeding and quality policy | [media](media.md) |
| Storage pool and watchdog | [storage-pool](storage-pool.md) |
| Homepage cards, widgets and their keys | [homepage-widgets](homepage-widgets.md) |
| This host's network and DNS | [network](network.md); the bundled AdGuard project is in [adguard](adguard.md) |
| A single optional service | Its own guide above |
| Portfolio and apex routing | [replication](replication.md) |
| How to verify a change | [AGENTS.md](../AGENTS.md) and [tests/README.md](../tests/README.md) |

## Writing a guide

Use this section order, skipping what does not apply. Older guides predate it;
follow it when adding or reworking one.

1. **Overview**: what it is, what it never does, the command that operates it.
2. **Inputs**: settings and private values, and what to ask the owner.
3. **Setup**: exact commands for a fresh installation.
4. **Existing installations**: reruns, upgrades, migration.
5. **Verification**: what to check and what a passing check does not prove.
6. **Persistence and backup**: where state lives.
7. **Rollback**.
8. **This host**: dated status and decisions for xdadwal.in.
9. **References**: upstream links, last.

Style:

- Commands go in fenced `sh` blocks, with `sudo` shown where it is required.
  Put script names, paths and setting names in backticks.
- Dates are ISO (`2026-11-25`). Say "the owner" for the person who runs the server.
- Write placeholders in capitals (`DOMAIN`, `HOST_LAN_IP`). When a value belongs
  to this host only (`xdadwal.in`, `192.168.1.101`, a disk UUID), say so.
- Link with relative Markdown links. Do not rename a guide or heading that a
  script message or another guide links to without updating both.
