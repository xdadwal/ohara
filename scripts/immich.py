#!/usr/bin/env python3
"""Operate the independent Immich project; never modifies Nginx, DNS or the media stack."""
import argparse
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import config
import immich

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['check', 'prepare', 'up', 'status', 'stop'])
    parser.add_argument('--static', action='store_true', help='check Compose without private credentials, storage or Docker daemon')
    args = parser.parse_args()
    if args.static and args.command != 'check':
        parser.error('--static is only supported with check')
    c = config.load(ROOT / ('.env.example' if args.static else '.env'))
    if args.command == 'check':
        immich.check(c, ROOT, static=args.static)
    elif args.command == 'prepare':
        immich.prepare(c, ROOT)
    elif args.command == 'up':
        immich.up(c, ROOT)
    elif args.command == 'status':
        return immich.status(c, ROOT)
    else:
        immich.compose(c, ROOT, ['stop'], static=True)
        print('Immich stopped; storage preserved.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, RuntimeError) as error:
        print(f'Immich: {error}', file=sys.stderr)
        sys.exit(1)
    except (OSError, KeyError, subprocess.TimeoutExpired):
        # Never echo subprocess output, dotenv values, or JSON containing secrets.
        print('Immich operation failed; check private inputs, mounts and local service logs. See docs/immich.md.', file=sys.stderr)
        sys.exit(1)
