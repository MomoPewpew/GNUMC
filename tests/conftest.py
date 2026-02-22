"""Pytest configuration: add the plugin directory to sys.path."""

import sys
import os

plugin_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "minecraft-skin-3d",
)
sys.path.insert(0, plugin_dir)
