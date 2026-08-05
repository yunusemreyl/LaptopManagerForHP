import ast
import os
import re
import unittest
import xml.etree.ElementTree as ET


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ICON_UTILS = os.path.join(REPO_ROOT, "src", "gui", "icon_utils.py")
ICON_DIR = os.path.join(
    REPO_ROOT, "data", "icons", "hicolor", "scalable", "actions"
)


def _literal_assignment(tree, name):
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                value = node.value
                if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "frozenset":
                    value = value.args[0]
                return ast.literal_eval(value)
    raise AssertionError(f"Missing literal assignment: {name}")


class BundledIconTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(ICON_UTILS, encoding="utf-8") as handle:
            cls.icon_utils_source = handle.read()
        tree = ast.parse(cls.icon_utils_source)
        cls.icon_keys = set(_literal_assignment(tree, "ICON_KEYS"))
        cls.aliases = dict(_literal_assignment(tree, "ICON_ALIASES"))

    def test_every_manifest_icon_is_a_valid_24px_symbolic_svg(self):
        for key in sorted(self.icon_keys):
            path = os.path.join(ICON_DIR, f"omenctl-{key}-symbolic.svg")
            with self.subTest(key=key):
                self.assertTrue(os.path.isfile(path), path)
                root = ET.parse(path).getroot()
                self.assertTrue(root.tag.endswith("svg"))
                self.assertEqual(root.attrib.get("viewBox"), "0 0 24 24")

    def test_aliases_resolve_to_bundled_icons(self):
        for alias, target in self.aliases.items():
            with self.subTest(alias=alias):
                self.assertIn(target, self.icon_keys)

    def test_literal_icon_calls_resolve_to_bundled_icons(self):
        call_pattern = re.compile(
            r"(?<![A-Za-z0-9_])(?:make_icon|icon_name)\(\s*[\"']([a-z_]+)[\"']"
        )
        for root, _, files in os.walk(os.path.join(REPO_ROOT, "src", "gui")):
            for filename in files:
                if not filename.endswith(".py"):
                    continue
                path = os.path.join(root, filename)
                with open(path, encoding="utf-8") as handle:
                    source = handle.read()
                for key in call_pattern.findall(source):
                    target = self.aliases.get(key, key)
                    with self.subTest(file=filename, key=key):
                        self.assertIn(target, self.icon_keys)

    def test_installers_copy_the_private_icon_theme(self):
        for relative_path in ("setup.sh", "PKGBUILD", "flake.nix"):
            path = os.path.join(REPO_ROOT, relative_path)
            with self.subTest(path=relative_path), open(path, encoding="utf-8") as handle:
                self.assertIn("data/icons", handle.read())

        with open(os.path.join(REPO_ROOT, "setup.sh"), encoding="utf-8") as handle:
            self.assertIn("src/gui/icon_utils.py", handle.read())


if __name__ == "__main__":
    unittest.main()
