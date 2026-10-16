#!/usr/bin/env python3
"""Configure local media accounts and service connections without printing secrets."""
import argparse
import fcntl
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent/'lib'))
import config
import media
import media_profile

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner-email', help='Real Seerr owner email; no external account is created')
    parser.add_argument('--profile', choices=['ohara'], help='explicitly enable the selected public indexers and automatic renaming')
    parser.add_argument('--profile-only', action='store_true', help='apply a profile to existing accounts; skip owner/login initialization')
    args = parser.parse_args()
    if args.profile_only and not args.profile:
        parser.error('--profile-only requires --profile')
    if not args.profile_only and not args.owner_email:
        parser.error('--owner-email is required unless --profile-only is used')
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
        if not args.profile_only:
            media.connect(c, ROOT, args.owner_email)
        if args.profile:
            media_profile.apply(ROOT)

if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, RuntimeError) as error:
        print(f'Ohara: {error}', file=sys.stderr)
        sys.exit(1)
