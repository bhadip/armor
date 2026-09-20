# Operation Guide
## Telegram Commands
* `/status` - Returns CPU, RAM, Disk, and Uptime.
* `/top` - Returns top 5 processes with inline `[Kill]` buttons.
* `/pause` - SSHes into the Edge Controller to create a lock file (suppresses offline alerts).
* `/resume` - Removes the lock file.
* `/sleep` - Creates lock file, then executes OS-level sleep command.

## Alert Lifecycle
1. **Trigger:** Metric exceeds 90% or node goes offline. Telegram alert is sent.
2. **Acknowledge (Threshold only):** Click the `[Acknowledge]` button. The bot will stop reminding you every 5 minutes.
3. **Resolve:** When the metric drops below 90% or the node pings successfully, a "Resolved" or "BACK ONLINE" message is sent, resetting the state.

## Maintenance
* **Update Agent:** `cd /root/armor && git pull && systemctl restart armor`
* **Update Edge:** `ssh root@192.168.50.4`, pull changes to `/root/armor-edge`, restart cron.
* **Logs:** `journalctl -u armor -f`
