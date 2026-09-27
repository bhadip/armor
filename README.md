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

### Headless Linux (Debian/Ubuntu Server) Limitations
Because `psth1` runs without a graphical desktop environment (X11/Wayland) or physical audio/display hardware, the following commands will gracefully return "Not applicable" or "Hardware not available":
- **Visuals:** `/shot`, `/cam` (No display or webcam attached).
- **Audio/Hardware:** `/vol`, `/bright`, `/say` (No soundcards or display backlight control).
- **GUI Management:** `/apps` (No window manager running).
- **Clipboard:** `/clip get`, `/clip set` (System clipboard requires an active GUI session).
