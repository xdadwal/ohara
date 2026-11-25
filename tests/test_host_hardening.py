from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class HostHardeningTests(unittest.TestCase):
    def test_ssh_template_only_disables_password_methods(self):
        text = (ROOT / 'configs/ssh/90-ohara-keys-only.conf').read_text()
        directives = [
            line.split()
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith('#')
        ]
        self.assertEqual(
            directives, [['PasswordAuthentication', 'no'], ['KbdInteractiveAuthentication', 'no']]
        )
        # The template must never weaken key login or touch unrelated policy.
        for forbidden in (
            'PubkeyAuthentication',
            'PermitRootLogin',
            'AuthorizedKeysFile',
            'Match',
            'AllowUsers',
        ):
            self.assertNotIn(forbidden, text)

    def test_guides_document_install_verification_and_rollback(self):
        guide = (ROOT / 'docs/agent-setup.md').read_text()
        self.assertIn('## Optional host hardening', guide)
        self.assertIn(
            'sudo install -m 644 -o root -g root configs/ssh/90-ohara-keys-only.conf '
            '/etc/ssh/sshd_config.d/90-ohara-keys-only.conf',
            guide,
        )
        self.assertIn('sudo sshd -t && sudo systemctl reload ssh', guide)
        self.assertIn(
            'sudo rm /etc/ssh/sshd_config.d/90-ohara-keys-only.conf && sudo systemctl reload ssh',
            guide,
        )
        self.assertIn(
            'sudo systemctl disable --now smbd.service nmbd.service winbind.service', guide
        )
        self.assertIn('sudo systemctl mask --now avahi-daemon.socket avahi-daemon.service', guide)
        agents = (ROOT / 'AGENTS.md').read_text()
        self.assertIn('configs/ssh/90-ohara-keys-only.conf', agents)
        self.assertIn('Optional host hardening', agents)


if __name__ == '__main__':
    unittest.main()
