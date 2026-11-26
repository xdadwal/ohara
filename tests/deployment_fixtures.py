"""Copy versioned deployment inputs into isolated test roots, preserving layout."""

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def copy_deployment(root, *names):
    for name in names:
        target = Path(root) / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / name, target)
        # compose/PROJECT.yaml may include group files from compose/PROJECT/.
        groups = (ROOT / name).with_suffix('')
        if name.startswith('compose/') and groups.is_dir():
            shutil.copytree(groups, target.with_suffix(''))
