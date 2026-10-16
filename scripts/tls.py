#!/usr/bin/env python3
import argparse
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import config
import dns_tls
import host
import proxy
import runtime


def main():
    parser = argparse.ArgumentParser(description='Explicit HTTPS activation; HTTP-01 or GoDaddy DNS-01')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--staging', action='store_true', help='ACME test only, no public application routes')
    mode.add_argument('--activate', action='store_true', help='issue production certificate and enable routes')
    mode.add_argument('--configure-renewal', action='store_true', help='test and save DNS renewal for existing ohara-wildcard; preserve routes')
    parser.add_argument('--dns-provider', choices=['godaddy'], help='use DNS-01 for DOMAIN and *.DOMAIN; no public port 80 required')
    parser.add_argument('--dns-credentials', type=Path, help='private JSON file containing domain and token')
    parser.add_argument('--accounts-ready', action='store_true', help='attest local owner setup and application authentication were verified')
    parser.add_argument('--agree-tos', action='store_true', help='accept the ACME subscriber agreement')
    args = parser.parse_args()
    if bool(args.dns_provider) != bool(args.dns_credentials):
        parser.error('--dns-provider and --dns-credentials must be supplied together')
    if args.configure_renewal and not args.dns_provider:
        parser.error('--configure-renewal requires --dns-provider and --dns-credentials')
    root = Path(__file__).resolve().parents[1]
    host.require_root()
    c = config.load(root / '.env')
    if not args.configure_renewal:
        runtime.check(c, root)
    if args.activate and runtime.status(c, root):
        raise ValueError('Local services are not ready; HTTPS activation stopped')
    with proxy.lock():
        if args.dns_provider:
            dns_tls.activate(c, root, args.dns_credentials, staging=args.staging,
                             renewal_only=args.configure_renewal,
                             accounts_ready=args.accounts_ready, agree=args.agree_tos)
        else:
            proxy.activate(c, root, staging=args.staging, accounts_ready=args.accounts_ready, agree=args.agree_tos)

if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f'Ohara TLS: {error}', file=sys.stderr)
        sys.exit(1)
