#!/usr/bin/env python3
"""Optional host client installation; never joins or reconfigures a tailnet."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import host
from runtime import run


def install(dry_run=False, system_root=Path('/')):
    identity, codename = host.os_info((system_root / 'etc/os-release').read_text())
    if not (system_root / 'run/systemd/system').is_dir():
        raise ValueError('Tailscale installation requires a running systemd Linux host')
    architecture = run(['dpkg', '--print-architecture'], capture=True).strip()
    if architecture not in ('amd64', 'arm64'):
        raise ValueError('Supported architectures: amd64 and arm64')
    if host.installed('tailscale'):
        print('Tailscale is already installed; package, service and tailnet settings preserved.')
        return
    if shutil.which('tailscale') or shutil.which('tailscaled'):
        raise ValueError('Existing non-package Tailscale installation; review manually')
    key = system_root / 'usr/share/keyrings/ohara-tailscale.gpg'
    source = system_root / 'etc/apt/sources.list.d/ohara-tailscale.list'
    expected = (f'deb [signed-by=/usr/share/keyrings/ohara-tailscale.gpg] '
                f'https://pkgs.tailscale.com/stable/{identity} {codename} main\n')
    candidates = [system_root / 'etc/apt/sources.list',
                  *source.parent.glob('*')]
    for candidate in candidates:
        if candidate == source:
            if candidate.is_symlink() or candidate.read_text() != expected:
                raise ValueError('Existing Ohara Tailscale source differs; inspect manually')
        elif candidate.is_file() and 'pkgs.tailscale.com' in candidate.read_text():
            raise ValueError('Existing Tailscale apt source; reconcile manually before installing')
    if key.is_symlink() or source.is_symlink():
        raise ValueError('Symlink Tailscale repository files are unsupported')
    if dry_run:
        print('Would install missing prerequisites, official stable Tailscale package, and enable tailscaled.')
        print('No changes made. Tailnet enrollment is a separate operator step; see docs/tailscale.md.')
        return
    host.ensure_packages(['ca-certificates', 'curl'])
    key.parent.mkdir(parents=True, exist_ok=True)
    source.parent.mkdir(parents=True, exist_ok=True)
    if not key.exists():
        # Download to a temporary file, so failed transfers cannot poison later runs.
        with tempfile.TemporaryDirectory() as temporary:
            downloaded = Path(temporary) / 'tailscale.gpg'
            run(['curl', '--fail', '--silent', '--show-error', '--max-time', '60',
                 f'https://pkgs.tailscale.com/stable/{identity}/{codename}.noarmor.gpg',
                 '-o', str(downloaded)], timeout=70)
            if not downloaded.stat().st_size:
                raise ValueError('Empty Tailscale signing key')
            # Copy atomically on the destination filesystem.
            with tempfile.NamedTemporaryFile(dir=key.parent, delete=False) as output:
                pending = Path(output.name)
                output.write(downloaded.read_bytes())
            try:
                pending.chmod(0o644)
                pending.replace(key)
            finally:
                pending.unlink(missing_ok=True)
    if not source.exists():
        source.write_text(expected)
        source.chmod(0o644)
    host.ensure_packages(['tailscale'])
    run(['systemctl', 'enable', '--now', 'tailscaled'], timeout=60)
    print('Installed Tailscale. Not enrolled; follow docs/tailscale.md to sign in privately.')


def main():
    parser = argparse.ArgumentParser(description='Optional Tailscale host client for remote OpenSSH')
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--dry-run', action='store_true', help='inspect installation without changes')
    action.add_argument('--install', action='store_true', help='install client; never authenticate or change routing')
    args = parser.parse_args()
    if not args.dry_run and os.geteuid() != 0:
        raise ValueError('Run sudo scripts/tailscale --install')
    install(args.dry_run)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f'Ohara Tailscale: {error}', file=sys.stderr)
        sys.exit(1)
