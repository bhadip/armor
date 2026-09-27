import os, sys, json, time, psutil, platform, subprocess

def _run(cmd, timeout=5):
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return res.returncode == 0, res.stdout.strip(), res.stderr.strip()
    except Exception as e:
        return False, "", str(e)

class OSAdapter:
    def __init__(self):
        self.is_mac = platform.system() == "Darwin"

    def get_status(self):
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent
        uptime_secs = int(time.time() - psutil.boot_time())
        hours, remainder = divmod(uptime_secs, 3600)
        mins, secs = divmod(remainder, 60)
        return {"cpu": cpu, "ram": ram, "disk": disk, "uptime": f"{hours}h {mins}m {secs}s"}

    def get_gpu_usage(self):
        if self.is_mac: return -1
        ok, out, err = _run(['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'], timeout=3)
        return int(out) if ok and out.isdigit() else -1

    def get_top_processes(self, limit=5):
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try: 
                info = p.info
                info['cpu_percent'] = round(info.get('cpu_percent') or 0, 1)
                info['memory_percent'] = round(info.get('memory_percent') or 0, 1)
                procs.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied): pass
        procs.sort(key=lambda x: x['cpu_percent'], reverse=True)
        return procs[:limit]

    def kill_process(self, pid):
        try: os.kill(pid, 9)
        except: pass

    def sleep(self):
        cmd = ["pmset", "sleepnow"] if self.is_mac else ["systemctl", "suspend"]
        _run(cmd, timeout=3)

    def get_sysinfo(self):
        if self.is_mac:
            ok1, model, _ = _run(["sysctl", "-n", "hw.model"])
            ok2, ram, _ = _run(["sysctl", "-n", "hw.memsize"])
            ram_gb = round(int(ram) / (1024**3), 1) if ok2 and ram.isdigit() else "?"
            return f"Model: {model if ok1 else 'Unknown'}\nRAM: {ram_gb} GB"
        else:
            ok1, cpu_raw, _ = _run(["grep", "-m1", "model name", "/proc/cpuinfo"])
            cpu = cpu_raw.split(":")[1].strip() if ok1 else "Unknown"
            ok2, ram_raw, _ = _run(["free", "-h"])
            ram = ram_raw.split("\n")[1].split()[1] if ok2 else "Unknown"
            return f"CPU: {cpu}\nRAM: {ram}"

    def get_apps(self):
        if self.is_mac:
            ok, out, err = _run(["osascript", "-e", 'tell application "System Events" to get name of every process whose background only is false'], timeout=5)
            if ok: return [a.strip() for a in out.split(',') if a.strip()]
            return ["Permission Denied (Check Accessibility in System Settings)"]
        else:
            ok, out, err = _run(["wmctrl", "-l"], timeout=5)
            if ok: return [line.split(None, 2)[2] for line in out.splitlines() if line]
            return ["wmctrl not installed or no X11"]

    def control_app(self, name, action):
        if self.is_mac:
            if action == "quit": _run(["osascript", "-e", f'tell application "{name}" to quit'])
            elif action == "force_quit": _run(["pkill", "-9", "-f", name])
        else:
            if action == "quit": _run(["wmctrl", "-c", name])
            elif action == "force_quit": _run(["pkill", "-9", "-f", name])

    def get_network_info(self):
        if self.is_mac:
            ok, out, _ = _run(["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-I"], timeout=3)
            for line in out.split('\n'):
                if ' SSID: ' in line: return line.split(':')[1].strip()
            return "Wi-Fi Off or Ethernet"
        else:
            ok, out, _ = _run(["iwgetid", "-r"], timeout=3)
            return out if ok else "Ethernet/Unknown"

    def take_screenshot(self):
        path = "/tmp/shot.jpg"
        if self.is_mac: _run(["screencapture", "-x", path], timeout=10)
        else: _run(["scrot", path], timeout=10)
        return path if os.path.exists(path) and os.path.getsize(path) > 0 else None

    def capture_cam(self):
        path = "/tmp/cam.jpg"
        if self.is_mac: _run(["imagesnap", "-w", "1", path], timeout=10)
        else: _run(["ffmpeg", "-f", "v4l2", "-i", "/dev/video0", "-frames:v", "1", "-y", path], timeout=10)
        return path if os.path.exists(path) and os.path.getsize(path) > 0 else None

    def set_volume(self, level):
        if self.is_mac: 
            ok, _, _ = _run(["osascript", "-e", f"set volume output volume {level}"])
            return ok
        else: 
            ok1, _, _ = _run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"])
            ok2, _, _ = _run(["amixer", "set", "Master", f"{level}%"])
            return ok1 or ok2

    def set_brightness(self, level):
        if self.is_mac: 
            ok, _, _ = _run(["brightness", str(level/100)])
            return ok
        else: 
            ok1, _, _ = _run(["brightnessctl", "set", f"{level}%"])
            ok2, _, _ = _run(["xbacklight", "-set", str(level)])
            return ok1 or ok2

    def get_battery(self):
        if self.is_mac:
            ok, out, _ = _run(["pmset", "-g", "batt"], timeout=3)
            return out.strip().split('\n')[0] if ok and out else "No Battery"
        else:
            ok, out, _ = _run(["upower", "-i", "/org/freedesktop/UPower/devices/battery_BAT0"], timeout=3)
            for line in out.split('\n'):
                if 'percentage:' in line: return line.split(':')[1].strip()
            return "No Battery (Headless/Desktop)"

    def media_control(self, action):
        if self.is_mac:
            cmd = {"play": "play pause", "next": "next track", "prev": "previous track"}.get(action, "")
            if cmd: 
                ok, _, _ = _run(["osascript", "-e", f'tell application "System Events" to key code {{' + ('3' if 'play' in cmd else ('19' if 'next' in cmd else '20')) + '} using command down'])
                return ok
        else:
            ok, _, _ = _run(["playerctl", action])
            return ok
        return False

    def say_text(self, text):
        cmd = ["say", text] if self.is_mac else ["espeak", text]
        subprocess.Popen(cmd)

    def run_shortcut(self, name):
        if not self.is_mac: return False
        ok, _, _ = _run(["shortcuts", "run", name], timeout=10)
        return ok

    def get_clipboard(self):
        cmd = ["pbpaste"] if self.is_mac else ["xclip", "-selection", "clipboard", "-o"]
        ok, out, err = _run(cmd, timeout=3)
        return out if ok else "(Empty or requires X11/Wayland session)"

    def set_clipboard(self, text):
        cmd = ["pbcopy"] if self.is_mac else ["xclip", "-selection", "clipboard"]
        try: 
            subprocess.run(cmd, input=text.encode(), check=True, timeout=3)
            return True
        except: 
            return False
