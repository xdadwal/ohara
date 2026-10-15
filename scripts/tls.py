#!/usr/bin/env python3
import argparse
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import config
import host
import proxy
import runtime


def main():
    parser = argparse.ArgumentParser(description='Explicit public HTTPS activation; requires root, DNS, and TCP 80 forwarding')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--staging', action='store_true', help='ACME test only, no public application routes')
    mode.add_argument('--activate', action='store_true', help='issue production certificate and enable routes')
    parser.add_argument('--accounts-ready', action='store_true', help='attest local owner setup and file authentication were verified')
    parser.add_argument('--agree-tos', action='store_true', help='accept the ACME subscriber agreement')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    host.require_root()
    c = config.load(root / '.env')
    runtime.check(c, root)
    if args.activate and runtime.status(c, root):
        raise ValueError('Local services are not ready; HTTPS activation stopped')
    with proxy.lock():
        proxy.activate(c, root, staging=args.staging, accounts_ready=args.accounts_ready, agree=args.agree_tos)

if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f'Ohara TLS: {error}', file=sys.stderr)
        sys.exit(1)
