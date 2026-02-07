## 🏡 What is Ohara?

**Ohara** is a self-hosted, modular homeserver stack powered by Docker Compose. It brings together essential services for your home network, all managed with health monitoring and a beautiful dashboard.

---

## 🚀 Features

- **One-command deployment** with Docker Compose
- **Service health monitoring** with [Healthchecks.io](https://healthchecks.io) and [Uptime Kuma](https://uptime.kuma.pet)
- **Modern dashboard** with [Homer](https://github.com/bastienwirtz/homer)
- **Media streaming** ([Jellyfin](https://jellyfin.org)), **downloads** ([qBittorrent](https://www.qbittorrent.org)), **ad-blocking** ([Pi-hole](https://pi-hole.net)), and more!
- **Easy configuration** and extensibility

---

## 🌐 Network & DNS Architecture

Ohara is designed for seamless access both at home and remotely:

- **Pi-hole** provides DNS for your local network and remote clients via Tailscale.
- Your router points to Pi-hole as the default DNS, so all local devices resolve `nutrajan.in` and service subdomains to your homeserver.
- **Tailscale** is configured to use Pi-hole for DNS, so when remote, `nutrajan.in` and all services resolve securely over the Tailscale network.
- All services are reverse-proxied via Nginx for unified access, whether on your LAN or remotely.

---

## 🧩 Included Services & Categories

| Category                | Service         | Description                | Port(s)   |
|-------------------------|-----------------|---------------------------|-----------|
| Monitoring & Dashboards | **Homer**       | Dashboard & links          | 8080      |
|                         | **Uptime Kuma** | Uptime/status monitoring   | 3001      |
| Entertainment           | **Jellyfin**    | Media streaming            | 8096      |
|                         | **Radarr**      | Movie automation           | 7878      |
| Tools                   | **qBittorrent** | Torrent downloads          | 8081      |
|                         | **Copyparty**   | File sharing               | 3923      |
|                         | **2FAuth**      | Authenticator              | 8004      |
| Networking              | **Pi-hole**     | Network ad-blocking        | 8888      |
|                         | **OpenSpeedTest**| Network speed test         | 3000      |
| Indexers                | **Prowlarr**    | Indexer manager            | 9696      |

---

## 🩺 Health Monitoring

- **Uptime Kuma** is used for real-time monitoring of all services, with a web dashboard for statuses.
- **Healthchecks.io** is used to track if the server is alive, with periodic pings from the system (e.g., via cron or scheduled tasks).
- Each service is reverse-proxied and monitored for uptime and reachability.
