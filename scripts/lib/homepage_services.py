"""Selective edits to the live Homepage services.yaml: cards and their widgets.

The file belongs to the owner once setup has seeded it. Callers read it, change
only their own card, save the previous text privately and write the result.
PyYAML is imported on use so commands still start on a host without it.
"""

from pathlib import Path

import config
import jellyfin_theme


def read(c):
    """Return (path, text, groups) for DATA_ROOT/homepage/services.yaml; refuse symlinks."""
    import yaml

    path = jellyfin_theme.safe(Path(c['DATA_ROOT']) / 'homepage/services.yaml')
    text = path.read_text()
    return path, text, yaml.safe_load(text)


def cards(groups, name):
    """Every card called NAME, in any group, as the dicts held inside `groups`."""
    return [
        entry[name]
        for group in groups
        for rows in group.values()
        for entry in rows
        if name in entry
    ]


def group(groups, name):
    """The card list of group NAME, appended as a new empty group when missing."""
    rows = next((g[name] for g in groups if name in g), None)
    if rows is None:
        rows = []
        groups.append({name: rows})
    return rows


def dump(groups):
    import yaml

    return yaml.safe_dump(groups, sort_keys=False, allow_unicode=True)


def backup(directory, text):
    """Save the previous services.yaml in a new private directory."""
    directory.mkdir(parents=True, mode=0o700)
    config.create_file(directory / 'services.yaml', text)
