# Pi Sensor Node Simulator v0.1

Simulates future Raspberry Pi, camera, and sensor nodes sending events to the AURA Sensor API over Wi-Fi.

## Prerequisites

1. Set `AURA_SENSOR_API_TOKEN` in `config/keys.env` (generate with `python scripts/generate_sensor_api_token.py`).
2. Start the AURA hub API:

```powershell
python scripts/run_sensor_api.py
```

## Basic usage

```powershell
python scripts/pi_node_simulator.py bedroom fall_detected
python scripts/pi_node_simulator.py kitchen smoke_detected
python scripts/pi_node_simulator.py balcony plant_moisture_low
python scripts/pi_node_simulator.py front_door unknown_person_detected
python scripts/pi_node_simulator.py medicine pill_missed
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

Point at another machine on your LAN:

```powershell
python scripts/pi_node_simulator.py bedroom fall_detected --hub-url http://192.168.1.50:8787
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
- Token must be in `config/keys.env` as `AURA_SENSOR_API_TOKEN` when auth is enabled.
