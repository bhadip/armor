# Installation Guide
## Phase 1: Edge Controller (AC2600)
1. **Flash OpenWrt:** Download the asus_rt-ac85p-squashfs-factory.bin image. Flash via ASUS Rescue Mode (Static IP 192.168.1.10, hold Reset on boot).
2. **Network Config:** Set LAN IP to 192.168.50.4, Gateway to 192.168.50.1, disable DHCP.
3. **Deploy Scripts:** SSH into the router, create /root/armor-edge/.env with Telegram tokens, and deploy offline_check.sh.
4. **Cron:** Add */5 * * * * /root/armor-edge/offline_check.sh to /etc/crontabs/root.

## Phase 2: Endpoint Agent (Debian/Mac)
1. **Clone Repo:** git clone git@github.com:bhadip/armor.git /root/armor
2. **Environment:** Create .env in agent/ with Telegram tokens and OpenWrt IP.
3. **SSH Trust:** Run ssh-copy-id root@192.168.50.4 to allow the agent to manage router lock files.
4. **Install:** Create venv, install requirements.txt.
5. **Daemonize:** Copy agent/armor.service to /etc/systemd/system/, run systemctl enable --now armor.
