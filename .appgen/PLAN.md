# Build Plan

## App Summary
- Name: moxa-interface
- Type: docker
- Description: Allows other Doover apps to publish/receive configurable information to/from one or more Moxa i/o hubs via ethernet

## External Integration
- Service: Moxa ioLogik E1200 Series Remote Ethernet I/O (and compatible models)
- Documentation:
  - [ioLogik E1200 Series Product Page](https://www.moxa.com/en/products/industrial-edge-connectivity/controllers-and-ios/universal-controllers-and-i-os/iologik-e1200-series)
  - [ioLogik E1200 Series User Manual v16.2](https://www.moxa.com/getmedia/451bb28e-7e07-4bd7-b8e8-260e093ad73b/moxa-iologik-e1200-series-manual-v16.2.pdf)
  - [RESTful API Tech Note](https://www.moxa.com/getmedia/e88951fa-17b7-4b24-a946-8fa69664284f/moxa-iologik-e1200-series-using-a-restful-api-to-connect-to-remote-ios-tech-note-v1.1.pdf)
  - [Community REST API Example (GitHub)](https://github.com/a5892731/MOXA-ioLogik-E1212)
- Authentication: None (HTTP RESTful API with no authentication by default; password can optionally be configured on the device)
- Protocol: RESTful API over HTTP (primary), Modbus TCP (fallback/alternative)

## Protocol Details

### Moxa ioLogik RESTful API

The Moxa ioLogik E1200 series exposes a RESTful HTTP API for reading and writing I/O channels.

**Required Headers:**
- `Content-Type: application/json`
- `Accept: vdn.dac.v1`

**Base URL pattern:** `http://<hub_ip>/api/slot/0/io/<io_type>`

**API Endpoints:**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/slot/0/sysInfo/device` | GET | Device info (model name, uptime, firmware) |
| `/api/slot/0/io/di` | GET | Read all digital inputs |
| `/api/slot/0/io/di/<index>` | GET | Read single digital input |
| `/api/slot/0/io/do` | GET/PUT | Read/write all digital outputs |
| `/api/slot/0/io/do/<index>` | GET/PUT | Read/write single digital output |
| `/api/slot/0/io/ai` | GET | Read all analog inputs |
| `/api/slot/0/io/ai/<index>` | GET | Read single analog input |
| `/api/slot/0/io/ao` | GET/PUT | Read/write all analog outputs |
| `/api/slot/0/io/ao/<index>` | GET/PUT | Read/write single analog output |

**Digital Input Response Fields:**
- `diIndex` - Channel index (0-based)
- `diMode` - Mode (0=DI)
- `diStatus` - Status (0=OFF, 1=ON) (read-only)
- `diCounterValue` - Counter value (read-only, in counter mode)

**Digital Output Request/Response Fields:**
- `doIndex` - Channel index (0-based)
- `doMode` - Mode (0=DO)
- `doStatus` - Status (0=OFF, 1=ON) (read-write)
- `doPulseCount` - Pulse count (read-write, in pulse mode)

**JSON Envelope Structure:**
```json
{
  "slot": 0,
  "io": {
    "do": [
      {"doIndex": 0, "doMode": 0, "doStatus": 0},
      {"doIndex": 1, "doMode": 0, "doStatus": 1}
    ]
  }
}
```

**Supported Moxa Models (E1200 Series):**
| Model | I/O Configuration |
|-------|-------------------|
| E1210 | 16 DI |
| E1211 | 16 DO |
| E1212 | 8 DI + 8 DIO |
| E1213 | 3 DI (RTD) |
| E1214 | 6 DI + 6 Relay |
| E1240 | 8 AI |
| E1241 | 4 AO |
| E1242 | 4 AI + 4 DI + 4 DIO |
| E1260 | 6 RTD |
| E1262 | 8 Thermocouple |

## Data Flow
- **Inputs:**
  - Configuration: List of Moxa hub IP addresses, poll interval, I/O channel mappings
  - From Moxa hubs: Digital input states, analog input values (via RESTful API GET)
  - From other Doover apps: Output commands via tags (to write to Moxa DO/AO channels)
- **Processing:**
  - Poll each configured Moxa hub on a regular interval
  - Read all configured I/O channels (DI, DO, AI, AO) from each hub
  - Publish read values as tags (keyed by hub + channel) for other Doover apps to consume
  - Listen for output command tags from other apps and write values to Moxa DO/AO channels
  - Track connection health per hub (online/offline, last seen, error count)
- **Outputs:**
  - Tags: Per-hub, per-channel I/O values published for other Doover apps
  - Tags: Connection status per hub
  - Tags: Overall app status
  - HTTP PUT requests: Write digital output and analog output values to Moxa hubs

## Configuration Schema
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `hubs` | Array of Object | yes | `[]` | List of Moxa hub configurations |
| `hubs[].name` | String | yes | - | Human-readable name for this hub (used in tag keys) |
| `hubs[].ip_address` | String | yes | - | IP address of the Moxa hub |
| `hubs[].enabled` | Boolean | no | `true` | Whether to poll this hub |
| `hubs[].poll_interval` | Number | no | `2.0` | Seconds between polls for this hub |
| `hubs[].di_channels` | Array of Integer | no | `[]` | Digital input channel indices to read |
| `hubs[].do_channels` | Array of Integer | no | `[]` | Digital output channel indices to manage |
| `hubs[].ai_channels` | Array of Integer | no | `[]` | Analog input channel indices to read |
| `hubs[].ao_channels` | Array of Integer | no | `[]` | Analog output channel indices to manage |
| `request_timeout` | Number | no | `2.0` | HTTP request timeout in seconds |
| `publish_on_change_only` | Boolean | no | `false` | Only publish tags when values change |
| `debug_enabled` | Boolean | no | `false` | Enable debug logging to channel |

## UI Elements

No UI components (has_ui is false). All interaction is via tags and configuration.

## Documentation Chunks

### Required Chunks
- `config-schema.md` - Configuration types and patterns (Array, Object, nested structures)
- `docker-application.md` - Application class structure, lifecycle, loop control
- `docker-project.md` - Entry point, Dockerfile, project setup

### Recommended Chunks
- `docker-advanced.md` - Hardware I/O patterns, error recovery, throttling, batching
- `tags-channels.md` - Tag read/write patterns, inter-app communication, change-based publishing
- `doover-config.md` - Application metadata, depends_on configuration

### Discovery Keywords
moxa, ethernet, i/o, digital input, digital output, analog input, analog output, hub, poll, REST, API, HTTP, connection, timeout, retry, tag, publish, channel, inter-app

## Implementation Notes

### Architecture
- The app acts as a **bridge** between Moxa ioLogik hubs and the Doover tag system
- Each hub is polled independently at its configured interval
- I/O values are published as tags using a naming convention: `{hub_name}_di_{index}`, `{hub_name}_do_{index}`, `{hub_name}_ai_{index}`, `{hub_name}_ao_{index}`
- Other Doover apps write to output tags (e.g. `{hub_name}_do_{index}_cmd`) which this app picks up and sends to the hub
- Connection status tags: `{hub_name}_status` (online/offline), `{hub_name}_last_seen`

### External Packages Needed
- `httpx` - Async HTTP client for REST API calls (preferred over `requests` for async compatibility)

### Key Patterns to Follow
- Use async HTTP calls (httpx.AsyncClient) in main_loop to avoid blocking
- Implement per-hub connection tracking with error counting and backoff
- Use change-based publishing to reduce unnecessary tag updates when `publish_on_change_only` is true
- Cache last-known values so other apps always have data even if a hub goes offline
- Graceful degradation: if one hub is unreachable, continue polling others
- Rate-limit PUT requests to prevent overwhelming hubs

### Error Handling
- Wrap each hub's poll in try/except to isolate failures
- Track consecutive errors per hub; after N failures, increase poll interval (backoff)
- Log connection errors but do not crash the main loop
- Publish error status via tags so other apps can react

### Main Loop Design
- `loop_target_period = 1` (1 second base loop)
- Each iteration: check which hubs are due for polling based on their individual `poll_interval`
- For each due hub: GET DI, AI statuses; check for pending output commands; PUT DO, AO if commands exist
- Update status tags after each hub poll

### Dependencies (doover_config.json)
- `depends_on` should include `"device_agent"` (for tag/channel operations)
- No `platform_interface` or `modbus_interface` needed (communication is via Ethernet HTTP, not local GPIO or Modbus)

### Simulator Design
- The simulator should emulate a Moxa ioLogik hub by running a simple HTTP server
- Respond to GET requests on `/api/slot/0/io/di`, `/api/slot/0/io/do`, `/api/slot/0/io/ai`, `/api/slot/0/io/ao`
- Accept PUT requests on `/api/slot/0/io/do`, `/api/slot/0/io/ao`
- Return realistic JSON responses matching the Moxa API format
- Allow toggling simulated input values over time for testing
