import pathlib, os

p_main = pathlib.Path(os.path.expanduser('~/armor/agent/src/main.py'))
p_adapter = pathlib.Path(os.path.expanduser('~/armor/agent/src/os_adapter.py'))

# ==========================================
# 1. Patch os_adapter.py
# ==========================================
adapter_code = p_adapter.read_text()

# Fix 1: Uptime formatting (y m d h m s)
old_uptime = """        uptime_secs = int(time.time() - psutil.boot_time())
        hours, remainder = divmod(uptime_secs, 3600)
        mins, secs = divmod(remainder, 60)
        return {"cpu": cpu, "ram": ram, "disk": disk, "uptime": f"{hours}h {mins}m {secs}s"}"""

new_uptime = """        uptime_secs = int(time.time() - psutil.boot_time())
        years = uptime_secs // (365 * 24 * 3600)
        uptime_secs %= (365 * 24 * 3600)
        months = uptime_secs // (30 * 24 * 3600)
        uptime_secs %= (30 * 24 * 3600)
        days = uptime_secs // (24 * 3600)
        uptime_secs %= (24 * 3600)
        hours = uptime_secs // 3600
        uptime_secs %= 3600
        mins = uptime_secs // 60
        secs = uptime_secs % 60
        parts = []
        if years > 0: parts.append(f"{years}y")
        if months > 0: parts.append(f"{months}m")
        if days > 0: parts.append(f"{days}d")
        if hours > 0: parts.append(f"{hours}h")
        if mins > 0: parts.append(f"{mins}m")
        parts.append(f"{secs}s")
        return {"cpu": cpu, "ram": ram, "disk": disk, "uptime": " ".join(parts)}"""
adapter_code = adapter_code.replace(old_uptime, new_uptime)

# Fix 2: Robust /sysinfo for Linux
old_sysinfo_linux = """        else:
            ok1, cpu_raw, _ = _run(["grep", "-m1", "model name", "/proc/cpuinfo"])
            cpu = cpu_raw.split(":")[1].strip() if ok1 else "Unknown"
            ok2, ram_raw, _ = _run(["free", "-h"])
            ram = ram_raw.split("\\n")[1].split()[1] if ok2 else "Unknown"
            return f"CPU: {cpu}\\nRAM: {ram}"""
            
new_sysinfo_linux = """        else:
            cpu = "Unknown"
            try:
                with open("/proc/cpuinfo", "r") as f:
                    for line in f:
                        if "model name" in line:
                            cpu = line.split(":")[1].strip()
                            break
            except: pass
            ram = "Unknown"
            try:
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        if "MemTotal" in line:
                            kb = int(line.split()[1])
                            ram = f"{round(kb / 1024 / 1024, 1)} GB"
                            break
            except: pass
            return f"CPU: {cpu}\\nRAM: {ram}"""
adapter_code = adapter_code.replace(old_sysinfo_linux, new_sysinfo_linux)

# Fix 3: /apps headless detection
old_get_apps_linux = """        else:
            ok, out, err = _run(["wmctrl", "-l"], timeout=5)
            if ok: return [line.split(None, 2)[2] for line in out.splitlines() if line]
            return ["wmctrl not installed or no X11"]"""
            
new_get_apps_linux = """        else:
            if not os.environ.get("DISPLAY"):
                return ["Not applicable (Headless Linux has no active GUI session)"]
            ok, out, err = _run(["wmctrl", "-l"], timeout=5)
            if ok and out.strip(): return [line.split(None, 2)[2] for line in out.splitlines() if line]
            return ["No GUI apps running or wmctrl not installed"]"""
adapter_code = adapter_code.replace(old_get_apps_linux, new_get_apps_linux)

# Fix 6: /clip headless detection
old_clip_get = """    def get_clipboard(self):
        cmd = ["pbpaste"] if self.is_mac else ["xclip", "-selection", "clipboard", "-o"]
        ok, out, err = _run(cmd, timeout=3)
        return out if ok else "(Empty or requires X11/Wayland session)""""
        
new_clip_get = """    def get_clipboard(self):
        if not self.is_mac and not os.environ.get("DISPLAY"):
            return "Headless_NoX11"
        cmd = ["pbpaste"] if self.is_mac else ["xclip", "-selection", "clipboard", "-o"]
        ok, out, err = _run(cmd, timeout=3)
        return out if ok else "Headless_NoX11""""
adapter_code = adapter_code.replace(old_clip_get, new_clip_get)

old_clip_set = """    def set_clipboard(self, text):
        cmd = ["pbcopy"] if self.is_mac else ["xclip", "-selection", "clipboard"]
        try: 
            subprocess.run(cmd, input=text.encode(), check=True, timeout=3)
            return True
        except: 
            return False"""
            
new_clip_set = """    def set_clipboard(self, text):
        if not self.is_mac and not os.environ.get("DISPLAY"):
            return False
        cmd = ["pbcopy"] if self.is_mac else ["xclip", "-selection", "clipboard"]
        try: 
            subprocess.run(cmd, input=text.encode(), check=True, timeout=3)
            return True
        except: 
            return False"""
