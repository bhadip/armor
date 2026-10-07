import os, sys, json, time, psutil, platform, subprocess, socket

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
        years = uptime_secs // (365 * 24 * 3600); uptime_secs %= (365 * 24 * 3600)
        months = uptime_secs // (30 * 24 * 3600); uptime_secs %= (30 * 24 * 3600)
        days = uptime_secs // (24 * 3600); uptime_secs %= (24 * 3600)
        hours = uptime_secs // 3600; uptime_secs %= 3600
        mins = uptime_secs // 60; secs = uptime_secs % 60
        parts = []
        if years > 0: parts.append(f"{years}y")
        if months > 0: parts.append(f"{months}m")
        if days > 0: parts.append(f"{days}d")
        if hours > 0: parts.append(f"{hours}h")
        if mins > 0: parts.append(f"{mins}m")
        parts.append(f"{secs}s")
        return {"cpu": cpu, "ram": ram, "disk": disk, "uptime": " ".join(parts)}

    def get_gpu_usage(self):
        if self.is_mac: return -1
        ok, out, err = _run(['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'], timeout=3)
        return int(out) if ok and out.isdigit() else -1

    def get_top_processes(self, limit=5):
        procs = []
        for p in psutil.process_iter(['pid', 'name']):
            try: p.cpu_percent(interval=None)
            except: pass
        time.sleep(0.1)
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
        try:
            if self.is_mac:
                model_id = subprocess.run(["sysctl", "-n", "hw.model"], capture_output=True, text=True).stdout.strip()
                chip = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip()
                ncpu = subprocess.run(["sysctl", "-n", "hw.ncpu"], capture_output=True, text=True).stdout.strip()
                ram_bytes = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout.strip()
                ram_gb = round(int(ram_bytes) / (1024**3), 1) if ram_bytes.isdigit() else "?"
                
                serial = "Unknown"
                try:
                    sp_out = subprocess.run(["system_profiler", "SPHardwareDataType"], capture_output=True, text=True, timeout=10).stdout
                    for line in sp_out.split('\n'):
                        if "Serial Number" in line:
                            serial = line.split(":")[1].strip()
                            break
                except Exception: pass

                os_name = subprocess.run(["sw_vers", "-productName"], capture_output=True, text=True).stdout.strip()
                os_ver = subprocess.run(["sw_vers", "-productVersion"], capture_output=True, text=True).stdout.strip()
                
                disk = psutil.disk_usage('/')
                storage = f"{disk.free/1024**3:.2f} GB available of {disk.total/1024**3:.2f} GB"
                
                gfx = subprocess.run(["system_profiler", "SPDisplaysDataType"], capture_output=True, text=True, timeout=10).stdout
                gpu_name, vram, resolution = "Unknown", "Unified", "Unknown"
                gpu_count = 0
                for line in gfx.split('\n'):
                    if "Chipset Model:" in line: 
                        gpu_name = line.split(':')[1].strip()
                        gpu_count += 1
                    if "VRAM" in line and "Total" in line: 
                        vram = line.split(':')[1].strip()
                    if "Resolution:" in line: 
                        resolution = line.split(':')[1].strip()

                return (f"Model: Mac Mini ({model_id})\n"
                        f"Chip/Processor: {chip} ({ncpu} Cores)\n"
                        f"Memory: {ram_gb} GB\n"
                        f"Graphics: {gpu_name} ({vram}) x{gpu_count}\n"
                        f"Display: {resolution}\n"
                        f"Storage: {storage}\n"
                        f"Serial: {serial}\n"
                        f"OS: {os_name} {os_ver}")
            else:
                cpu = "Unknown"
                try:
                    with open("/proc/cpuinfo", "r") as f:
                        for line in f:
                            if "model name" in line:
                                cpu = line.split(":")[1].strip()
                                break
                except Exception: pass
                
                ncpu = str(psutil.cpu_count(logical=True))
                ram_gb = round(psutil.virtual_memory().total / (1024**3), 1)
                
                gpu_str = "None/Headless"
                try:
                    lspci = subprocess.run(["lspci"], capture_output=True, text=True, timeout=3).stdout
                    gpus = [line.split(':', 2)[2].strip() for line in lspci.split('\n') if 'VGA' in line or '3D' in line]
                    if gpus: gpu_str = ", ".join(gpus)
                except FileNotFoundError: pass
                except Exception: pass
                
                disk = psutil.disk_usage('/')
                storage = f"{disk.free/1024**3:.2f} GB available of {disk.total/1024**3:.2f} GB"
                os_ver = platform.platform()
                return (f"CPU: {cpu} ({ncpu} Cores)\n"
                        f"RAM: {ram_gb} GB\n"
                        f"GPU: {gpu_str}\n"
                        f"Storage: {storage}\n"
                        f"OS: {os_ver}")
        except Exception as e:
            return f"Error fetching sysinfo: {e}"

    def get_apps(self):
        if self.is_mac:
            ok, out, err = _run(["osascript", "-e", 'tell application "System Events" to get name of every process whose background only is false'], timeout=5)
            if ok: return [a.strip() for a in out.split(',') if a.strip()]
            return ["Permission Denied (Check Accessibility)"]
        else:
            if not os.environ.get("DISPLAY"):
                return ["Not applicable (Headless Linux has no active GUI session)"]
            ok, out, err = _run(["wmctrl", "-l"], timeout=5)
            if ok and out.strip(): return [line.split(None, 2)[2] for line in out.splitlines() if line]
            return ["No GUI apps running or wmctrl not installed"]

    def control_app(self, name, action):
        if self.is_mac:
            if action == "quit": _run(["osascript", "-e", f'tell application "{name}" to quit'])
            elif action == "force_quit": _run(["pkill", "-9", "-f", name])
        else:
            if action == "quit": _run(["wmctrl", "-c", name])
            elif action == "force_quit": _run(["pkill", "-9", "-f", name])

    def get_network_info(self):
        try:
            if self.is_mac:
                ports_out = subprocess.run(["networksetup", "-listallhardwareports"], capture_output=True, text=True).stdout
                active_port, active_device = "Unknown", ""
                current_port, current_dev = "", ""
                for line in ports_out.split('\n'):
                    if "Hardware Port:" in line: current_port = line.split(':', 1)[1].strip()
                    if "Device:" in line: 
                        current_dev = line.split(':', 1)[1].strip()
                        ip_check = subprocess.run(["ipconfig", "getifaddr", current_dev], capture_output=True, text=True).stdout.strip()
                        if ip_check and ip_check.startswith("192.168."):
                            active_port, active_device = current_port, current_dev
                            break
                
                if not active_device:
                    return "Status: No active LAN connection (Only Tailscale/VPN detected)"

                ip4 = subprocess.run(["ipconfig", "getifaddr", active_device], capture_output=True, text=True).stdout.strip() or "N/A"
                
                mac = "N/A"
                ifconf_out = subprocess.run(["ifconfig", active_device], capture_output=True, text=True).stdout
                for line in ifconf_out.split('\n'):
                    if "ether " in line:
                        mac = line.split()[1]
                        break

                dns_out = subprocess.run(["networksetup", "-getdnsservers", active_port], capture_output=True, text=True).stdout
                if "aren't any" in dns_out:
                    try:
                        with open('/etc/resolv.conf', 'r') as f:
                            dns_out = " ".join([l.split()[1] for l in f.readlines() if l.startswith("nameserver")])
                    except: dns_out = "N/A"
                
                ssid = "N/A (Ethernet)"
                if "Wi-Fi" in active_port:
                    airport_out = subprocess.run(["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-I"], capture_output=True, text=True).stdout
                    for line in airport_out.split('\n'):
                        if ' SSID: ' in line: ssid = line.split(':')[1].strip()

                # Check Tailscale status (macOS) via ifconfig (permission-free & reliable)
                ts_status = "INACTIVE"
                try:
                    ifconf_out = subprocess.run(["ifconfig"], capture_output=True, text=True, timeout=5).stdout
                    lines = ifconf_out.split('\n')
                    for i, line in enumerate(lines):
                        # Look for utun interfaces
                        if "utun" in line and not line.startswith(' '):
                            # Check the next few lines for a Tailscale IP (100.x.x.x)
                            for j in range(i, min(i+5, len(lines))):
                                if "inet 100." in lines[j]:
                                    ts_status = "ACTIVE"
                                    break
                        if ts_status == "ACTIVE":
                            break
                except Exception:
                    pass

                return f"Port: {active_port} ({active_device})\nSSID: {ssid}\nIPv4: {ip4}\nMAC: {mac}\nDNS: {dns_out.strip()}\nTailscale: {ts_status}"
            else:
                ip4, mac = "N/A", "N/A"
                for iface, addrs in psutil.net_if_addrs().items():
                    if iface == 'lo': continue
                    for addr in addrs:
                        if addr.family == socket.AF_INET and not addr.address.startswith('127.'):
                            ip4 = addr.address
                        elif addr.family == psutil.AF_LINK:
                            mac = addr.address
                    if ip4 != "N/A" and mac != "N/A": break
                
                dns = "N/A"
                # 1. Use absolute paths for tailscale to bypass systemd PATH restrictions
                ts_out = ""
                for ts_bin in ["/usr/bin/tailscale", "/usr/local/bin/tailscale", "tailscale"]:
                    try:
                        res = subprocess.run([ts_bin, "dns", "status"], capture_output=True, text=True, timeout=5)
                        if res.returncode == 0:
                            ts_out = res.stdout
                            break
                    except Exception:
                        pass

                if ts_out:
                    in_system = False
                    nameservers = []
                    for line in ts_out.split('\n'):
                        if "=== System DNS configuration ===" in line:
                            in_system = True
                        elif in_system and line.strip().startswith("- "):
                            ip = line.strip()[2:].strip()
                            if not ip.startswith("100.") and not ip.startswith("127.") and not ip.startswith("fd7a:"):
                                nameservers.append(ip)
                        elif in_system and line.startswith("==="):
                            break
                    if nameservers:
                        dns = " ".join(nameservers)

                # 2. Fallback to Gateway IP via /proc/net/route (Pure Python)
                if dns == "N/A":
                    try:
                        import struct
                        with open('/proc/net/route', 'r') as f:
                            for line in f.readlines():
                                fields = line.strip().split()
                                if len(fields) >= 3 and fields[1] == '00000000':
                                    gw_ip = socket.inet_ntoa(struct.pack('<L', int(fields[2], 16)))
                                    dns = f"{gw_ip} (Gateway)"
                                    break
                    except Exception:
                        dns = "192.168.50.1 (Gateway)" # Hardcoded fallback for your network
                    
                # Check Tailscale status
                ts_status = "INACTIVE"
                try:
                    for ts_bin in ["/usr/bin/tailscale", "/usr/local/bin/tailscale", "tailscale"]:
                        res = subprocess.run([ts_bin, "status", "--json"], capture_output=True, text=True, timeout=5)
                        if res.returncode == 0:
                            import json
                            ts_data = json.loads(res.stdout)
                            if ts_data.get("BackendState") == "Running":
                                ts_status = "ACTIVE"
                            break
                except Exception:
                    pass

                return f"IPv4: {ip4}\nMAC: {mac}\nDNS: {dns}\nTailscale: {ts_status}"
        except Exception as e:
            return f"Error fetching network info: {e}"

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
        if not self.is_mac:
            ok, out, _ = _run(["aplay", "-l"], timeout=3)
            if not ok or "no soundcards" in out.lower():
                return "Headless_NoAudio"
        cmd = ["say", text] if self.is_mac else ["espeak", text]
        try:
            subprocess.Popen(cmd)
            return True
        except:
            return False

    def run_shortcut(self, name):
        if not self.is_mac: return False
        ok, _, _ = _run(["shortcuts", "run", name], timeout=10)
        return ok

    def get_clipboard(self):
        if not self.is_mac and not os.environ.get("DISPLAY"):
            return "Headless_NoX11"
        cmd = ["pbpaste"] if self.is_mac else ["xclip", "-selection", "clipboard", "-o"]
        ok, out, err = _run(cmd, timeout=3)
        return out if ok else "Headless_NoX11"

    def set_clipboard(self, text):
        if not self.is_mac and not os.environ.get("DISPLAY"):
            return False
        cmd = ["pbcopy"] if self.is_mac else ["xclip", "-selection", "clipboard"]
        try: 
            subprocess.run(cmd, input=text.encode(), check=True, timeout=3)
            return True
        except: 
            return False
