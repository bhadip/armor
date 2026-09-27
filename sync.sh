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
