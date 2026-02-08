import json
import logging
import time
from datetime import datetime, timezone

import httpx
from pydoover.docker import Application

from .app_config import MoxaInterfaceConfig

log = logging.getLogger(__name__)

# Moxa ioLogik REST API required headers
MOXA_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "vdn.dac.v1",
}

# Backoff constants
MAX_CONSECUTIVE_ERRORS = 5
BACKOFF_MULTIPLIER = 2.0
MAX_BACKOFF_INTERVAL = 60.0


class HubState:
    """Tracks connection state and cached values for a single Moxa hub."""

    def __init__(self, name: str, ip_address: str, poll_interval: float):
        self.name = name
        self.ip_address = ip_address
        self.poll_interval = poll_interval
        self.base_poll_interval = poll_interval

        self.online = False
        self.last_seen = None
        self.consecutive_errors = 0
        self.last_poll_time = 0.0

        # Cached I/O values (keyed by channel index)
        self.di_values: dict[int, int] = {}
        self.do_values: dict[int, int] = {}
        self.ai_values: dict[int, float] = {}
        self.ao_values: dict[int, float] = {}

    @property
    def base_url(self) -> str:
        return f"http://{self.ip_address}"

    def is_due_for_poll(self, now: float) -> bool:
        return (now - self.last_poll_time) >= self.poll_interval

    def record_success(self):
        self.online = True
        self.last_seen = datetime.now(timezone.utc).isoformat()
        self.consecutive_errors = 0
        self.poll_interval = self.base_poll_interval

    def record_error(self):
        self.consecutive_errors += 1
        if self.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            self.online = False
        # Apply backoff
        backoff = min(
            self.base_poll_interval * (BACKOFF_MULTIPLIER ** self.consecutive_errors),
            MAX_BACKOFF_INTERVAL,
        )
        self.poll_interval = backoff