adapter_code = adapter_code.replace(old_clip_set, new_clip_set)

p_adapter.write_text(adapter_code)

# ==========================================
# 2. Patch main.py
# ==========================================
main_code = p_main.read_text()

# Fix 5: /media requires parameter
old_media = """async def media_cmd(u, c):
    action = u.message.text.split()[1] if len(u.message.text.split()) > 1 else "play"
    adapter.media_control(action)
    await u.message.reply_text("🎵 Media: " + action)"""
    
new_media = """async def media_cmd(u, c):
    args = u.message.text.split()
    action = args[1] if len(args) > 1 else ""
    if not action:
        await u.message.reply_text("Usage: /media <play|pause|next|prev>")
        return
    if adapter.media_control(action):
        await u.message.reply_text("🎵 Media: " + action)
    else:
        await u.message.reply_text("❌ Not applicable to this OS setting (No media player active).")"""
main_code = main_code.replace(old_media, new_media)

# Fix 6: /clip meaningful response
old_clip_cmd = """async def clip_cmd(u, c):
    args = u.message.text.split(maxsplit=1)
    if len(args) < 2 or args[1].startswith("get"):
        clip_text = adapter.get_clipboard()
        if "requires X11" in clip_text:
            await u.message.reply_text("❌ Not applicable to this OS setting (Headless Linux has no active GUI clipboard).")
        else:
            await u.message.reply_text("📋 Clipboard:\\n`" + clip_text + "`", parse_mode="Markdown")
    elif args[1].startswith("set "):
        if adapter.set_clipboard(args[1][4:]):
            await u.message.reply_text("✅ Copied to clipboard.")
        else:
            await u.message.reply_text("❌ Not applicable to this OS setting (Headless Linux has no active GUI clipboard).")"""
            
new_clip_cmd = """async def clip_cmd(u, c):
    args = u.message.text.split(maxsplit=1)
    if len(args) < 2 or args[1].startswith("get"):
        clip_text = adapter.get_clipboard()
        if clip_text == "Headless_NoX11":
            await u.message.reply_text("❌ Not applicable to this OS setting (Headless Linux has no active GUI clipboard).")
        else:
            await u.message.reply_text("📋 Clipboard:\\n`" + (clip_text if clip_text else "(Empty)") + "`", parse_mode="Markdown")
    elif args[1].startswith("set "):
        if adapter.set_clipboard(args[1][4:]):
            await u.message.reply_text("✅ Copied to clipboard.")
        else:
            await u.message.reply_text("❌ Not applicable to this OS setting (Headless Linux has no active GUI clipboard).")"""
main_code = main_code.replace(old_clip_cmd, new_clip_cmd)

# Fix 7: /pause & /resume with timeout to prevent hanging
old_pause = """async def pause(u, c):
    subprocess.run(["ssh", OPENWRT_USER + "@" + OPENWRT_IP, "touch /tmp/" + HOSTNAME + "_paused"])
    await u.message.reply_text("⏸ Offline monitoring paused.")"""
new_pause = """async def pause(u, c):
    try:
        subprocess.run(["ssh", "-o", "ConnectTimeout=3", f"{OPENWRT_USER}@{OPENWRT_IP}", f"touch /tmp/{HOSTNAME}_paused"], timeout=5, check=True)
        await u.message.reply_text("⏸ Offline monitoring paused.")
    except Exception:
        await u.message.reply_text("❌ Failed to contact router. Is it online?")"""
main_code = main_code.replace(old_pause, new_pause)

old_resume = """async def resume(u, c):
    subprocess.run(["ssh", OPENWRT_USER + "@" + OPENWRT_IP, "rm -f /tmp/" + HOSTNAME + "_paused"])
    await u.message.reply_text("▶️ Offline monitoring resumed.")"""
new_resume = """async def resume(u, c):
    try:
        subprocess.run(["ssh", "-o", "ConnectTimeout=3", f"{OPENWRT_USER}@{OPENWRT_IP}", f"rm -f /tmp/{HOSTNAME}_paused"], timeout=5, check=True)
        await u.message.reply_text("▶️ Offline monitoring resumed.")
    except Exception:
        await u.message.reply_text("❌ Failed to contact router. Is it online?")"""
main_code = main_code.replace(old_resume, new_resume)

# Fix 7b: Add /threshold as an alias for /thresholds
if 'CommandHandler("threshold", thresholds_cmd)' not in main_code:
    main_code = main_code.replace('app.add_handler(CommandHandler("thresholds", thresholds_cmd))', 
                                  'app.add_handler(CommandHandler("thresholds", thresholds_cmd))\n    app.add_handler(CommandHandler("threshold", thresholds_cmd))')

# Verify and save
try:
    compile(main_code, 'main.py', 'exec')
    p_main.write_text(main_code)
    print("✅ All 7 issues patched successfully!")
except SyntaxError as e:
    print(f"❌ Syntax error: {e}")
