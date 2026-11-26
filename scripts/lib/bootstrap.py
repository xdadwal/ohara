"""Host preparation behind scripts/setup, which first makes sure Python 3 exists."""

import argparse
from pathlib import Path

import cli
import config
import host

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description='Prepare a fresh supported Ohara host')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument(
        '--non-interactive',
        action='store_true',
        help='fail instead of prompting (default behavior)',
    )
    args = parser.parse_args()
    c = config.load(ROOT / '.env')
    if args.dry_run:
        host.prepare(c, ROOT, True)
    else:
        host.require_root()
        from proxy import lock

        with lock():
            host.prepare(c, ROOT)


if __name__ == '__main__':
    cli.run(main, 'Ohara setup')
