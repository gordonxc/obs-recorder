# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-07-17

### Added
- Initial release.
- Starts a local recording when stream uptime reaches the configured
  threshold (default 715 minutes = 11h55m, a 5-minute safety margin
  under YouTube's 12-hour archive cap).
- Stops the recording when streaming stops (only if the script
  started it; respects user-initiated stops).
- Persists state across OBS restarts and script reloads so protection
  survives a crash mid-stream.
- Script properties panel with `Enabled` toggle and `Threshold (minutes)`
  field.
- Logs all state transitions to the OBS script log.
