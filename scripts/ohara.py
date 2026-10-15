#!/usr/bin/env python3
"""Small command dispatcher; operational code lives in focused modules."""
import argparse
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import config
import runtime

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['check', 'up', 'status'])
    parser.add_argument('--static', action='store_true', help='check only: skip private files/storage')
    args = parser.parse_args()
    if args.static and args.command != 'check':
        parser.error('--static is only supported by check')
    c = config.load(ROOT / '.env')
    if args.command == 'check':
        runtime.check(c, ROOT, static=args.static)
    elif args.command == 'up':
        runtime.check(c, ROOT)
        runtime.compose(c, ROOT, ['up', '-d', '--wait', '--wait-timeout', '180'], timeout=900)
        print('Local stack started. Complete account setup through SSH forwarding before public activation.')
    else:
        return runtime.status(c, ROOT)
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f'Ohara: {error}', file=sys.stderr)
        sys.exit(1)
