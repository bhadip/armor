import os, platform, subprocess, signal, time, psutil

class OSAdapter:
    def __init__(self): self.system = platform.system()
    
    def get_gpu_usage(self):
        try:
            res = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=2)
            if res.returncode == 0: return int(res.stdout.strip())
        except: pass
        return -1

    def get_status(self):
        return {"cpu": psutil.cpu_percent(1), "ram": psutil.virtual_memory().percent,
                "disk": psutil.disk_usage('/').percent, 
                "uptime": int((time.time() - psutil.boot_time()) / 60),
                "hostname": platform.node()}
    def get_top_processes(self, limit=5):
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try: procs.append(p.info)
            except: pass
        procs.sort(key=lambda x: (x['cpu_percent'] or 0, x['memory_percent'] or 0), reverse=True)
        return procs[:limit]
    def kill_process(self, pid):
        try: os.kill(pid, signal.SIGKILL); return True
        except: return False
    def sleep(self):
        if self.system == "Linux": subprocess.run(["systemctl", "suspend"])
        elif self.system == "Darwin": subprocess.run(["pmset", "sleepnow"])
    def shutdown(self):
        if self.system == "Linux": subprocess.run(["shutdown", "-h", "now"])
        elif self.system == "Darwin": subprocess.run(["osascript", "-e", 'tell app "System Events" to shut down'])
    def restart(self):
        if self.system == "Linux": subprocess.run(["reboot"])
        elif self.system == "Darwin": subprocess.run(["osascript", "-e", 'tell app "System Events" to restart'])
    def media_play_pause(self):
        if self.system == "Linux": subprocess.run(["playerctl", "play-pause"], capture_output=True)
