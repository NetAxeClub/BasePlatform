import os
import importlib
from .base import register_processor, get_processor

# 自动导入当前目录下所有的处理器模块
def discover_processors():
    current_dir = os.path.dirname(__file__)
    for filename in os.listdir(current_dir):
        if filename.endswith('.py') and filename != '__init__.py' and filename != 'base.py':
            module_name = f".{filename[:-3]}"
            importlib.import_module(module_name, package=__name__)

# 执行发现
discover_processors()
