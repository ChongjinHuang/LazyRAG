"""Regression checks for the distributed diagram skill's style selection."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

PAYLOAD = Path(__file__).resolve().parents[2] / 'skills/patches/diagram-design/publish-chat-output-v1/files'
SPEC = importlib.util.spec_from_file_location('diagram_resolve_style', PAYLOAD / 'scripts/resolve_style.py')
style = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(style)


class DiagramStyleResolutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / 'project'
        self.project.mkdir()
        self.home = self.root / 'home'
        self.library = self.home / '.diagram-design/profiles'
        self.library.mkdir(parents=True)
        self.skill = self.root / 'skill'
        (self.skill / 'references').mkdir(parents=True)
        self.defaults = (PAYLOAD / 'references/style-defaults.md').read_text()
        for name in ('style-guide.md', 'style-defaults.md'):
            (self.skill / 'references' / name).write_text(self.defaults)
        mock = patch.object(style.Path, 'home', return_value=self.home)
        mock.start()
        self.addCleanup(mock.stop)

    def resolve(self):
        return style.resolve(str(self.project), self.skill)[0]

    def marker(self, content):
        (self.project / '.diagram-design').write_text(content)

    def test_no_marker_uses_working_defaults_without_creating_library_files(self):
        result = self.resolve()
        self.assertEqual(result['profile'], 'default')
        self.assertFalse(result['marker_found'])
        self.assertIn('focal', result['node_treatments'])
        self.assertEqual(list(self.library.iterdir()), [])

    def test_named_marker_uses_custom_profile_without_mutating_working_or_profile(self):
        custom = self.defaults.replace('#eb6c36', '#167d8d')
        profile = self.library / 'acme.md'
        profile.write_text(custom)
        self.marker('profile: acme\n')
        for _ in range(2):
            result = self.resolve()
            self.assertEqual(result['profile'], 'acme')
            self.assertIn('#167d8d', result['semantic_roles']['accent'][1])
        self.assertEqual(profile.read_text(), custom)
        self.assertEqual((self.skill / 'references/style-guide.md').read_text(), self.defaults)

    def test_hostile_marker_is_ignored_with_visible_warning(self):
        self.marker('profile: ../../secret\nprint("execute")\n')
        result = self.resolve()
        self.assertEqual(result['profile'], 'default')
        self.assertTrue(result['warnings'])

    def test_missing_named_profile_does_not_silently_fall_back(self):
        self.marker('profile: missing\n')
        with self.assertRaisesRegex(style.StyleError, 'missing'):
            self.resolve()

    def test_default_marker_uses_pristine_package_when_snapshot_absent(self):
        (self.skill / 'references/style-guide.md').write_text(self.defaults.replace('#eb6c36', '#167d8d'))
        self.marker('profile: default\n')
        result = self.resolve()
        self.assertIn('#eb6c36', result['semantic_roles']['accent'][1])
        self.assertFalse((self.library / 'default.md').exists())

    def test_old_profile_backfills_only_in_memory(self):
        old = '\n'.join(line for line in self.defaults.splitlines() if not line.startswith('| `link`'))
        profile = self.library / 'old.md'
        profile.write_text(old)
        self.marker('profile: old\n')
        result = self.resolve()
        self.assertIn('link', result['semantic_roles'])
        self.assertTrue(result['warnings'])
        self.assertEqual(profile.read_text(), old)

    def test_malformed_profile_requires_user_resolution(self):
        (self.library / 'broken.md').write_text('# No token tables\n')
        self.marker('profile: broken\n')
        with self.assertRaisesRegex(style.StyleError, 'malformed'):
            self.resolve()

    def test_profile_symlink_cannot_escape_library(self):
        outside = self.root / 'outside.md'
        outside.write_text(self.defaults)
        (self.library / 'escape.md').symlink_to(outside)
        self.marker('profile: escape\n')
        with self.assertRaisesRegex(style.StyleError, 'outside'):
            self.resolve()



class DiagramPreparationTests(unittest.TestCase):
    def setUp(self):
        import sys, types
        from unittest.mock import Mock
        self.verify = Mock(return_value=[])
        dependency = types.SimpleNamespace(verify=self.verify)
        with patch.dict(sys.modules, {'self_check': dependency}):
            spec = importlib.util.spec_from_file_location('diagram_prepare_html', PAYLOAD / 'scripts/prepare_html.py')
            self.helper = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.helper)

    def test_validated_bytes_are_written_atomically(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'flow.html'
            checked = []
            def verify(path):
                checked.append(path.read_text())
                return []
            self.helper.verify = verify
            result = self.helper.prepare(output, '<html>candidate</html>')
            self.assertTrue(result['validated'])
            self.assertEqual(checked, ['<html>candidate</html>'])
            self.assertEqual(output.read_text(), checked[0])
            self.assertEqual(list(Path(folder).iterdir()), [output])

    def test_failed_check_does_not_create_or_replace_output(self):
        self.verify.return_value = ['missing accessible SVG']
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'flow.html'
            for existing in (False, True):
                if existing:
                    output.write_text('previous valid deliverable')
                result = self.helper.prepare(output, '<html>invalid</html>')
                self.assertEqual(result['status'], 'invalid')
                if existing:
                    self.assertEqual(output.read_text(), 'previous valid deliverable')
                else:
                    self.assertFalse(output.exists())
                self.assertEqual(len(list(Path(folder).iterdir())), int(existing))

    def test_verifier_exception_cleans_temporary_file(self):
        self.verify.side_effect = OSError('cannot read candidate')
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(OSError):
                self.helper.prepare(Path(folder) / 'flow.html', '<html>candidate</html>')
            self.assertEqual(list(Path(folder).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
