#!/bin/bash
echo "=== 1. Checking if os_adapter.py was updated ==="
grep -c "tailscale dns status" /root/armor/agent/src/os_adapter.py
if [ $? -eq 0 ]; then
    echo "✅ File contains the new tailscale logic."
else
    echo "❌ File DOES NOT contain the new logic. The update failed."
fi

echo ""
echo "=== 2. Testing 'tailscale dns status' manually ==="
tailscale dns status 2>&1 | grep -A 10 "=== System DNS configuration ==="

echo ""
echo "=== 3. Testing /etc/resolv.conf manually ==="
cat /etc/resolv.conf

echo ""
echo "=== 4. Testing Python parsing directly ==="
python3 << 'PYEOF'
import subprocess

try:
    res = subprocess.run(["tailscale", "dns", "status"], capture_output=True, text=True, timeout=5).stdout
    in_system = False
    nameservers = []
    for line in res.split('\n'):
        if "=== System DNS configuration ===" in line:
            in_system = True
        elif in_system and line.strip().startswith("- "):
            ip = line.strip()[2:].strip()
            if not ip.startswith("100.") and not ip.startswith("127.") and not ip.startswith("fd7a:"):
                nameservers.append(ip)
        elif in_system and line.startswith("==="):
            break
    if nameservers:
        print("✅ Python found DNS:", " ".join(nameservers))
    else:
        print("❌ Python found NO valid DNS in tailscale output.")
except Exception as e:
    print("❌ Python error:", e)
PYEOF
