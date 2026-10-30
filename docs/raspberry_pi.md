# AURA on Raspberry Pi

## Target hardware

Start with a Raspberry Pi 5 with 8 GB RAM, Raspberry Pi OS 64-bit, the official 27 W USB-C power supply, active cooling, and a reliable USB SSD for 24/7 use. Use an official Camera Module 3, a USB microphone, and powered USB speakers or an HDMI display with audio. The holographic browser UI is served locally; Claude or OpenAI replies still need internet access and a server-side API key.

For sensor experiments, plan on a separate ADC board such as an ADS1115 or MCP3008 for analog sensors. Pi GPIO is 3.3 V only. Many inexpensive gas and ultrasonic sensor boards output 5 V or analog voltages, so use the correct level shifter/divider and ADC before wiring them. Digital water float switches and digital fire modules still need verified pull-up/down wiring. Do not use hobby sensors or AURA as a certified fire, gas, or flood alarm.

## What currently runs

- `aura-app` has a full-screen face at `http://127.0.0.1:8790/?kiosk=1` after session login.
- The existing Python companion brain can call the configured Claude provider or the new server-side OpenAI Responses provider.
- Personal memory continues to work in local SQLite. Optional Supabase sync copies user/assistant conversation rows and sensor events to cloud tables; profile facts, routines, and complete incident/action history are not synced. Failed uploads are retained in a durable SQLite outbox as source-row references and retried with capped backoff. Message text and event summaries are read from their source rows only when sending; they are not duplicated in the outbox. Clearing local conversation history removes pending uploads and queues a remote delete for previously synced rows while the device ID and cloud credentials remain configured.
- The current continuous camera and microphone service uses Apple frameworks and only runs on macOS. The Pi ambient capture daemon, local wake-word/STT, camera scene context, and GPIO sensor drivers are not implemented yet. Software for the TLS sensor hub, enrolled-node heartbeats, owner-managed room invitations, one-shot reply claims, and immediate claim validation is present and tested. A hardware-free reply gate can call an injected playback callback only after those checks pass, but no real speaker pipeline uses it; this is not room-to-room conversation acceptance.
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

The sync sends each new user and assistant conversation entry and each sensor event over HTTPS. Audio and video are not synced. The local SQLite outbox retries after outages without blocking memory writes. Clearing local chat history also queues deletion of its cloud rows; if the cloud device ID or credentials are removed before that delete succeeds, the remote copy may remain. Set the OpenAI or Claude key on the server only. Hosted model requests contain the text/context AURA is asked to answer, so avoid sending private ambient observations unless you choose to enable that behavior.

## Optional systemd sensor API hub

`deploy/systemd/aura-sensor-api.service` is a hardened system service template
for the sensor API hub. It is not the ambient voice/camera companion and does
not provide GPIO drivers or physical room-to-room playback. Install the
checkout at `/opt/aura-companion`, create a dedicated `aura` system user, and
install the unit file into `/etc/systemd/system/`. Create `/etc/aura/aura.env`
with a unique `AURA_SENSOR_API_TOKEN` of at least 32 characters; keep that file
readable only by root. Install a trusted server certificate at
`/etc/aura/tls/server.crt` and its private key at `/etc/aura/tls/server.key`;
the key must be readable by the `aura` service account and unavailable to other
users. The service binds to the network only with TLS 1.2 or newer, and its
startup check rejects missing certificate material or a world-accessible key.
The database stays in the service's private
`/var/lib/aura` state directory. Review firewall rules to allow port 8787 only
from trusted devices before enabling the service. The unit and startup validator
are covered by automated tests, but have not been run on a Raspberry Pi.

### Prepare the enrolled-node heartbeat files

On a development computer, prepare the templates without installing a service
or changing the computer's system settings:

```sh
python3 scripts/prepare_pi_node_service.py --output-dir ./pi-node-prep \
  --project-root /opt/aura-companion
```

The output contains the hardened systemd unit and a placeholder environment
example. It never enrolls a node, generates or copies a credential, creates a
service account, enables systemd, or writes to `/etc`. Use the existing
`scripts/enroll_sensor_node.py` on the trusted hub to enroll the real Pi, then
replace every placeholder on the Pi, install the environment file with
owner-only permissions for `aura-node`, and run
`scripts/check_pi_node_heartbeat_config.py` as that account before enabling the
unit. Do not commit the filled environment file. The preparation test uses a
temporary directory and verifies the generated limits and file permissions;
it does not establish a Raspberry Pi installation or live heartbeat.

