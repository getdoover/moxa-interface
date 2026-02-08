from pydoover.docker import run_app

from .application import MoxaInterfaceApplication
from .app_config import MoxaInterfaceConfig

def main():
    """
    Run the application.
    """
    run_app(MoxaInterfaceApplication(config=MoxaInterfaceConfig()))
