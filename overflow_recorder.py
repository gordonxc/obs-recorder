"""
Overflow Recorder
==================
Starts a local recording when a live stream nears YouTube's 12-hour
archive retention limit, so the portion of the stream that YouTube
would otherwise discard is preserved locally.

Author: Gordon
Version: 1.0.0
License: MIT
URL: https://github.com/gordonxc/obs-recorder
"""

import os
import time
import json
import traceback

# obspython is provided by OBS at runtime — not installable via pip.
import obspython as obs  # type: ignore[import-not-found]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCRIPT_NAME = "Overflow Recorder"
SCRIPT_VERSION = "1.0.0"

DEFAULT_THRESHOLD_MINUTES = 715  # 11h55m — 5 min safety margin under 12h
POLL_INTERVAL_MS = 30_000       # 30 seconds
STATE_FILENAME = "overflow_recorder_state.json"

# ---------------------------------------------------------------------------
# Module state
# ---------------------------------------------------------------------------

# Settings (updated via script_update)
g_enabled = True
g_threshold_minutes = DEFAULT_THRESHOLD_MINUTES
g_threshold_seconds = DEFAULT_THRESHOLD_MINUTES * 60

# Runtime state
g_stream_started_at = None        # monotonic seconds, or None
g_we_started_recording = False    # did *we* call recording_start()?
g_attempted_and_failed = False    # recording_start() threw; don't retry
g_poll_suspended = False          # unhandled exception; stop polling


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def log(msg):
    print("[{}] {}".format(SCRIPT_NAME, msg))


# ---------------------------------------------------------------------------
# State file persistence
# ---------------------------------------------------------------------------


def state_file_path():
    # Directory of the script itself is the most reliable writable spot
    # and survives OBS upgrades/profile switches.
    try:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            STATE_FILENAME)
    except Exception:
        return STATE_FILENAME


def write_state_file():
    if g_stream_started_at is None:
        return
    try:
        with open(state_file_path(), "w") as f:
            json.dump({
                "stream_started_monotonic": g_stream_started_at,
                "we_started_recording": g_we_started_recording,
                "written_at_wall": time.time(),
            }, f)
    except Exception as e:
        log("WARN: could not write state file: {}".format(e))


def clear_state_file():
    try:
        p = state_file_path()
        if os.path.exists(p):
            os.remove(p)
    except Exception as e:
        log("WARN: could not remove state file: {}".format(e))


def load_state_if_streaming():
    """On script load: try to recover overflow state if OBS is streaming."""
    global g_stream_started_at, g_we_started_recording

    try:
        streaming_now = obs.obs_frontend_streaming_active()
    except Exception as e:
        log("WARN: could not query streaming state on load: {}".format(e))
        return

    p = state_file_path()

    if not streaming_now:
        if os.path.exists(p):
            log("OBS not streaming; discarding stale state file.")
            clear_state_file()
        return

    if not os.path.exists(p):
        log("Streaming is active but no state file was found. "
            "Overflow protection cannot engage for this stream "
            "(start time unknown).")
        return

    try:
        with open(p) as f:
            data = json.load(f)
    except Exception as e:
        log("WARN: could not parse state file ({}); ignoring.".format(e))
        clear_state_file()
        return

    saved_mono = data.get("stream_started_monotonic")
    saved_we_started = bool(data.get("we_started_recording", False))

    if saved_mono is None:
        log("State file present but start time missing; ignoring.")
        clear_state_file()
        return

    now_mono = time.monotonic()
    if saved_mono > now_mono:
        # System rebooted (monotonic clock reset), or clock otherwise invalid.
        log("State file's start time is in the future relative to current "
            "monotonic clock (likely a reboot). Cannot recover; ignoring.")
        clear_state_file()
        return

    g_stream_started_at = saved_mono
    g_we_started_recording = saved_we_started
    elapsed = now_mono - saved_mono
    log("Recovered state across reload: elapsed so far={}, "
        "recording-started-by-us={}.".format(
            fmt_elapsed(elapsed), g_we_started_recording))


# ---------------------------------------------------------------------------
# Pure logic (testable without OBS)
# ---------------------------------------------------------------------------


def should_start_recording(stream_started_at, now, threshold_seconds):
    if stream_started_at is None:
        return False
    return (now - stream_started_at) >= threshold_seconds


def fmt_elapsed(seconds):
    if seconds is None or seconds < 0:
        return "?"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return "{}h{:02d}m{:02d}s".format(h, m, s)


# ---------------------------------------------------------------------------
# OBS frontend callbacks
# ---------------------------------------------------------------------------


