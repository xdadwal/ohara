#!/usr/bin/env python3
"""Optional LAN DNS lifecycle; never changes router, host or client DNS."""
import argparse
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import adguard
import config

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['check', 'up', 'status', 'stop'])
    args = parser.parse_args()
    c = config.load(ROOT/'.env')
    adguard.settings(c)
    if args.command == 'up':
        adguard.prepare(c, ROOT)
        adguard.compose(c, ROOT, ['up', '-d'], timeout=300)
        print('AdGuard started; run scripts/adguard status before configuring any clients.')
    elif args.command == 'check':
        adguard.check(c, ROOT)
    elif args.command == 'stop':
        adguard.compose(c, ROOT, ['stop'])
        print('DNS stopped; existing data preserved. Revert DHCP/client DNS first if in use.')
    else:
        return adguard.status(c, ROOT)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f'Ohara DNS: {error}', file=sys.stderr)
        sys.exit(1)
