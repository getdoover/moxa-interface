from pathlib import Path

from pydoover import config


class MoxaInterfaceConfig(config.Schema):
    def __init__(self):
        # Hub configuration - array of hub objects
        self.hubs = config.Array(
            "Moxa Hubs",
            description="List of Moxa ioLogik hub configurations",
        )
        hub = config.Object("Hub")
        hub.add_elements(
            config.String("Name", description="Human-readable name for this hub (used in tag keys)"),
            config.String("IP Address", description="IP address of the Moxa hub"),
            config.Boolean("Enabled", description="Whether to poll this hub", default=True),
            config.Number("Poll Interval", description="Seconds between polls for this hub", default=2.0),
            config.Array(
                "DI Channels",
                description="Digital input channel indices to read",
                element=config.Integer("Channel Index"),
            ),
            config.Array(
                "DO Channels",
                description="Digital output channel indices to manage",
                element=config.Integer("Channel Index"),
            ),
            config.Array(
                "AI Channels",
                description="Analog input channel indices to read",
                element=config.Integer("Channel Index"),
            ),
            config.Array(
                "AO Channels",
                description="Analog output channel indices to manage",
                element=config.Integer("Channel Index"),
            ),
        )
        self.hubs.element = hub

        # Global settings
        self.request_timeout = config.Number(
            "Request Timeout",
            description="HTTP request timeout in seconds",
            default=2.0,
        )
        self.publish_on_change_only = config.Boolean(
            "Publish On Change Only",
            description="Only publish tags when values change",
            default=False,
        )
        self.debug_enabled = config.Boolean(
            "Debug Enabled",
            description="Enable debug logging to channel",
            default=False,
        )

    @property
    def timeout_seconds(self):
        return self.request_timeout.value


def export():
    MoxaInterfaceConfig().export(Path(__file__).parents[2] / "doover_config.json", "moxa_interface")


if __name__ == "__main__":
    export()
