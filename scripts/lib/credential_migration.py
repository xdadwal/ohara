"""One-time, backed-up consolidation of legacy inputs; never rotates values."""
import datetime
import os
from pathlib import Path
import shutil
import tempfile

import config
import credentials


def migrate(root, backup=None):
    root = Path(root)
    if backup is not None:
        candidate = Path(backup).resolve()
        if candidate == root.resolve() or root.resolve() in candidate.parents:
            raise ValueError('Credential backup directory must be outside the checkout')
    path = root/'.env'
    config.load(path)
    existing = credentials.read(path, set(), credentials.ALL_KEYS, config.KEYS)
    legacy = [root/'local/homepage.env', root/'local/media-credentials']
    if not any(p.exists() or p.is_symlink() for p in legacy):
        credentials.load(root)
        return None
    hp = credentials.read(legacy[0], credentials.HOMEPAGE_KEYS, credentials.WIDGET_KEYS)
    media = credentials.read(legacy[1], credentials.MEDIA_KEYS)
    values = {**hp, **media}
    if any(key in existing and existing[key] != value for key, value in values.items()):
        raise ValueError('Conflicting .env and legacy credentials; reconcile privately before migration')
    text = path.read_text().rstrip('\n')+'\n\n# Consolidated application credentials (literal values).\n'
    text += ''.join(key+'='+value+'\n' for key,value in sorted(values.items()) if key not in existing)
    state = path.stat()
    descriptor, temporary = tempfile.mkstemp(dir=root, prefix='.env-migrate-')
    try:
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        credentials.read(temporary, credentials.HOMEPAGE_KEYS | credentials.MEDIA_KEYS,
                         credentials.WIDGET_KEYS, config.KEYS)
        config.load(temporary)
        backup = Path(backup) if backup else root.parent/'ohara-backups'/(
            'credentials-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
        if any(p.is_symlink() for p in [backup, *backup.parents]):
            raise ValueError('Symlink credential backup directories are unsupported')
        # Never reuse a backup directory or overwrite previous recovery material.
        backup.mkdir(mode=0o700, parents=True, exist_ok=False)
        for source, name in [(path, 'deployment.env'), (legacy[0], 'homepage.env'),
                             (legacy[1], 'media-credentials')]:
            target = backup/name
            shutil.copy2(source, target)
            target.chmod(0o600)
        if os.geteuid() == 0:
            os.chown(temporary, state.st_uid, state.st_gid)
        os.replace(temporary, path)
        credentials.load(root)
        for source in legacy:
            source.unlink()
        return backup
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
