from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from driver import discover_extensible_plugins


class DriverPluginDiscoveryTests(SimpleTestCase):
    @patch("driver.importlib.import_module")
    @patch("driver.pkgutil.iter_modules")
    def test_discover_extensible_plugins_skips_optional_plugin_when_dependency_missing(
        self,
        mock_iter_modules,
        mock_import_module,
    ):
        package = SimpleNamespace(
            __path__=["/fake/plugins/extensibles"],
            __name__="plugins.extensibles",
        )
        mock_iter_modules.return_value = [
            (None, "plugins.extensibles.elasticsearch", True),
            (None, "plugins.extensibles.public_net_sync", True),
        ]

        def fake_import(name):
            if name == "plugins.extensibles.public_net_sync":
                raise ModuleNotFoundError("No module named 'apps.monitor'")
            return object()

        mock_import_module.side_effect = fake_import

        discovered = discover_extensible_plugins(package=package)

        self.assertIn("plugins.extensibles.elasticsearch", discovered)
        self.assertNotIn("plugins.extensibles.public_net_sync", discovered)
