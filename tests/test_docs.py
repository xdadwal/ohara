"""Keep the documentation navigable: links resolve and the indexes are complete."""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN = [
    path
    for path in ROOT.rglob('*.md')
    if not {'.git', '.venv', 'local', 'node_modules'} & set(path.relative_to(ROOT).parts)
]


def anchors(text):
    """GitHub-style heading anchors of a Markdown document."""
    return {
        re.sub(r'[^\w\- ]', '', heading.strip().lower()).replace(' ', '-')
        for heading in re.findall(r'^#{1,6}\s+(.*)$', text, re.M)
    }


class DocumentationTests(unittest.TestCase):
    def test_relative_links_and_anchors_resolve(self):
        broken = []
        for source in MARKDOWN:
            for target in re.findall(r'\[[^\]]*\]\(([^)\s]+)\)', source.read_text()):
                if re.match(r'https?://|mailto:', target):
                    continue
                path, _, fragment = target.partition('#')
                destination = (source.parent / path).resolve() if path else source
                if not destination.exists():
                    broken.append(f'{source.relative_to(ROOT)}: {target} (missing file)')
                elif (
                    fragment
                    and destination.suffix == '.md'
                    and fragment not in anchors(destination.read_text())
                ):
                    broken.append(f'{source.relative_to(ROOT)}: {target} (missing heading)')
        self.assertEqual(broken, [])

    def test_every_guide_is_in_the_index(self):
        index = (ROOT / 'docs/README.md').read_text()
        linked = set(re.findall(r'\]\(([a-z0-9-]+\.md)\)', index))
        guides = {path.name for path in (ROOT / 'docs').glob('*.md')} - {'README.md'}
        self.assertEqual(guides - linked, set())

    def test_every_command_is_in_the_scripts_readme(self):
        readme = (ROOT / 'scripts/README.md').read_text()
        listed = set(re.findall(r'`([a-z][a-z-]*)`', readme))
        commands = {path.name for path in (ROOT / 'scripts').iterdir() if path.is_file()}
        self.assertEqual(commands - listed - {'README.md'}, set())


if __name__ == '__main__':
    unittest.main()