### Check local voice software readiness

Before enabling push-to-talk on a prepared Pi, run this offline preflight from
the repository root:

```sh
python3 scripts/check_pi_voice_readiness.py
```

It checks Python 3.11+, the optional Vosk and audio packages, and the configured
non-empty local model directory. `espeak-ng` is reported as optional. The check
does not print the model path, import the speech provider, open a microphone,
test device permissions, access the network, or change system settings. A
ready result covers installed software only; microphone access, model
compatibility and accuracy, speaker output and Pi hardware still need direct
acceptance on the target device.

## Planned Pi service boundary

The Pi integration should keep capture and sensor sampling on the device. A local companion service will read the camera through Picamera2, use local wake-word and speech recognition, synthesize speech locally, and sample individually configured sensor drivers. It should send only a wake-triggered transcript, a short camera-derived description, or a sensor event to the AURA server. AURA should then store conversations and telemetry through a cloud database adapter and call the chosen hosted AI provider from the server process. Provider keys must never be exposed to the kiosk browser. Raw ambient audio and video should not be retained or uploaded by default.

The Python console's one-shot camera observation stores only its derived
summary in SQLite; it does not keep a JPEG snapshot.

### Local push-to-talk speech prototype

The Python companion console can use optional on-device Vosk speech recognition
on Linux/Raspberry Pi and macOS. Install the packages from
`requirements-pi-voice.txt`, install a compatible model separately, and set
`AURA_VOSK_MODEL_PATH` to that existing model directory. AURA never downloads a
model. At startup, microphone input is off unless the user explicitly enables
it; each capture begins only after Enter is pressed, is limited to 15 seconds,
and is immediately closed after one utterance. The recognized text is shown for
confirmation before the existing SQLite memory/personality flow processes it;
the confirmation names that normal memory/provider path. If capture fails on
the first attempt or a requested retry, AURA returns to typed input rather than
terminating the console.
Raw PCM stays in memory and is not written to disk. If the user enabled a
hosted brain earlier in the console, the approved transcript follows that
existing provider path; otherwise the local companion engine responds. If
device setup fails, the console falls back to typed input. This is push-to-talk
only: it does not implement a wake word, background listening, camera
perception, or a network Pi-to-hub conversation. Automated tests use injected
audio/model doubles and do not test microphone permissions, acoustic quality,
or Raspberry Pi hardware.

### One-turn private console conversation

Enter `/private` at the message prompt to make the next typed or reviewed voice
message a private turn. AURA uses a fresh in-memory SQLite store containing
only that message; it skips the saved conversation, memory extractor, camera
observation, routine/feedback writes, and persistent SQLite database. AURA
clears the one-turn setting before generating the reply, and `/cancel-private`
cancels it. If the owner selected a hosted brain at startup, the private text
still goes to that provider and follows its retention policy; the confirmation
repeats this boundary for voice input. AURA displays the reply in the console,
never saves it, and speaks it only if voice output was separately enabled.
This mode has automated
store-isolation tests but no live-provider or Pi acceptance.

```sh
sudo apt install libportaudio2 espeak-ng python3-venv
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-pi-voice.txt
export AURA_VOSK_MODEL_PATH=/opt/aura/models/vosk-model-small-en-us
export AURA_TTS_PROVIDER=espeak-ng
python3 scripts/run_companion_console.py
```

Use a model obtained and reviewed by the device owner. Keep it on the Pi; do not
put model files, recordings, transcripts, or voice credentials in Git.
`vosk` is pinned to its available `0.3.45` release; check wheel compatibility
and package provenance on the target OS before installing it. The software
prototype does not establish deployment support for a specific Pi OS image.
Set `AURA_TTS_PROVIDER=espeak-ng` only when you want local system speech;
console voice output still requires a separate explicit Yes at startup. AURA
passes replies to `espeak-ng` through standard input, imposes a length and time
limit, and does not save generated audio. Automated tests replace the binary
with a fake process; speaker hardware and voice quality remain untested.

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
