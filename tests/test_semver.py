"""
Testes Automatizados para o Sistema de Versionamento SemVer (MAJOR.MINOR.PATCH)
"""

import unittest
from pathlib import Path

from cad.semver import SemVer
import config


class TestSemVer(unittest.TestCase):
    def test_parse_valid_semver(self):
        v = SemVer.parse("1.2.3")
        self.assertEqual(v.major, 1)
        self.assertEqual(v.minor, 2)
        self.assertEqual(v.patch, 3)
        self.assertEqual(str(v), "1.2.3")
        self.assertEqual(v.tag, "v1.2.3")
        self.assertEqual(v.tuple(), (1, 2, 3))

        # Aceita prefixo 'v'
        v2 = SemVer.parse("v2.0.0")
        self.assertEqual(v2.major, 2)
        self.assertEqual(v2.minor, 0)
        self.assertEqual(v2.patch, 0)

    def test_parse_invalid_semver_raises_value_error(self):
        invalid_versions = ["2026.3", "1.0", "1.0.0.1", "alpha", "1.2.x", "-1.0.0"]
        for inv in invalid_versions:
            with self.subTest(version=inv):
                with self.assertRaises(ValueError):
                    SemVer.parse(inv)

    def test_bump_major_resets_minor_and_patch(self):
        v = SemVer.parse("1.2.3")
        bumped = v.bump_major()
        self.assertEqual(str(bumped), "2.0.0")
        self.assertEqual(bumped.tag, "v2.0.0")

    def test_bump_minor_resets_patch(self):
        v = SemVer.parse("1.2.3")
        bumped = v.bump_minor()
        self.assertEqual(str(bumped), "1.3.0")
        self.assertEqual(bumped.tag, "v1.3.0")

    def test_bump_patch_increments_only_patch(self):
        v = SemVer.parse("1.2.3")
        bumped = v.bump_patch()
        self.assertEqual(str(bumped), "1.2.4")
        self.assertEqual(bumped.tag, "v1.2.4")

    def test_bump_by_level_string(self):
        v = SemVer.parse("1.0.0")
        self.assertEqual(str(v.bump("major")), "2.0.0")
        self.assertEqual(str(v.bump("minor")), "1.1.0")
        self.assertEqual(str(v.bump("patch")), "1.0.1")

        with self.assertRaises(ValueError):
            v.bump("invalid_level")

    def test_config_app_version_is_valid_semver(self):
        v = SemVer.parse(config.APP_VERSION)
        self.assertIsInstance(v.major, int)
        self.assertIsInstance(v.minor, int)
        self.assertIsInstance(v.patch, int)
        self.assertEqual(config.APP_VERSION, "1.0.0")


if __name__ == "__main__":
    unittest.main()
