# AURA on Raspberry Pi

## Target hardware

Start with a Raspberry Pi 5 with 8 GB RAM, Raspberry Pi OS 64-bit, the official 27 W USB-C power supply, active cooling, and a reliable USB SSD for 24/7 use. Use an official Camera Module 3, a USB microphone, and powered USB speakers or an HDMI display with audio. The holographic browser UI is served locally; Claude or OpenAI replies still need internet access and a server-side API key.

For sensor experiments, plan on a separate ADC board such as an ADS1115 or MCP3008 for analog sensors. Pi GPIO is 3.3 V only. Many inexpensive gas and ultrasonic sensor boards output 5 V or analog voltages, so use the correct level shifter/divider and ADC before wiring them. Digital water float switches and digital fire modules still need verified pull-up/down wiring. Do not use hobby sensors or AURA as a certified fire, gas, or flood alarm.

## What currently runs

- `aura-app` has a full-screen face at `http://127.0.0.1:8790/?kiosk=1` after session login.
- The existing Python companion brain can call the configured Claude provider or the new server-side OpenAI Responses provider.
- Personal memory continues to work in local SQLite. An optional Supabase sync now copies user/assistant conversation rows and sensor events to cloud tables; profile facts, routines, and complete incident/action history are not synced yet. Sync is best-effort and does not have a durable retry queue.
- The current continuous camera and microphone service uses Apple frameworks and only runs on macOS. The Pi ambient capture daemon, local wake-word/STT, camera scene context, sensor drivers, cloud database, and Pi boot service are not implemented yet.
- The existing sensor API and tests model gas, fire, water, and other events, but that is event-processing logic, not Raspberry Pi GPIO driver code.

## Optional cloud setup

Create a Supabase project, run [`../cloud/supabase_schema.sql`](../cloud/supabase_schema.sql) in its SQL editor, and add these settings to the Pi's ignored `config/keys.env`. Keep the service key on the Pi server and never put it in frontend code or share it in a screenshot.

```env
AURA_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
AURA_SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVER_ONLY_KEY
AURA_CLOUD_DEVICE_ID=aura-pi-main
AURA_BRAIN_PROVIDER=openai
OPENAI_API_KEY=YOUR_SERVER_ONLY_KEY
OPENAI_MODEL=gpt-4.1-mini
```

The sync sends each new user and assistant conversation entry and each sensor event over HTTPS. Audio and video are not synced. The current sync runs alongside local SQLite writes, so the companion still works when Supabase is unavailable; missed cloud rows are not retried automatically yet. Set the OpenAI or Claude key on the server only. Hosted model requests contain the text/context AURA is asked to answer, so avoid sending private ambient observations unless you choose to enable that behavior.

## Planned Pi service boundary

The Pi integration should keep capture and sensor sampling on the device. A local companion service will read the camera through Picamera2, use local wake-word and speech recognition, synthesize speech locally, and sample individually configured sensor drivers. It should send only a wake-triggered transcript, a short camera-derived description, or a sensor event to the AURA server. AURA should then store conversations and telemetry through a cloud database adapter and call the chosen hosted AI provider from the server process. Provider keys must never be exposed to the kiosk browser. Raw ambient audio and video should not be retained or uploaded by default.

Sensor configuration must specify exact board, module, room, GPIO/ADC channel, units, calibration, and safe threshold for each sensor. A generic `gas`, `fire`, or `water` threshold is unsafe because modules use different scales and false-alarm behavior. Until each mapping is calibrated and tested against a known reference, sensor reports must be presented as advisory and must not trigger external or physical actions.

## Current checks on a non-Pi computer

From `aura-app/`, run:

```sh
npm ci
npm run build
npm run lint
npm test
```

From the repository root, run the provider contract tests:

```sh
python3 -m unittest scripts.test_openai_provider
python3 -m unittest scripts.test_cloud_sync
```

These checks validate the browser bundle, local API, offline cloud request construction, and provider selection. They do not verify Raspberry Pi camera access, audio devices, GPIO wiring, live cloud credentials, model billing, or sensor calibration. Those require a Pi, a configured cloud project, and the exact sensor modules.
