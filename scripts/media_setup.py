#!/usr/bin/env python3
"""Configure local media accounts and service connections without printing secrets."""
import argparse
import fcntl
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent/'lib'))
import config
import media

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner-email', required=True, help='Real Seerr owner email; no external account is created')
    args = parser.parse_args()
    c = config.load(ROOT/'.env')
    if (ROOT/'local').is_symlink() or not (ROOT/'local').is_dir():
        raise ValueError('Run scripts/setup first; local must be a private directory')
    lockpath = ROOT/'local/media-setup.lock'
    if lockpath.is_symlink():
        raise ValueError('Symlink setup lock is unsupported')
    with lockpath.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another media setup is running') from None
        media.connect(c, ROOT, args.owner_email)

if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, RuntimeError) as error:
        print(f'Ohara: {error}', file=sys.stderr)
        sys.exit(1)
