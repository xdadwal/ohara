#!/usr/bin/env python3
import argparse
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import config
import host


def main():
    parser = argparse.ArgumentParser(description='Prepare a fresh supported Ohara host')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--non-interactive', action='store_true', help='fail instead of prompting (default behavior)')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    host.prepare(config.load(root / '.env'), root, args.dry_run)

if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f'Ohara setup: {error}', file=sys.stderr)
        sys.exit(1)