def on_frontend_event(event):
    global g_stream_started_at, g_we_started_recording, g_attempted_and_failed

    if event == obs.OBS_FRONTEND_EVENT_STREAMING_STARTED:
        g_stream_started_at = time.monotonic()
        g_we_started_recording = False
        g_attempted_and_failed = False
        write_state_file()
        threshold_local = time.strftime(
            "%H:%M:%S",
            time.localtime(g_stream_started_at + g_threshold_seconds),
        )
        log("Stream started. Threshold at +{} (wall clock ~{}).".format(
            fmt_elapsed(g_threshold_seconds), threshold_local))

    elif event == obs.OBS_FRONTEND_EVENT_STREAMING_STOPPED:
        if g_we_started_recording:
            try:
                obs.obs_frontend_recording_stop()
                log("Stream stopped; stopping overflow recording.")
            except Exception as e:
                log("WARN: failed to stop recording on stream stop: {}".format(e))
        else:
            log("Stream stopped; no overflow recording to stop.")
        g_stream_started_at = None
        g_we_started_recording = False
        g_attempted_and_failed = False
        clear_state_file()

    elif event == obs.OBS_FRONTEND_EVENT_RECORDING_STOPPED:
        # If we started the recording but the stream is still going,
        # the user stopped it manually. Respect that; don't restart.
        if g_we_started_recording and g_stream_started_at is not None:
            log("Overflow recording stopped by user; respecting and "
                "will not restart this stream.")
            g_we_started_recording = False
            write_state_file()


def poll():
    """Periodic threshold check."""
    global g_we_started_recording, g_attempted_and_failed, g_poll_suspended

    if g_poll_suspended:
        return
    if not g_enabled:
        return
    if g_stream_started_at is None:
        return
    if g_we_started_recording or g_attempted_and_failed:
        return

    try:
        now = time.monotonic()
        if not should_start_recording(g_stream_started_at, now,
                                      g_threshold_seconds):
            return

        if obs.obs_frontend_recording_active():
            # Already recording (user-initiated). Don't disrupt; don't
            # spam the log every poll.
            log("Threshold reached but recording is already active; "
                "not disrupting existing recording.")
            g_attempted_and_failed = True
            return

        try:
            obs.obs_frontend_recording_start()
            g_we_started_recording = True
            write_state_file()
            log("Threshold reached after {}; started overflow recording.".format(
                fmt_elapsed(now - g_stream_started_at)))
        except Exception as e:
            g_attempted_and_failed = True
            log("FAILED to start overflow recording: {} "
                "(will not retry this stream).".format(e))
            log(traceback.format_exc())

    except Exception as e:
        g_poll_suspended = True
        log("ERROR: unhandled exception in poll, suspending polling for "
            "this session: {}".format(e))
        log(traceback.format_exc())


# ---------------------------------------------------------------------------
# OBS script lifecycle
# ---------------------------------------------------------------------------


def script_description():
    return (
        "<h2>Overflow Recorder v{ver}</h2>"
        "<p>Starts a local recording when your live stream nears "
        "YouTube's 12-hour archive retention limit, so the portion "
        "YouTube would otherwise discard is preserved locally.</p>"
        "<p>Default threshold: 715 minutes (11h55m), giving a 5-minute "
        "safety margin under YouTube's 12-hour cap. Set to a small "
        "value (e.g. 1) for testing.</p>"
        "<p><b>License:</b> MIT &middot; <b>URL:</b> "
        "<a href='https://github.com/gordonxc/obs-recorder'>"
        "github.com/gordonxc/obs-recorder</a></p>"
    ).format(ver=SCRIPT_VERSION)


def script_defaults(settings):
    obs.obs_data_set_default_bool(settings, "enabled", True)
    obs.obs_data_set_default_int(settings, "threshold_minutes",
                                 DEFAULT_THRESHOLD_MINUTES)


def script_properties():
    props = obs.obs_properties_create()
    obs.obs_properties_add_bool(props, "enabled", "Enabled")

    p = obs.obs_properties_add_int(
        props, "threshold_minutes",
        "Threshold (minutes of stream uptime)",
        0, 24 * 60, 1)
    obs.obs_property_set_long_description(
        p,
        "Stream uptime at which to start a local recording. "
        "Default 715 (= 11h55m, a 5-minute safety margin under "
        "YouTube's 12-hour archive cap). Set to 1 for testing.")
    return props


def script_update(settings):
    global g_enabled, g_threshold_minutes, g_threshold_seconds
    g_enabled = obs.obs_data_get_bool(settings, "enabled")
    g_threshold_minutes = obs.obs_data_get_int(settings, "threshold_minutes")
    g_threshold_seconds = g_threshold_minutes * 60
    log("Settings updated: enabled={}, threshold_minutes={}".format(
        g_enabled, g_threshold_minutes))


def script_load(_settings):  # type: ignore[unused-parameter]
    # Signature requires a settings arg per OBS; we don't use it on load.
    log("Loading {} v{}".format(SCRIPT_NAME, SCRIPT_VERSION))
    obs.obs_frontend_add_event_callback(on_frontend_event)
    obs.timer_add(poll, POLL_INTERVAL_MS)
    load_state_if_streaming()


def script_unload():
    log("Unloading {}.".format(SCRIPT_NAME))
    try:
        obs.timer_remove(poll)
    except Exception:
        pass
