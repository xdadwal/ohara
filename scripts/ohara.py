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
    parser = argparse.ArgumentParser(description='Ohara maintenance commands')
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('check', help='validate stack configuration')
    check.add_argument('--static', action='store_true')
    sub.add_parser('up', help='start local applications')
    sub.add_parser('status', help='container and HTTP health')
    doctor = sub.add_parser('doctor', help='read-only host and stack diagnostics')
    doctor.add_argument('--json', action='store_true', help='machine-readable check results')
    tools = sub.add_parser('tools', help='optional tmux and bpytop packages')
    mode = tools.add_mutually_exclusive_group()
    mode.add_argument('--install', action='store_true', help='explicitly install missing packages')
    mode.add_argument('--dry-run', action='store_true', help='show availability without changes (default)')
    args = parser.parse_args()
    if args.command in ('doctor', 'tools'):
        import maintainer
        return (maintainer.doctor(ROOT, args.json) if args.command == 'doctor'
                else maintainer.terminal_tools(args.install))
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
