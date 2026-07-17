# Overflow Recorder

An [OBS Studio](https://obsproject.com/) Python script that starts a local
recording when your live stream nears **YouTube's 12-hour archive retention
limit**, so the portion of the stream YouTube would otherwise discard is
preserved locally.

## Why

YouTube Live's auto-generated archive caps at **12 hours**. If you stream
longer than that, anything past 12h is silently lost on YouTube's side.
Combine YouTube's archive (0–12h) with this script's local recording
(11h55m+) and you have the full stream on disk for editing or re-upload.

The script starts the local recording a few minutes *before* the 12h mark
(default 11h55m, configurable) to avoid losing the boundary second.

## Requirements

- OBS Studio 30+ (Python scripting is built into OBS).
- The OBS Python scripting engine enabled, pointed at a Python 3.11 install.
  See **Python setup** below — this step varies by OS.

## Install

1. Download `overflow_recorder.py` (or clone this repo).
2. In OBS: **Tools → Scripts**.
3. On the **Scripts** tab, click **+** and choose `overflow_recorder.py`.
4. Switch to the **Script Properties** tab (with the script selected) and
   confirm:
   - **Enabled** is checked.
   - **Threshold (minutes)** is `715` (= 11h55m). Set to `1` for a quick
     end-to-end test (see **Testing** below).
5. Click the **Script Log** button to see what the script is doing.

## Python setup

OBS Python scripts need a Python 3.11 interpreter that OBS can find. The
config lives at **Tools → Settings → Advanced → Python** (or
**Tools → Scripts → Python Settings** in some versions).

### macOS

OBS does not bundle Python. Install Python 3.11 and point OBS at it:

```sh
brew install python@3.11
```

Then set OBS's Python path to
`/opt/homebrew/opt/python@3.11/Frameworks/Python.framework/Versions/3.11`
(Apple Silicon) or
`/usr/local/opt/python@3.11/Frameworks/Python.framework/Versions/3.11`
(Intel). The directory must contain a `Python` executable inside `bin/`.

### Windows

Recent OBS versions on Windows bundle a Python interpreter. If **Python
Settings** is grayed out or shows an error, install
[Python 3.11](https://www.python.org/downloads/release/python-3110/) and
point OBS at its install directory.

### Linux

Use your distro's Python 3.11 (e.g. `python3.11` on Debian/Ubuntu). Set
OBS's Python path to the directory containing `python3.11`.

## Configuration

| Setting | Default | Description |
|---|---|---|
| Enabled | on | Master toggle. Turn off without unloading the script. |
| Threshold (minutes) | 715 | Stream uptime at which to start a local recording. 715 = 11h55m. Set to `1` for testing. |

## Behavior

- **On stream start** — records the start time using a monotonic clock
  (immune to system clock drift / NTP adjustments).
- **Every 30 seconds** — checks stream uptime; when uptime ≥ threshold,
  starts a local recording via `obs_frontend_recording_start()`.
  - If a recording is *already* running (e.g. you record locally from t=0),
    the script leaves it alone.
- **If you stop the recording manually** mid-overflow, the script respects
  that and will not restart it for the rest of the stream.
- **On stream stop** — if the script started the recording, it stops it.
  If you started it manually, it's left alone.
- **Crash / reload recovery** — start time is persisted to a small JSON
  file next to the script (`overflow_recorder_state.json`). On reload, if
  OBS reports the stream still active, the script picks up where it left
  off. If OBS is not streaming, the stale file is discarded.

## Testing

Don't wait 12 hours to test this. End-to-end test in ~2 minutes:

1. Set **Threshold (minutes)** to `1`.
2. Start streaming (you can use a throwaway RTMP target if you don't
   want to actually broadcast — e.g. stream to `rtmp://localhost/live`
   with no server running; OBS will still fire the start event).
3. Watch the **Script Log** — you should see:
   - `Stream started. Threshold at +1m0s (wall clock ~HH:MM:SS).`
   - ~60s later: `Threshold reached after 1m0s; started overflow recording.`
   - OBS's recording indicator lights up.
4. Stop the stream. You should see:
   - `Stream stopped; stopping overflow recording.`
5. Reset **Threshold (minutes)** to `715` for real use.

Also worth testing once: while the script is recording, hit OBS's
**Stop Recording** button manually. The log should show
`Overflow recording stopped by user; respecting and will not restart`
and the script should leave recording off for the rest of that stream.

## Troubleshooting

**Where is the script log?**
**Tools → Scripts → Script Log** button (not a tab — a button at the
bottom of the Scripts window).

**The recording didn't start at the threshold.**
Open the script log and look for `FAILED to start overflow recording` or
`ERROR: unhandled exception`. The most common cause is OBS's recording
output being misconfigured (bad output path, no encoder selected). Fix
that in **Settings → Output → Recording**.

**The script didn't survive an OBS restart mid-stream.**
Check the log on next launch for
`Recovered state across reload` or `State file's start time is in the future`.
The latter means the machine rebooted (monotonic clock reset) — the script
gives up rather than guessing wrong.

## Platform support

- **macOS**: tested on macOS 26 (Darwin 25.5.0) with OBS 30+ and
  Python 3.11 via Homebrew.
- **Windows / Linux**: not yet verified by the author. The script uses
  only cross-platform OBS Python APIs (`obspython`), so it *should* work.
  If you hit issues, please file them at
  https://github.com/gordon/obs-recorder/issues.

## License

MIT — see [LICENSE](LICENSE).
