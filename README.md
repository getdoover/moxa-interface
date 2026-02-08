# Moxa Interface

<img src="https://raw.githubusercontent.com/getdoover/moxa-interface/main/assets/icon.png" alt="App Icon" style="max-width: 100px;">

**Allows other Doover apps to publish/receive configurable information to/from one or more Moxa i/o hubs via ethernet**

[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](https://github.com/getdoover/moxa-interface)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/getdoover/moxa-interface/blob/main/LICENSE)

[Getting Started](#getting-started) | [Configuration](#configuration) | [Developer](https://github.com/getdoover/moxa-interface/blob/main/DEVELOPMENT.md) | [Need Help?](#need-help)

<br/>

## Overview

Moxa Interface is a Doover device application that bridges the gap between the Doover IoT platform and Moxa ioLogik series I/O hubs. It communicates with one or more Moxa hubs over Ethernet using the Moxa ioLogik REST API, reading digital and analog inputs and outputs at configurable intervals, and publishing the data as Doover tags for consumption by other applications in the ecosystem.

The application supports bidirectional communication: it continuously polls configured I/O channels and publishes their values as tags, while also listening for output command tags set by other Doover apps. When a command tag is detected, the application writes the corresponding value to the Moxa hub's digital or analog output, enabling remote control of physical I/O from anywhere in the Doover platform.

Designed for reliability in industrial environments, Moxa Interface includes per-hub connection tracking with automatic exponential backoff on errors, configurable poll intervals, and optional change-only publishing to minimise unnecessary network traffic. It supports multiple hubs simultaneously, each with independent channel configurations and polling schedules.

### Features

- **Multi-hub support** - Connect to and manage multiple Moxa ioLogik hubs simultaneously, each with independent configuration
- **Full I/O coverage** - Read digital inputs (DI), digital outputs (DO), analog inputs (AI), and analog outputs (AO)
- **Bidirectional control** - Read I/O values and write to digital/analog outputs via command tags from other Doover apps
- **Per-hub connection tracking** - Independent online/offline status monitoring with last-seen timestamps for each hub
- **Exponential backoff** - Automatic retry backoff on communication errors to avoid flooding unresponsive hubs
- **Change-only publishing** - Optional mode to publish tags only when values change, reducing platform traffic
- **Configurable polling** - Per-hub poll intervals allow fine-tuning based on I/O update frequency requirements
- **Debug logging** - Optional debug mode that publishes detailed diagnostic information to a debug channel

<br/>

## Getting Started

### Prerequisites

1. One or more **Moxa ioLogik** series I/O hubs (e.g., E1210, E1212, E1240, E1260) accessible over Ethernet
2. The Moxa hubs must have the **REST API enabled** (the ioLogik REST API with `Accept: vdn.dac.v1` header support)
3. Network connectivity between the Doover device running this application and the Moxa hub(s)
4. A **Doover account** with a device configured to run Docker applications

### Installation

1. Add the **Moxa Interface** application to your Doover device from the Doover app catalogue
2. The application container image will be pulled automatically from `ghcr.io/getdoover/moxa_interface:main`
3. Configure the application with your Moxa hub details (see [Configuration](#configuration))

### Quick Start

1. Add the application to your Doover device
2. In the application configuration, add at least one hub entry with the hub's **name** and **IP address**
3. Specify the **channel indices** you want to monitor (DI, DO, AI, AO)
4. Save the configuration -- the application will begin polling immediately
5. Verify connectivity by checking the `{hub_name}_status` tag for `"online"`

<br/>

## Configuration

### Global Settings

| Setting | Description | Default |
|---------|-------------|---------|
| **Moxa Hubs** | List of Moxa ioLogik hub configurations | *Required* |
| **Request Timeout** | HTTP request timeout in seconds for all API calls to Moxa hubs | `2.0` |
| **Publish On Change Only** | Only publish tags when values change (reduces platform traffic) | `false` |
| **Debug Enabled** | Enable debug logging to the debug channel | `false` |

### Per-Hub Settings

Each entry in the Moxa Hubs array supports the following settings:

| Setting | Description | Default |
|---------|-------------|---------|
| **Name** | Human-readable name for this hub (used as prefix in tag keys) | *Required* |
| **IP Address** | IP address of the Moxa hub on the local network | *Required* |
| **Enabled** | Whether to poll this hub | `true` |
| **Poll Interval** | Seconds between polls for this hub | `2.0` |
| **DI Channels** | Digital input channel indices to read | *Required* |
| **DO Channels** | Digital output channel indices to manage | *Required* |
| **AI Channels** | Analog input channel indices to read | *Required* |
| **AO Channels** | Analog output channel indices to manage | *Required* |

### Example Configuration

```json
{
  "moxa_hubs": [
    {
      "name": "plant_room",
      "ip_address": "192.168.1.100",
      "enabled": true,
      "poll_interval": 2.0,
      "di_channels": [0, 1, 2, 3],
      "do_channels": [0, 1],
      "ai_channels": [0, 1, 2],
      "ao_channels": [0]
    },
    {
      "name": "roof_unit",
      "ip_address": "192.168.1.101",
      "enabled": true,
      "poll_interval": 5.0,
      "di_channels": [0, 1],
      "do_channels": [],
      "ai_channels": [0, 1, 2, 3],
      "ao_channels": []
    }
  ],
  "request_timeout": 2.0,
  "publish_on_change_only": true,
  "debug_enabled": false
}
```

<br/>

## Tags

This application exposes the following tags, where `{hub}` is the hub's configured name and `{n}` is the channel index.

### I/O Value Tags (Published by App)

| Tag | Type | Description |
|-----|------|-------------|
| **`{hub}_di_{n}`** | Integer (0/1) | Current digital input status for channel `n` on the named hub |
| **`{hub}_do_{n}`** | Integer (0/1) | Current digital output status for channel `n` on the named hub |
| **`{hub}_ai_{n}`** | Float | Current analog input value (raw) for channel `n` on the named hub |
| **`{hub}_ao_{n}`** | Float | Current analog output value (raw) for channel `n` on the named hub |

### Hub Status Tags (Published by App)

| Tag | Type | Description |
|-----|------|-------------|
| **`{hub}_status`** | String | Connection status of the hub: `"online"` or `"offline"` |
| **`{hub}_last_seen`** | String (ISO 8601) | Timestamp of the last successful poll for the hub |
| **`app_status`** | String | Overall application status (publishes `"running"` each loop) |

### Command Tags (Consumed by App)

Other Doover applications can write to these tags to control outputs on a Moxa hub. The tag is cleared automatically after the command is executed.

| Tag | Type | Description |
|-----|------|-------------|
| **`{hub}_do_{n}_cmd`** | Integer (0/1) | Set to `0` or `1` to write a digital output on channel `n` |
| **`{hub}_ao_{n}_cmd`** | Float | Set to a numeric value to write an analog output on channel `n` |

### Example

For a hub named `plant_room` with DI channels `[0, 1]` and DO channels `[0]`, the following tags would be created:

- `plant_room_di_0` -- digital input channel 0 value
- `plant_room_di_1` -- digital input channel 1 value
- `plant_room_do_0` -- digital output channel 0 value
- `plant_room_do_0_cmd` -- write command for digital output channel 0
- `plant_room_status` -- hub connection status
- `plant_room_last_seen` -- last successful communication timestamp

<br/>

## How It Works

1. **Startup** -- The application initialises an HTTP client and builds internal state objects for each enabled Moxa hub defined in the configuration.
2. **Polling loop** -- A main loop runs every 1 second. On each iteration, it checks whether each hub is due for a poll based on its configured poll interval.
3. **I/O reads** -- For each hub that is due, the application sends HTTP GET requests to the Moxa ioLogik REST API endpoints (`/api/slot/0/io/di`, `/api/slot/0/io/do`, `/api/slot/0/io/ai`, `/api/slot/0/io/ao`) to read the current state of all configured channels.
4. **Tag publishing** -- The retrieved I/O values are published as Doover tags using the naming convention `{hub_name}_{io_type}_{channel_index}`. If "Publish On Change Only" is enabled, values that have not changed since the last publish are skipped.
5. **Output commands** -- The application checks for command tags (e.g., `{hub}_do_{n}_cmd`) set by other Doover apps. When a command is found, it sends an HTTP PUT request to the Moxa hub to write the value, then clears the command tag.
6. **Error handling** -- If a hub poll fails, the application records the error, increments an error counter, and applies exponential backoff to the poll interval (up to 60 seconds). After 5 consecutive errors, the hub is marked as offline. On the next successful poll, the hub is restored to online and the poll interval is reset.

<br/>

## Integrations

This Docker device application works with:

- **Moxa ioLogik series hubs** -- Any Moxa ioLogik hub that supports the REST API (e.g., E1200 series) for digital and analog I/O
- **Doover Device Agent** -- Runs alongside the Doover device agent which manages the application lifecycle
- **Other Doover apps** -- Any Doover application on the same device can read I/O tags published by this app or write command tags to control outputs
- **Doover platform** -- All I/O data is available through the Doover platform for dashboards, alerts, and automation

<br/>

## Need Help?

- Email: support@doover.com
- [Doover Documentation](https://docs.doover.com)
- [App Developer Documentation](https://github.com/getdoover/moxa-interface/blob/main/DEVELOPMENT.md)

<br/>

## Version History

### v0.1.0 (Current)
- Initial release
- Multi-hub Moxa ioLogik REST API polling over Ethernet
- Digital and analog input/output reading and publishing as Doover tags
- Bidirectional output control via command tags
- Per-hub connection tracking with online/offline status
- Exponential backoff on communication errors
- Configurable poll intervals and change-only publishing
- Debug logging support

<br/>

## License

This app is licensed under the [Apache License 2.0](https://github.com/getdoover/moxa-interface/blob/main/LICENSE).