class MoxaInterfaceApplication(Application):
    config: MoxaInterfaceConfig

    loop_target_period = 1  # 1 second base loop

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.hub_states: dict[str, HubState] = {}
        self.http_client: httpx.AsyncClient | None = None
        self.last_published_values: dict[str, object] = {}

    async def setup(self):
        timeout = self.config.request_timeout.value or 2.0
        self.http_client = httpx.AsyncClient(
            headers=MOXA_HEADERS,
            timeout=httpx.Timeout(timeout),
        )
        self._init_hub_states()
        log.info(
            "Moxa Interface started with %d hub(s) configured",
            len(self.hub_states),
        )

    # ------------------------------------------------------------------
    # Hub state initialization
    # ------------------------------------------------------------------

    def _init_hub_states(self):
        """Build HubState objects from the current configuration."""
        self.hub_states.clear()
        if not self.config.hubs or not self.config.hubs.elements:
            return
        for hub_cfg in self.config.hubs.elements:
            name = hub_cfg.name.value
            ip_address = hub_cfg.ip_address.value
            enabled = hub_cfg.enabled.value if hub_cfg.enabled.value is not None else True
            poll_interval = hub_cfg.poll_interval.value if hub_cfg.poll_interval.value is not None else 2.0
            if not enabled:
                log.info("Hub '%s' is disabled, skipping", name)
                continue
            if not name or not ip_address:
                log.warning("Hub missing name or IP address, skipping")
                continue
            self.hub_states[name] = HubState(name, ip_address, poll_interval)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def main_loop(self):
        now = time.time()

        for hub_name, hub in self.hub_states.items():
            if not hub.is_due_for_poll(now):
                continue

            hub.last_poll_time = now

            try:
                await self._poll_hub(hub)
                hub.record_success()
            except Exception as e:
                hub.record_error()
                log.error(
                    "Error polling hub '%s' (%s): %s (consecutive errors: %d)",
                    hub_name,
                    hub.ip_address,
                    e,
                    hub.consecutive_errors,
                )

            # Publish hub status tags
            await self._publish_hub_status(hub)

        # Check for pending output commands
        await self._process_output_commands()

        # Publish overall app status
        await self.set_tag("app_status", "running")

    # ------------------------------------------------------------------
    # Hub polling
    # ------------------------------------------------------------------

    async def _poll_hub(self, hub: HubState):
        """Poll all configured I/O channels for a single hub."""
        hub_cfg = self._get_hub_config(hub.name)
        if hub_cfg is None:
            return

        # Read digital inputs
        di_channels = self._get_channel_indices(hub_cfg, "di_channels")
        if di_channels:
            await self._read_digital_inputs(hub, di_channels)

        # Read digital outputs (to track current state)
        do_channels = self._get_channel_indices(hub_cfg, "do_channels")
        if do_channels:
            await self._read_digital_outputs(hub, do_channels)

        # Read analog inputs
        ai_channels = self._get_channel_indices(hub_cfg, "ai_channels")
        if ai_channels:
            await self._read_analog_inputs(hub, ai_channels)

        # Read analog outputs (to track current state)
        ao_channels = self._get_channel_indices(hub_cfg, "ao_channels")
        if ao_channels:
            await self._read_analog_outputs(hub, ao_channels)

    def _get_hub_config(self, hub_name: str):
        """Find the hub config object by name."""
        if not self.config.hubs or not self.config.hubs.elements:
            return None
        for hub_cfg in self.config.hubs.elements:
            if hub_cfg.name.value == hub_name:
                return hub_cfg
        return None

    def _get_channel_indices(self, hub_cfg, attr_name: str) -> list[int]:
        """Extract channel index list from hub config."""
        channels_cfg = getattr(hub_cfg, attr_name, None)
        if channels_cfg is None or not channels_cfg.elements:
            return []
        return [ch.value for ch in channels_cfg.elements if ch.value is not None]

    # ------------------------------------------------------------------
    # I/O read operations
    # ------------------------------------------------------------------

    async def _read_digital_inputs(self, hub: HubState, channels: list[int]):
        url = f"{hub.base_url}/api/slot/0/io/di"
        response = await self.http_client.get(url)
        response.raise_for_status()
        data = response.json()

        io_list = data.get("io", {}).get("di", [])
        for item in io_list:
            index = item.get("diIndex")
            if index in channels:
                status = item.get("diStatus", 0)
                hub.di_values[index] = status
                tag_key = f"{hub.name}_di_{index}"
                await self._publish_value(tag_key, status)

    async def _read_digital_outputs(self, hub: HubState, channels: list[int]):
        url = f"{hub.base_url}/api/slot/0/io/do"
        response = await self.http_client.get(url)
        response.raise_for_status()
        data = response.json()

        io_list = data.get("io", {}).get("do", [])
        for item in io_list:
            index = item.get("doIndex")
            if index in channels:
                status = item.get("doStatus", 0)
                hub.do_values[index] = status
                tag_key = f"{hub.name}_do_{index}"
                await self._publish_value(tag_key, status)

    async def _read_analog_inputs(self, hub: HubState, channels: list[int]):
        url = f"{hub.base_url}/api/slot/0/io/ai"
        response = await self.http_client.get(url)
        response.raise_for_status()
        data = response.json()

        io_list = data.get("io", {}).get("ai", [])
        for item in io_list:
            index = item.get("aiIndex")
            if index in channels:
                value = item.get("aiValueRaw", item.get("aiValue", 0.0))
                hub.ai_values[index] = value
                tag_key = f"{hub.name}_ai_{index}"
                await self._publish_value(tag_key, value)

    async def _read_analog_outputs(self, hub: HubState, channels: list[int]):
        url = f"{hub.base_url}/api/slot/0/io/ao"
        response = await self.http_client.get(url)
        response.raise_for_status()
        data = response.json()

        io_list = data.get("io", {}).get("ao", [])
        for item in io_list:
            index = item.get("aoIndex")
            if index in channels:
                value = item.get("aoValueRaw", item.get("aoValue", 0.0))
                hub.ao_values[index] = value
                tag_key = f"{hub.name}_ao_{index}"
                await self._publish_value(tag_key, value)

    # ------------------------------------------------------------------
    # I/O write operations
    # ------------------------------------------------------------------

    async def _write_digital_output(self, hub: HubState, index: int, status: int):
        """Write a single digital output on a Moxa hub."""
        url = f"{hub.base_url}/api/slot/0/io/do/{index}"
        payload = {"io": {"do": {"doIndex": index, "doMode": 0, "doStatus": status}}}
        try:
            response = await self.http_client.put(url, content=json.dumps(payload))
            response.raise_for_status()
            hub.do_values[index] = status
            log.info("Set DO %d to %d on hub '%s'", index, status, hub.name)
        except Exception as e:
            log.error("Failed to write DO %d on hub '%s': %s", index, hub.name, e)

    async def _write_analog_output(self, hub: HubState, index: int, value: float):
        """Write a single analog output on a Moxa hub."""
        url = f"{hub.base_url}/api/slot/0/io/ao/{index}"
        payload = {"io": {"ao": {"aoIndex": index, "aoValue": value}}}
        try:
            response = await self.http_client.put(url, content=json.dumps(payload))
            response.raise_for_status()
            hub.ao_values[index] = value
            log.info("Set AO %d to %s on hub '%s'", index, value, hub.name)
        except Exception as e:
            log.error("Failed to write AO %d on hub '%s': %s", index, hub.name, e)

    # ------------------------------------------------------------------
    # Output command processing
    # ------------------------------------------------------------------

    async def _process_output_commands(self):
        """Check for output command tags from other apps and write to hubs."""
        for hub_name, hub in self.hub_states.items():
            hub_cfg = self._get_hub_config(hub_name)
            if hub_cfg is None or not hub.online:
                continue

            # Process digital output commands
            do_channels = self._get_channel_indices(hub_cfg, "do_channels")
            for index in do_channels:
                cmd_tag = f"{hub_name}_do_{index}_cmd"
                cmd_value = self.get_tag(cmd_tag)
                if cmd_value is not None:
                    status = int(cmd_value)
                    await self._write_digital_output(hub, index, status)
                    # Clear the command tag
                    await self.set_tag(cmd_tag, None)

            # Process analog output commands
            ao_channels = self._get_channel_indices(hub_cfg, "ao_channels")
            for index in ao_channels:
                cmd_tag = f"{hub_name}_ao_{index}_cmd"
                cmd_value = self.get_tag(cmd_tag)
                if cmd_value is not None:
                    value = float(cmd_value)
                    await self._write_analog_output(hub, index, value)
                    # Clear the command tag
                    await self.set_tag(cmd_tag, None)

    # ------------------------------------------------------------------
    # Publishing helpers
    # ------------------------------------------------------------------

    async def _publish_value(self, tag_key: str, value):
        """Publish a value as a tag, optionally only on change."""
        publish_on_change = self.config.publish_on_change_only.value
        if publish_on_change:
            last = self.last_published_values.get(tag_key)
            if last == value:
                return
        self.last_published_values[tag_key] = value
        await self.set_tag(tag_key, value)

    async def _publish_hub_status(self, hub: HubState):
        """Publish connection status tags for a hub."""
        await self.set_tag(f"{hub.name}_status", "online" if hub.online else "offline")
        if hub.last_seen:
            await self.set_tag(f"{hub.name}_last_seen", hub.last_seen)

    # ------------------------------------------------------------------
    # Debug logging
    # ------------------------------------------------------------------

    async def _debug_log(self, category: str, message: str, data: dict = None):
        """Publish debug info to the debug channel."""
        if not self.config.debug_enabled.value:
            return
        await self.device_agent.publish_to_channel_async(
            "debug",
            json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "category": category,
                "message": message,
                "data": data,
            }),
        )
