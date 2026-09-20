# Requirements Document
## 1. Functional Requirements
1. **Offline Detection:** The system must detect when an endpoint is offline without relying on the endpoint's own software (Dead Man's Switch).
2. **State-Change Alerts:** Alerts must only trigger on transitions (Online ↔ Offline) to prevent message spam.
3. **Threshold Watchdog:** The agent must push Telegram alerts if CPU, RAM, or Disk usage exceeds 90%.
4. **Alert Acknowledgment:** Threshold alerts must repeat every 5 minutes until acknowledged via an inline Telegram button. Once acknowledged, they stay silent until the metric resolves.
5. **Remote Power Control:** The system must support Wake-on-LAN (WOL) for supported hardware, and software sleep/shutdown/restart for all nodes.
6. **Intentional Sleep Handling:** When a node is commanded to sleep via Telegram, it must signal the Edge Controller to suppress offline alerts.
7. **Process Management:** The agent must list top CPU/RAM consuming processes and allow remote killing via inline buttons.

## 2. Non-Functional Requirements
1. **Zero Footprint:** The Edge Controller must consume <5% CPU and <10MB RAM.
2. **No Docker:** Agents must run as native bare-metal system services (`systemd`/`launchd`) to maintain OS-level hardware control.
3. **Security:** All secrets (Telegram tokens, SSH keys) must be stored in `.env` files and excluded from version control via `.gitignore`.
