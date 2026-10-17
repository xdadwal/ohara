# Remote SSH with Tailscale

Tailscale is optional and runs on the Linux host, independently of Compose and
Nginx. Use ordinary OpenSSH over its private network: existing Linux accounts,
SSH keys, authorized_keys and sshd policy continue to apply. Tailscale SSH (its
separate identity-based SSH server) is disabled in the enrollment command below.
Public HTTPS, LAN routing and GoDaddy DNS continue through the existing network.
No new public hostname, router port forward or .env credential is required.

## Install on Ohara

Run the normal host bootstrap first (Python 3 is required). The optional installer
supports the same Ubuntu 24.04 / Debian 13, systemd, amd64/arm64 targets:

```sh
./scripts/tailscale --dry-run
sudo ./scripts/tailscale --install
```

It installs missing CA certificates/curl and Tailscale from the official stable
signed apt repository, then enables tailscaled. It does not execute a downloaded
installer, upgrade an already installed client, install/configure sshd, join a
network or change Tailscale preferences. Existing package installations are left
untouched; conflicting repository/custom binary installations require review.
An installed package remains managed separately from versions.env/Compose.

If sshd is absent, deliberately install the distribution openssh-server package
and verify your existing key login from the LAN before remote enrollment. Preserve
a working local/LAN session while configuring access.

## Join the tailnet

Install Tailscale on your remote laptop/phone and sign in to the same intended
tailnet. On a **new, unenrolled Ohara client**, run:

```sh
sudo tailscale up --accept-dns=false --accept-routes=false \
  --advertise-routes= --advertise-exit-node=false --exit-node= --ssh=false
```

Open the displayed login URL privately, sign in and approve the device if required.
Agents must pause for the owner's interactive login; never request login URLs,
auth keys or browser credentials in chat, invent keys, or commit Tailscale state.
There is no auth-key entry in .env. Do not run `up --reset`, logout or force
reauthentication to repair an existing remote connection.

For an **already enrolled client**, inspect its existing preferences locally
(`sudo tailscale debug prefs`; keep diagnostics private) and tailnet policy first.
Do not blindly apply the fresh-client command: an existing subnet router, exit
node, Serve/Funnel configuration or Tailscale SSH session may be in use. After
confirming those roles can be removed, apply the same flags using `tailscale set`
instead of `up`, from an independent LAN/local session. The installer never
changes existing preferences or deletes legacy containers/state.

DNS acceptance and subnet-route acceptance are disabled, no LAN routes or exit
node are advertised, and no exit node is selected. Traffic addressed to tailnet
peers uses Tailscale; ordinary internet/LAN service traffic retains existing routes.
Tailscale still manages its own interface/routes and firewall rules; this does
not mean that the host networking configuration is byte-for-byte unchanged.

## Limit access to SSH

In the Tailscale admin console, grant only the intended owner/device access to
Ohara TCP port 22 (or your existing custom SSH port). Tailscale network grants/
ACLs are separate from its SSH policy; ordinary OpenSSH needs network access and
a valid Linux SSH login. Replace any broad default allow-all rule that would also
grant access to Ohara; adding a narrow grant does not override broader grants.
Do not replace the whole tailnet policy without reviewing other devices.

Keep backend services bound to loopback. Do not add Nginx routes, Serve, Funnel,
IP forwarding, exit-node functionality, subnet routing or public SSH forwarding.
For a restrictive host firewall, inspect Tailscale's firewall interaction and
allow only the intended SSH interface/source as needed; do not disable the firewall
or assume UFW alone constrains tailnet traffic. A tailnet is not automatically
SSH-only: the network policy must enforce that restriction.

## Connect and verify

On Ohara, privately inspect `tailscale status` and obtain `tailscale ip -4`.
From a remote device connected to the tailnet:

```sh
ssh YOUR_LINUX_USER@OHARA_TAILSCALE_IP
# Private admin forwarding still works over that same SSH connection:
ssh -L 8686:127.0.0.1:8686 YOUR_LINUX_USER@OHARA_TAILSCALE_IP
```

Use the actual returned IP, not a public DNS record. MagicDNS names can also be
used if the remote client's DNS supports them; Ohara itself need not accept DNS.
Check the SSH host fingerprint against the trusted LAN connection first.

Verify key login and forwarding from outside the LAN, normal public HTTPS and
LAN access, unchanged DNS/default routing, and denial of unintended tailnet ports.
Reboot and retest service persistence. Test from a disallowed tailnet identity too.
Repository tests do not verify tailnet policy, remote SSH or real Linux installation.
Monitor device/key expiry in the admin console; handle renewal privately before
losing remote access. Protect /var/lib/tailscale as sensitive device identity state;
do not clone it onto another server or include it in public diagnostics.

To disconnect deliberately, use `sudo tailscale down` from a local/LAN session;
it ends tailnet access. Do not do this through your only remote connection.

References: [Linux installation](https://tailscale.com/docs/install/linux),
[official apt packages](https://pkgs.tailscale.com/stable/),
[CLI preferences](https://tailscale.com/docs/reference/tailscale-cli),
[access control](https://tailscale.com/kb/1018/acls),
[firewall interaction](https://tailscale.com/kb/1294/firewall-mode).
