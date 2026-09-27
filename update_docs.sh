#!/bin/bash
cd "$(dirname "$0")"

echo "📝 Updating Documentation..."

# 1. Create docs directory if it doesn't exist
mkdir -p docs

# 2. Write comprehensive README.md
cat << 'README' > README.md
# 🛡️ ARMOR (Autonomous Remote Monitoring & Operations Resource)

A lightweight, self-hosted Telegram bot agent for monitoring and controlling Linux and macOS devices. Designed for zero-footprint, decoupled home lab infrastructure.

## 🌟 Key Features
- **Real-time Monitoring:** CPU, RAM, Disk, and GPU (Linux) usage with multi-tier alerts (Warning/Critical).
- **External Heartbeat:** Integrated with Healthchecks.io to detect internet/gateway outages.
- **Remote Control:** Full OS control via Telegram (Screenshots, Webcam, Volume, Brightness, Process Killing, App Management).
- **Smart Context:** Alerts include ISP geolocation, public IP, and actionable recommendations.
- **Cross-Platform:** Identical codebase runs on Debian/Ubuntu and macOS (Apple Silicon & Intel).

## 💻 Compatibility & Supported Environments
The ARMOR Python Agent requires **zero code changes** on any modern OS meeting these baselines: Python 3.8+ and standard POSIX utilities.

### Fully Supported Out-of-the-Box
- **Linux:** Debian, Ubuntu, RHEL, Rocky Linux, AlmaLinux, Fedora, Arch Linux, openSUSE.
- **macOS:** Apple Silicon (M1/M2/M3/M4) and Intel (x86_64) running macOS 11 (Big Sur) or newer.

### Known Caveats
1. **Power Commands:** `/sleep` and `/reboot` rely on `systemctl`. On non-systemd Linux (e.g., Alpine), these return a harmless error, but monitoring remains fully functional.
2. **macOS Background Execution:** The macOS agent runs as a user-level `LaunchAgent`. It requires an active user session. If the Mac is fully shut down or logged out, the agent pauses until the next login.
3. **Headless Linux:** Commands requiring a GUI (`/shot`, `/cam`, `/clip`, `/vol`, `/bright`) will gracefully return "Hardware not available or missing tools" on pure CLI servers.
4. **Router Alerts:** The Edge Controller (OpenWrt) cannot send Telegram alerts if the main internet gateway fails, as it loses its default route. This is intentionally mitigated by the external Healthchecks.io heartbeat.

## 📋 Available Commands
Use the Telegram menu (type `/` in the chat) to see all available commands, including `/status`, `/top`, `/sysinfo`, `/apps`, `/shot`, `/cam`, `/vol`, `/bright`, `/battery`, `/netinfo`, `/media`, `/say`, `/clip`, `/shortcut`, `/thresholds`, `/setcpu`, `/setram`, `/setdisk`, `/setgpu`, `/interval`, `/pause`, `/resume`, and `/sleep`.

## 🔄 Syncing Changes
To safely sync local changes with GitHub without merge conflicts:
\`\`\`bash
./sync.sh
\`\`\`
README

# 3. Write comprehensive docs/DESIGN.md
cat << 'DESIGN' > docs/DESIGN.md
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
DESIGN

# 4. Update sync.sh to be conflict-proof
cat << 'SYNC' > sync.sh
#!/bin/bash
cd "\$(dirname "\$0")"
echo "🔄 Syncing ARMOR..."

# If running on Debian (psth1), fetch the latest router script via SSH
if [ "\$(whoami)" = "root" ] && [ -d "/root/armor/edge" ]; then
    echo "📥 Fetching Edge script from AC-2600..."
    ssh root@192.168.50.4 "cat /root/armor-edge/offline_check.sh" > edge/offline_check.sh 2>/dev/null || echo "⚠️ Could not fetch edge script (SSH failed)"
fi

# Stash any uncommitted local changes to prevent merge conflicts
git stash push -m "auto-stash before sync" >/dev/null 2>&1

# Pull remote changes
echo "📥 Pulling from GitHub..."
git pull --rebase origin main

# If there were stashed changes, try to apply them (optional, usually we want remote to win for canonical files)
git stash pop >/dev/null 2>&1 || true

# Push to GitHub
echo "📤 Pushing to GitHub..."
git push origin main

echo "✅ Sync Complete!"
SYNC

chmod +x sync.sh

echo "✅ Documentation and sync.sh updated successfully!"
