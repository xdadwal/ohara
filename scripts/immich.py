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
    parser.add_argument('command', choices=['check', 'prepare', 'up', 'status', 'stop', 'oauth'])
    parser.add_argument('--static', action='store_true', help='check Compose without private credentials, storage or Docker daemon')
    parser.add_argument('--allow-short-db-password', action='store_true',
                        help='explicit operator exception: accept a nonempty alphanumeric DB password shorter than 16 characters')
    args = parser.parse_args()
    if args.static and args.command != 'check':
        parser.error('--static is only supported with check')
    c = config.load(ROOT / ('.env.example' if args.static else '.env'))
    if args.command == 'check':
        immich.check(c, ROOT, static=args.static, allow_short=args.allow_short_db_password)
    elif args.command == 'prepare':
        immich.prepare(c, ROOT, allow_short=args.allow_short_db_password)
    elif args.command == 'up':
        immich.up(c, ROOT, allow_short=args.allow_short_db_password)
    elif args.command == 'oauth':
        immich.configure_oauth(c, ROOT, allow_short=args.allow_short_db_password)
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
