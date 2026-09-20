# ARMOR: Automated Remote Monitoring & Operational Recovery
ARMOR is a lightweight, cross-platform infrastructure monitoring and remote recovery framework designed for home labs. It utilizes an externalized "Dead Man's Switch" architecture to achieve zero-footprint offline detection on headless nodes, while providing deep OS-level control via a unified Telegram bot interface.

## Architecture
* **Edge Controller (OpenWrt):** Asus RT-AC2600 (flashed as RT-AC85P). Handles local network ping monitoring, Wake-on-LAN (WOL), and SSH lock-files.
* **Endpoint Agents (Python):** Headless Debian (`psth1`) and Mac Mini (`pstt1`). Run a bare-metal Python daemon for telemetry push, threshold watchdog, and Telegram command execution.

## Documentation
* [Requirements](docs/REQUIREMENTS.md)
* [System Design](docs/DESIGN.md)
* [Installation Guide](docs/INSTALLATION.md)
* [Operation Guide](docs/OPERATION.md)
