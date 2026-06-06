# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-06-06

### Added

- Core Matrix Client-Server API wrapper (`MatrixClient`)
- `/sync` listener with automatic reconnection and exponential backoff
- Policy engine with 4 levels: lurk, mention-only, important, all
- Anti-echo filtering (ignores bot's own messages)
- Pluggable delivery backends: stdout, webhook, exec
- CLI: `matrixd whoami`, `send`, `rooms`, `listen`, `serve`, `version`
- JSONC configuration with env var interpolation
- Vendored zerodep modules: `httpclient` (HTTP client), `jsonc` (config parser)
- Zero runtime dependencies — pure stdlib + vendored modules
- Pre-commit CI: ruff, ty, complexipy (excluding `_vendor/`)
- GitHub Actions CI with Python 3.10–3.13 test matrix

[0.1.0]: https://github.com/Oaklight/matrixd/releases/tag/v0.1.0
