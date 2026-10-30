# Pi Sensor Node Simulator v0.1

Simulates future Raspberry Pi, camera, and sensor nodes sending events to the AURA Sensor API over Wi-Fi.

## Prerequisites

1. Set a 32-character-or-longer hub token in `config/keys.env` (generate with `python scripts/generate_sensor_api_token.py`).
2. Start the AURA hub API and enroll the node:

```powershell
python scripts/run_sensor_api.py
python scripts/enroll_sensor_node.py pi_bedroom_node bedroom --name "Bedroom Pi"
```

Copy the one-time `AURA_SENSOR_NODE_TOKEN` output into the Pi's private
`config/keys.env`. The hub token stays on the hub only.

## Basic usage

```powershell
python scripts/pi_node_simulator.py bedroom fall_detected
python scripts/pi_node_simulator.py kitchen smoke_detected
python scripts/pi_node_simulator.py balcony plant_moisture_low
python scripts/pi_node_simulator.py front_door unknown_person_detected
python scripts/pi_node_simulator.py medicine pill_missed
```

The simulator uses the enrolled node token when configured. A background Pi
service should send a heartbeat every 30 seconds; test one with:

```powershell
python scripts/pi_node_simulator.py --heartbeat pi_bedroom_node
```

List supported nodes and events:

```powershell
python scripts/pi_node_simulator.py --list
```

## Loop example

Send the same event multiple times with a delay:

```powershell
python scripts/pi_node_simulator.py balcony plant_moisture_low --loop 3 --delay 5
```

## Remote hub example

For a hub on another machine, configure a trusted TLS certificate and use its
hostname. Remote HTTP URLs are rejected before AURA sends the node credential.

```powershell
python scripts/pi_node_simulator.py bedroom fall_detected --hub-url https://aura-hub.example.com:8787
```

Or set `AURA_SENSOR_API_URL` in `config/keys.env`.

## Optional arguments

| Flag | Description |
|------|-------------|
| `--hub-url` | Hub base URL (default: `AURA_SENSOR_API_URL` or `http://127.0.0.1:8787`) |
| `--confidence` | Override event confidence |
| `--source` | Override source identifier |
| `--summary` | Override event summary text |
| `--loop N` | Send event N times |
| `--delay SECONDS` | Delay between loop sends (default: 3) |
| `--list` | Show supported nodes/events |

The default `http://127.0.0.1:8787` is limited to local development. A network
hub requires HTTPS; install its issuing CA in the Pi operating system trust
store so normal certificate verification remains enabled.

## Supported nodes

| Node | Source | Room | Example events |
|------|--------|------|----------------|
| `bedroom` | `pi_bedroom_node` | bedroom | `fall_detected`, `sleep_unusual` |
| `kitchen` | `pi_kitchen_node` | kitchen | `smoke_detected`, `fire_detected` |
| `balcony` | `pi_balcony_plant_node` | balcony | `plant_moisture_low` |
| `front_door` | `pi_front_door_node` | front_door | `unknown_person_detected` |
| `medicine` | `medicine_schedule_node` | bedroom | `pill_missed` |
| `health` | `wearable_bridge_node` | user | `heart_rate_high` |

## Test script

With the API server running:

```powershell
python scripts/test_pi_node_simulator.py
```

Inspect results:

```powershell
python scripts/list_recent_events.py
python scripts/list_action_logs.py
```

## Safety notes

- This simulates future Raspberry Pi nodes — **no real sensors are required**.
- **No real emergency calls, SMS, siren, or water pump** actions happen.
- Keep the API on a **trusted LAN only**.
- Configure `AURA_SENSOR_NODE_TOKEN` on an enrolled node, or the hub token for hub-side simulation; the simulator refuses to send without a strong token and never prints token contents.
- Each simulated event includes a stable UUID and retries transient connection or server errors up to three times. AURA deduplicates those retries, so event observations and safety handling run once.
