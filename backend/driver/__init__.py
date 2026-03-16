import logging
import importlib
import pkgutil
import plugins.extensibles
from driver.driver_auto_loader import driver_auto_loader, auto_driver_auto_loader


log = logging.getLogger(__name__)


def discover_extensible_plugins(package=plugins.extensibles):
    """Best-effort discover extensible plugins.

    Optional legacy plugins may depend on external repos such as `apps.monitor`.
    Missing optional dependencies must not block Django startup or test execution.
    """
    discovered = {}
    for finder, name, ispkg in pkgutil.iter_modules(
        package.__path__, package.__name__ + "."
    ):
        try:
            discovered[name] = importlib.import_module(name)
        except ModuleNotFoundError as exc:
            log.warning("skip optional plugin %s due to missing dependency: %s", name, exc)
        except Exception as exc:
            log.warning("skip optional plugin %s due to import error: %s", name, exc)
    return discovered

driver_map = driver_auto_loader()
auto_driver_map = auto_driver_auto_loader()

discovered_plugins = discover_extensible_plugins()

"""
from driver import discovered_plugins
def caller(args, func):
    func(args)
caller(('abc'), eval("discovered_plugins['plugins.extensibles.xunmi'].reader_SG"))
"""

__all__ = ['driver_map', 'auto_driver_map', 'discovered_plugins', 'discover_extensible_plugins']
