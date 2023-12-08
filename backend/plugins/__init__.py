# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      __init__
   Description:
   Author:          Lijiamin
   date：           2023/12/6 16:39
-------------------------------------------------
   Change Activity:
                    2023/12/6 16:39
-------------------------------------------------
"""
# plugins/__init__.py
# Import the pyplugs libs
import pyplugs
import os
# All function names are going to be stored under names
names = pyplugs.names_factory(__package__)

# When read function is called, it will call a function received as parameter
read = pyplugs.call_factory(__package__)
print(os.path.abspath('extensibles'))
print(__package__)
print(names)
print(read)