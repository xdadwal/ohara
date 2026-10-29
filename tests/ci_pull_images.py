#!/usr/bin/env python3
"""Prepare public digest-pinned test images without reading deployment credentials."""
import argparse
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/lib'))
import config
import immich
import maintainerr
import bambuddy


def retry(command,timeout,*,attempts=3):
    # Only daemon readiness and idempotent image pulls retry, never smoke assertions.
    # Commands contain public image references only. Keep registry/daemon errors
    # visible here instead of weakening production's secret-safe subprocess wrapper.
    for attempt in range(attempts):
        try:
            result=subprocess.run(command,timeout=timeout,check=False)
            if result.returncode==0:return
        except subprocess.TimeoutExpired:
            print('Docker preparation command timed out.',flush=True)
        if attempt+1<attempts:
            print('Retrying Docker preparation ('+str(attempt+2)+'/'+str(attempts)+').',flush=True)
            time.sleep(5*(attempt+1))
    raise RuntimeError('Docker preparation failed after bounded retries; inspect daemon/registry errors above')


def image_list(target):
    if target=='bambuddy':return list(bambuddy.images(ROOT).values())
    if target=='immich':return list(immich.images(ROOT).values())
    from smoke import NGINX
    return list(dict.fromkeys([*config.images(ROOT/'versions.env').values(),*maintainerr.images(ROOT).values(),NGINX]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target',choices=['main','immich','bambuddy'])
    args=parser.parse_args()
    images=image_list(args.target)  # Validate public pins before any Docker command.
    retry(['docker','info','--format','{{.ServerVersion}}'],30)
    for image in images:
        print('Pulling '+image,flush=True)
        retry(['docker','pull','--quiet',image],120)


if __name__=='__main__':
    try:main()
    except (ValueError,OSError,RuntimeError) as error:
        print('CI Docker preparation: '+str(error),file=sys.stderr);sys.exit(1)
