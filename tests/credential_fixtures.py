"""Fixed dummy inputs for disposable tests only. Never used by deployment commands."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts/lib'))
import credentials


def write(root):
    local = root/'local'
    local.mkdir(mode=0o700, exist_ok=True)
    files = [('.env', credentials.HOMEPAGE_KEYS | credentials.MEDIA_KEYS)]
    for name, keys in files:
        text = ''
        for index, key in enumerate(sorted(keys)):
            value = ('true' if key == 'HOMEPAGE_AUTH_ENABLED' else
                     f'{index+1:032x}' if key.endswith('_API_KEY') else
                     'Disposable test only '+key+' $ # = !')
            text += key+'='+value+'\n'
        path = root/name
        existing = path.read_text() if path.exists() else ''
        path.write_text(existing + '\n' + text)
        path.chmod(0o600)
