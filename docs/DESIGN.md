# System Design & Architecture

## 1. Node Roles & Responsibilities

### Edge Controller (AC-2600 / OpenWrt)
- **Role:** Local LAN Watchdog.
- **Function:** Pings local endpoints (\`psth1\`, \`pstt1\`) every 1 minute via cron.
- **Limitation:** It **cannot** reliably monitor the Main Gateway (AX-3000) because if the gateway dies, the AC-2600 loses its internet route and cannot send Telegram alerts.
- **Alerts:** Sends "OFFLINE/ONLINE" alerts only when local devices disappear from the LAN.

### Endpoint Agents (psth1 & pstt1)
- **Role:** Internal Telemetry & External Heartbeat.
- **Internal Watchdog:** Polls local CPU/RAM/Disk metrics every \`N\` seconds (configurable). Alerts via Telegram if thresholds are breached, including impact assessments.
- **External Heartbeat:** Sends a "ping" to **Healthchecks.io** every 1 minute. *(Note: If the Main Gateway fails, the agent cannot reach Healthchecks.io. This effectively monitors the Internet Gateway status without needing extra hardware).*
- **Command Receiver:** Listens for Telegram commands to execute OS-level tasks.

### External Watchdog (Healthchecks.io)
- **Role:** Global Availability Monitor.
- **Function:** Monitors the heartbeats from \`psth1\` and \`pstt1\`.
- **Logic:** If a heartbeat is missing for > 3 minutes (Period + Grace), it assumes the device **OR** the internet connection (AX-3000) is down and triggers a Telegram alert.

## 2. Device Monitoring Matrix

| Device | Hardware / OS | Monitor Method | Limitations / Exceptions |
| :--- | :--- | :--- | :--- |
| **ax-3000** | Main Gateway Router | **Indirect:** Monitored via correlated Healthchecks.io heartbeat failures from \`psth1\` & \`pstt1\`. | Cannot be pinged directly by Edge Controller if it loses internet. |
| **ac-2600** | Edge Controller (OpenWrt) | **Local:** Monitored via LAN ping from \`psth1\` (optional) or by its own ability to send alerts. | If internet dies, it cannot send Telegram alerts (relies on Healthchecks.io fallback). |
| **psth1** | Headless Debian Server | **Dual:** 1. LAN ping by \`ac-2600\`. 2. External heartbeat to Healthchecks.io. | None. Acts as the primary always-on anchor. |
| **pstt1** | Mac Mini (or MacBook) | **Dual:** 1. LAN ping by \`ac-2600\` (when on local network). 2. External heartbeat to Healthchecks.io (always). | macOS LaunchAgent requires a user to be logged in. If the Mac is fully powered off, alerts pause until boot. |

## 3. Data Flow Diagram
1. **Local Failure:** Node stops -> AC-2600 detects ping loss -> **Telegram Alert**.
2. **Internal Overload:** Node CPU > 95% -> Agent detects -> **Telegram Alert** (with Impact/Action guide).
3. **Internet/Gateway Failure:** Node cannot reach Healthchecks.io -> Healthchecks.io detects missing heartbeat -> **Telegram Alert**.
4. **Remote Control:** User sends \`/cam\` -> Telegram -> Agent -> Webcam -> Image sent to User.
