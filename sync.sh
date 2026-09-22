#!/bin/bash
cd "$(dirname "$0")"
echo "🔄 Syncing ARMOR..."

# If running on Debian (psth1), fetch the latest router script via SSH
if [ "$(whoami)" = "root" ] && [ -d "/root/armor/edge" ]; then
    echo "📥 Fetching Edge script from AC-2600..."
    ssh root@192.168.50.4 "cat /root/armor-edge/offline_check.sh" > edge/offline_check.sh
fi

# Stage local changes (if any)
git add .
git diff --staged --quiet || git commit -m "sync: auto-commit local changes $(date +%F)"

# Pull remote changes (rebase keeps history clean)
echo "📥 Pulling from GitHub..."
git pull --rebase origin main

# Push to GitHub
echo "📤 Pushing to GitHub..."
git push origin main

echo "✅ Sync Complete!"
