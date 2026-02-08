"""
Basic tests for an application.

This ensures all modules are importable and that the config is valid.
"""

def test_import_app():
    from moxa_interface.application import MoxaInterfaceApplication
    assert MoxaInterfaceApplication

def test_config():
    from moxa_interface.app_config import MoxaInterfaceConfig

    config = MoxaInterfaceConfig()
    assert isinstance(config.to_dict(), dict)

def test_ui():
    from moxa_interface.app_ui import MoxaInterfaceUI
    assert MoxaInterfaceUI

def test_state():
    from moxa_interface.app_state import MoxaInterfaceState
    assert MoxaInterfaceState