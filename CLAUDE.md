# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Firmware + tooling for a WiFi/IP megaphone speaker built on the Waveshare ESP32-S3-AUDIO-Board (Xtensa dual-core, 8MB Octal PSRAM, 16MB flash, ES8311 DAC + ES7210 ADC + TCA9555 I/O expander). **SIRENA**, the Docker command-center dashboard (`docker/dashboard/`, Flask + SQLite), receives incidents from the 112CV feed, synthesizes speech with Piper TTS, and streams the audio in real time over UDP to one or more of these speakers (one per población/zona in the BRAVO 2 deployment); it also supports manual message sending and per-speaker/zone management.

Repo layout:
- `esp32s3-firmware/ip-speaker/` — the ESP-IDF firmware project (all the C code lives in `main/`).
- `docker/dashboard/` — the SIRENA Flask dashboard (`app.py`, `routes/`, `models/`, `services/`, `templates/`, `schema.sql`). `db.py` applies `schema.sql` plus a small hand-rolled `_COLUMN_MIGRATIONS` list on every startup (no formal migration framework) — add new columns there when evolving the schema.
- `docker/reference_send_audio.py` — standalone reference implementation of the sender-side protocol (header packing, Opus encoding, lead-buffer pacing), used by `services/sender.py` and as documentation for anything else that needs to send audio to a speaker.
- `documentation/` — environment setup and project docs.

## Build / flash / monitor commands

Requires ESP-IDF v6.1 activated in the shell first:
```bash
source /Users/alexcasanova/.espressif/tools/activate_idf_v6.1.sh
```
`idf.py` may not be on `PATH` after activation; if so invoke it via `python3 $IDF_PATH/tools/idf.py ...`.

All commands run from `esp32s3-firmware/ip-speaker/`:
```bash
idf.py build                          # compile
idf.py -p /dev/cu.usbmodemXXXX flash  # flash (find the port with `ls /dev/cu.*`)
idf.py -p /dev/cu.usbmodemXXXX monitor  # serial monitor, Ctrl+] to exit
idf.py menuconfig                     # interactive Kconfig; for scripted changes, edit sdkconfig directly then `idf.py reconfigure`
idf.py add-dependency "ns/component^1.2.3"  # add an IDF Component Registry dependency to main/idf_component.yml
```
No unit test suite exists yet — verification is done by flashing to real hardware and checking serial logs / actual audio output. There is no lint/format tooling configured beyond `.clangd` (clangd is used for IDE diagnostics only).

`main/wifi_credentials.h` (gitignored) must exist with `WIFI_SSID`/`WIFI_PASSWORD` defines before building for the first time — copy it from `main/wifi_credentials.h.example`. These are only fallback defaults for development; in normal operation credentials come from NVS (see below).

## Architecture

**Firmware pipeline** (`main/ip-speaker.c` orchestrates `app_main()`):
1. `audio_codec_es8311` brings up the shared I2C bus, the TCA9555 I/O expander (used only for `PA_CTRL`, amplifier enable — it is **not** a direct GPIO, see `docs/hardware_pins.md`), the I2S TX channel, and the ES8311 codec via the `esp_codec_dev` component (not the standalone `espressif/es8311` registry component, which is legacy-I2C-only and would conflict with TCA9555's modern `i2c_master` driver on the same bus).
2. `wifi_manager` connects STA using NVS-stored credentials if present, else falling back to `wifi_credentials.h`. `WIFI_PS_NONE` is always set after connecting — WiFi power-save adds jitter that's audible as dropouts in real-time audio. If there are no valid credentials, connection times out, or the BOOT button (GPIO0) is held at boot, it starts an open AP (`IPSpeaker-Config-XXXX`) instead and returns `WIFI_MANAGER_AP_CONFIG`; `app_main` then only starts `http_config_server` and returns early — it deliberately does **not** also start `http_status_server` in AP mode (both would try to bind port 80 and `httpd_start()` would fail/abort).
3. `ring_buffer` — a lock-free SPSC byte ring buffer in PSRAM (64KB ≈ 2s margin), one writer (`udp_audio_server`'s RX task, core 0) and one reader (`i2s_player`'s playback task, core 1). No mutex by design (single producer/single consumer).
4. `udp_audio_server` parses the custom protocol (`protocol.h`: 16-byte header, `START`/`AUDIO`/`END`/`PING`/`PONG`, sequence numbers), decodes Opus payloads via `opus_decoder_wrapper` (20ms/320-sample frames), and writes PCM into the ring buffer. A new `START` interrupts whatever stream is currently playing (`ring_buffer_reset`) — the newest alarm always wins. Lost frames (sequence gaps) are filled via Opus PLC (packet-loss concealment), not silence.
5. `i2s_player`'s playback task reads fixed 640-byte blocks from the ring buffer and writes them to the codec; on underrun it writes silence rather than blocking, so the I2S clock never stalls.
6. `http_status_server` (STA mode only) exposes `GET /status` (firmware version, IP, MAC, RSSI, `idle`/`streaming` state — driven by `udp_audio_server_is_streaming()`, not buffer occupancy — volume, timestamps, uptime) and `POST /volume`. `time_sync` provides the timestamps via SNTP (`pool.ntp.org`, Europe/Madrid TZ).
7. `nvs_config` / `volume_storage` persist WiFi credentials + optional static IP + `speaker_id`, and the volume level, in NVS namespace `ipspk_cfg`.

**Known hardware-specific gotchas** (see `docs/hardware_pins.md` for the full pinout, sourced from Waveshare's official `factory_01` demo, not guessed):
- `PA_CTRL` is TCA9555 `EXIO08`, not a raw GPIO.
- The Opus decoder needs ~10KB of task stack (`udp_rx_task`) — 4KB (fine for raw PCM) causes a silent stack-overflow reboot once Opus decoding is added.
- The default single-app partition (1MB) fills up almost entirely once Opus is linked in; the project uses a custom `partitions.csv` with a 4MB app partition.
- PSRAM must be Octal mode (`CONFIG_SPIRAM_MODE_OCT`), not the Kconfig default Quad — this board's PSRAM chip is Octal-SPI.

**Protocol reference** for anything sending audio to the firmware: see `main/protocol.h` and the working reference sender `docker/reference_send_audio.py` (handles header packing, Opus encoding, and — important — an initial ~300ms unpaced lead-buffer before real-time pacing kicks in; sending strictly in real-time lockstep with no lead produces audible micro-dropouts from ordinary network jitter).

## Roadmap / issue tracking

Development is tracked as sequential milestones ("Hitos"), each with a corresponding closed GitHub issue in `alexbogus/esp32s3-ip-speaker-net` (issues #1–#6, all closed as of the last session): hardware pin discovery → WiFi/UDP/raw-PCM MVP → HTTP status/volume API → framed protocol with loss detection → Opus + PLC → AP config portal + NVS. New work should follow the same pattern: open a milestone issue, implement, validate on real hardware (this project has no CI/simulator — every milestone so far was verified by flashing and listening), close with `Closes #N` in the commit message.
