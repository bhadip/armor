#!/bin/bash
cd "$(dirname "$0")"
echo "🔄 Syncing ARMOR..."

# 1. Fetch Edge script from AC-2600 (if running on psth1)
if [ "$(whoami)" = "root" ] && [ -d "/root/armor/edge" ]; then
    echo "📥 Fetching Edge script from AC-2600..."
    # Using 'cat' over SSH bypasses OpenWrt's missing sftp-server issue
    ssh root@192.168.50.4 "cat /root/armor-edge/offline_check.sh" > edge/offline_check.sh
    if [ $? -eq 0 ]; then
        echo "✅ Edge script fetched successfully."
    else
        echo "⚠️ Failed to fetch Edge script. Check router connectivity."
    fi
fi

# 2. Stage and commit any local changes first
git add .
if ! git diff --staged --quiet; then
    echo "💾 Committing local changes..."
    git commit -m "sync: auto-commit local changes $(date +%F)"
fi

# 3. Stash any remaining uncommitted changes to prevent merge conflicts
echo "📦 Stashing uncommitted changes (if any)..."
git stash push -m "auto-stash before sync" >/dev/null 2>&1

# 4. Pull remote changes (rebase keeps history clean)
echo "📥 Pulling from GitHub..."
git pull --rebase origin main

# 5. Restore stashed changes (if any existed)
git stash pop >/dev/null 2>&1

# 6. Push to GitHub
echo "📤 Pushing to GitHub..."
git push origin main

echo "✅ Sync Complete!"
