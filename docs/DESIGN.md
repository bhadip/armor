# System Design
## 1. Edge Controller (OpenWrt)
The Edge Controller acts as an external watchdog.
* **State Tracking:** It uses /tmp/ flag files to track node status. It only sends a Telegram message when the state changes.
* **Lock Files:** When the Python agent executes /sleep, it SSHes into the Edge Controller and creates a lock file. The cron job checks for this file and skips the ping check, preventing false alarms.

## 2. Endpoint Agent (Python)
The agent runs as a background daemon and manages two main threads:
1. **Telegram Polling Thread:** Listens for commands and renders inline keyboards.
2. **Watchdog Thread:** Polls psutil metrics every 60 seconds. It maintains an internal state dictionary to track if an alert is active and acked.

## 3. State Management
* **Online -> Offline:** Edge Controller detects ping failure, sends alert, creates flag.
* **Offline -> Online:** Edge Controller detects ping success, sends alert, removes flag.
* **Threshold Alert:** Agent detects >90% metric, sends alert with [Acknowledge] button. Repeats every 5 mins if not acked. Stays silent until resolved.
