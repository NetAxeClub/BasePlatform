import importlib
import pkgutil
import plugins.extensibles
from driver.driver_auto_loader import driver_auto_loader, auto_driver_auto_loader

driver_map = driver_auto_loader()
auto_driver_map = auto_driver_auto_loader()



discovered_plugins = {
    name: importlib.import_module(name)
    for finder, name, ispkg
    in pkgutil.iter_modules(plugins.extensibles.__path__, plugins.extensibles.__name__ + ".")
}

"""
from driver import discovered_plugins
def caller(args, func):
    func(args)
caller(('abc'), eval("discovered_plugins['plugins.extensibles.xunmi'].reader_SG"))
"""

__all__ = ['driver_map', 'auto_driver_map', 'discovered_plugins']