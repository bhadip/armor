import os
import json
import time
import datetime
import logging
import threading
import subprocess
import requests
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("TELEGRAM_ADMIN_CHAT_ID"))
HOSTNAME = os.getenv("HOSTNAME", "node")
OPENWRT_IP = os.getenv("OPENWRT_IP", "192.168.50.4")
OPENWRT_USER = os.getenv("OPENWRT_USER", "root")
HEALTHCHECK_URL = os.getenv("HEALTHCHECK_URL", "")

THRESHOLDS_FILE = os.path.join(os.path.dirname(__file__), "..", "thresholds.json")
DEFAULT_THRESHOLDS = {"cpu_warn": 80, "cpu_crit": 95, "ram_warn": 80, "ram_crit": 95,
                      "disk_warn": 85, "disk_crit": 95, "gpu_warn": 80, "gpu_crit": 95, "interval": 60}

IMPACT_GUIDE = {
    "cpu": {"warning": "Impact: Minor lag. Rec: Monitor via `/top`.", "critical": "Impact: Unresponsive. Rec: Run `/top` and kill processes."},
    "ram": {"warning": "Impact: Swapping begins. Rec: Check `/top` for leaks.", "critical": "Impact: OOM Killer active. Rec: Free memory or reboot."},
    "disk": {"warning": "Impact: Low space. Rec: Clear old logs.", "critical": "Impact: Instability imminent. Rec: Delete large files."},
    "gpu": {"warning": "Impact: Throttling. Rec: Check GPU processes.", "critical": "Impact: Driver crash risk. Rec: Halt GPU tasks."}
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from os_adapter import OSAdapter
adapter = OSAdapter()

alert_states = {"cpu": {"state": "normal", "acked": False, "last_alert": 0}, 
                "ram": {"state": "normal", "acked": False, "last_alert": 0}, 
                "disk": {"state": "normal", "acked": False, "last_alert": 0}, 
                "gpu": {"state": "normal", "acked": False, "last_alert": 0}}

TG_URL = "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage"

def load_thresholds():
    try:
        with open(THRESHOLDS_FILE, "r") as f: return json.load(f)
    except Exception:
        with open(THRESHOLDS_FILE, "w") as f: json.dump(DEFAULT_THRESHOLDS, f, indent=2)
        return dict(DEFAULT_THRESHOLDS)

def get_network_context():
    try:
        resp = requests.get("http://ip-api.com/json/", timeout=5).json()
        lat, lon = resp.get("lat", 0), resp.get("lon", 0)
        maps = "https://maps.google.com/?q=" + str(lat) + "," + str(lon)
        ts = datetime.datetime.now().strftime("%d/%m/%Y, %H:%M:%S")
        city = resp.get("city", "Unknown")
        country = resp.get("country", "Unknown")
        query = resp.get("query", "Unknown")
        isp = resp.get("isp", "Unknown")
        return "Time: " + ts + "\nISP Location: " + city + ", " + country + " (Data Exchange)\nCoords: " + str(lat) + ", " + str(lon) + " (" + maps + ")\nIP: " + query + " - " + isp
    except Exception as e:
        return "Context Error: " + str(e)

def send_tg(text, kb=None):
    data = {"chat_id": ADMIN_CHAT_ID, "text": text}
    if kb: data["reply_markup"] = json.dumps({"inline_keyboard": kb})
    try: requests.post(TG_URL, data=data, timeout=10)
    except Exception as e: logger.error("TG send failed: " + str(e))

def heartbeat_loop():
    if not HEALTHCHECK_URL: return
    logger.info("Healthcheck heartbeat started.")
    while True:
        try: requests.get(HEALTHCHECK_URL, timeout=10)
        except Exception as e: logger.error("Heartbeat failed: " + str(e))
        time.sleep(load_thresholds().get("interval", 60))

def watchdog_loop():
    logger.info("Watchdog started (Multi-Tier).")
    while True:
        time.sleep(load_thresholds().get("interval", 60))
        try:
            s = adapter.get_status()
            gpu = adapter.get_gpu_usage() if hasattr(adapter, "get_gpu_usage") else -1
            metrics = {"cpu": s["cpu"], "ram": s["ram"], "disk": s["disk"]}
            if gpu >= 0: metrics["gpu"] = gpu
            t = load_thresholds()
            for metric, value in metrics.items():
                st = alert_states[metric]
                warn_t = t.get(metric + "_warn", 80)
                crit_t = t.get(metric + "_crit", 95)
                tier = "critical" if value >= crit_t else ("warning" if value >= warn_t else "normal")
                
                if tier != st["state"]:
                    st["state"] = tier
                    st["acked"] = False
                    st["last_alert"] = time.time()
                    if tier == "normal":
                        send_tg("✅ " + HOSTNAME + " " + metric.upper() + " Resolved: " + str(value) + "%")
                    else:
                        icon = "🔴" if tier == "critical" else "🟡"
                        kb = [[{"text": "Acknowledge", "callback_data": "ack_" + metric}]]
                        impact = IMPACT_GUIDE.get(metric, {}).get(tier, "Check system.")
                        msg = icon + " " + HOSTNAME + " " + metric.upper() + " " + tier.upper() + ": " + str(value) + "%\n\n" + get_network_context() + "\n\n⚠️ *Impact & Action:*\n" + impact
                        send_tg(msg, kb)
                elif tier != "normal" and not st["acked"] and (time.time() - st["last_alert"] > 300):
                    st["last_alert"] = time.time()
                    icon = "🔴" if tier == "critical" else "🟡"
                    kb = [[{"text": "Acknowledge", "callback_data": "ack_" + metric}]]
                    send_tg(" " + HOSTNAME + " " + metric.upper() + " Still " + tier.upper() + ": " + str(value) + "%", kb)
        except Exception as e: logger.error("Watchdog error: " + str(e))

# --- Phase 1 Commands ---
async def start(u, c): await u.message.reply_text("🛡 ARMOR agent online: " + HOSTNAME)
async def status(u, c):
    s = adapter.get_status()
    gpu = adapter.get_gpu_usage() if hasattr(adapter, "get_gpu_usage") else -1
    msg = " " + HOSTNAME + "\nCPU: " + str(s['cpu']) + "%\nRAM: " + str(s['ram']) + "%\nDisk: " + str(s['disk']) + "%\nUp: " + s['uptime']
    if gpu >= 0: msg += "\nGPU: " + str(gpu) + "%"
    await u.message.reply_text(msg)

async def top(u, c):
    procs = adapter.get_top_processes()
    kb = [[InlineKeyboardButton("Kill " + str(p.get('name')), callback_data="kill_" + str(p.get('pid')))] for p in procs]
    lines = [str(p.get('name')) + " | CPU " + str(p.get('cpu_percent')) + "% | RAM " + str(p.get('memory_percent')) + "%" for p in procs]
    await u.message.reply_text("Top processes:\n" + "\n".join(lines), reply_markup=InlineKeyboardMarkup(kb))

async def pause(u, c):
    subprocess.run(["ssh", OPENWRT_USER + "@" + OPENWRT_IP, "touch /tmp/" + HOSTNAME + "_paused"])
    await u.message.reply_text("⏸ Offline monitoring paused.")
async def resume(u, c):
    subprocess.run(["ssh", OPENWRT_USER + "@" + OPENWRT_IP, "rm -f /tmp/" + HOSTNAME + "_paused"])
    await u.message.reply_text("▶️ Offline monitoring resumed.")
async def sleep_cmd(u, c):
    subprocess.run(["ssh", OPENWRT_USER + "@" + OPENWRT_IP, "touch /tmp/" + HOSTNAME + "_paused"])
    await u.message.reply_text("😴 Sleeping...")
    adapter.sleep()

async def thresholds_cmd(u, c):
    t = load_thresholds()
    msg = "⚙️ Thresholds (warn/crit):\n"
    for m in ["cpu", "ram", "disk", "gpu"]: msg += m.upper() + ": " + str(t.get(m + '_warn')) + "% / " + str(t.get(m + '_crit')) + "%\n"
    msg += "\nUsage: /setcpu 80 95"
    await u.message.reply_text(msg)

async def set_metric(u, c, metric):
    try:
        a = u.message.text.split()
        w, cr = int(a[1]), int(a[2])
        t = load_thresholds()
        t[metric + "_warn"] = w
        t[metric + "_crit"] = cr
        with open(THRESHOLDS_FILE, "w") as f: json.dump(t, f, indent=2)
        await u.message.reply_text("✅ " + metric.upper() + " set: warn " + str(w) + "% / crit " + str(cr) + "%")
    except Exception: await u.message.reply_text("Usage: /set" + metric + " <warn> <crit>")

async def setcpu(u, c): await set_metric(u, c, "cpu")
async def setram(u, c): await set_metric(u, c, "ram")
async def setdisk(u, c): await set_metric(u, c, "disk")
async def setgpu(u, c): await set_metric(u, c, "gpu")
async def interval_cmd(u, c):
    try:
        val = int(u.message.text.split()[1])
        t = load_thresholds()
        t["interval"] = val
        with open(THRESHOLDS_FILE, "w") as f: json.dump(t, f, indent=2)
        await u.message.reply_text("✅ Watchdog interval set to " + str(val) + "s.")
    except Exception: await u.message.reply_text("Usage: /interval <seconds>")

# --- Phase 2 Commands ---
async def sysinfo_cmd(u, c):
    info = adapter.get_sysinfo()
    await u.message.reply_text("🖥 *System Info*\n\n" + info, parse_mode="Markdown")

async def shortcut_cmd(u, c):
    name = u.message.text.replace("/shortcut", "").strip()
    if not name: return await u.message.reply_text("Usage: /shortcut <Name>")
    if adapter.run_shortcut(name): await u.message.reply_text("✅ Shortcut '" + name + "' triggered.")
    else: await u.message.reply_text("❌ Failed. Is the shortcut name correct?")

async def cam_cmd(u, c):
    await u.message.reply_text("📸 Snapping photo...")
    path = adapter.capture_cam()
    if path: await u.message.reply_photo(open(path, "rb"))
    else: await u.message.reply_text("❌ Camera failed. (Mac: `brew install imagesnap`, Lin: `apt install ffmpeg`)")

async def clip_cmd(u, c):
    args = u.message.text.split(maxsplit=1)
    if len(args) < 2 or args[1].startswith("get"):
        clip_text = adapter.get_clipboard()
        if "requires X11" in clip_text:
            await u.message.reply_text("❌ Not applicable to this OS setting (Headless Linux has no active GUI clipboard).")
        else:
            await u.message.reply_text("📋 Clipboard:\n`" + clip_text + "`", parse_mode="Markdown")
    elif args[1].startswith("set "):
        if adapter.set_clipboard(args[1][4:]):
            await u.message.reply_text("✅ Copied to clipboard.")
        else:
            await u.message.reply_text("❌ Not applicable to this OS setting (Headless Linux has no active GUI clipboard).")

async def apps_cmd(u, c):
    apps = adapter.get_apps()
    kb = []
    for app in apps[:10]:
        kb.append([InlineKeyboardButton("Quit " + app, callback_data="quit_" + app), InlineKeyboardButton("Force " + app, callback_data="force_" + app)])
    await u.message.reply_text("Running Apps:\n" + "\n".join(apps[:10]), reply_markup=InlineKeyboardMarkup(kb))

async def netinfo_cmd(u, c):
    ssid = adapter.get_network_info()
    await u.message.reply_text(" Current Network: " + ssid)

async def vol_cmd(u, c):
    try:
        level = int(u.message.text.split()[1])
        if adapter.set_volume(level):
            await u.message.reply_text("🔊 Volume set to " + str(level) + "%")
        else:
            await u.message.reply_text("❌ Hardware not available or missing tools.")
    except Exception: await u.message.reply_text("Usage: /vol <0-100>")

async def bright_cmd(u, c):
    try:
        level = int(u.message.text.split()[1])
        if adapter.set_brightness(level):
            await u.message.reply_text("💡 Brightness set to " + str(level) + "%")
        else:
            await u.message.reply_text("❌ Hardware not available or missing tools.")
    except Exception: await u.message.reply_text("Usage: /bright <0-100>")

async def battery_cmd(u, c):
    await u.message.reply_text("🔋 " + adapter.get_battery())

async def shot_cmd(u, c):
    await u.message.reply_text("📸 Taking screenshot...")
    path = adapter.take_screenshot()
    if path: await u.message.reply_photo(open(path, "rb"))
    else: await u.message.reply_text("❌ Screenshot failed.")

async def media_cmd(u, c):
    action = u.message.text.split()[1] if len(u.message.text.split()) > 1 else "play"
    adapter.media_control(action)
    await u.message.reply_text("🎵 Media: " + action)

async def say_cmd(u, c):
    text = u.message.text.replace("/say", "").strip()
    if text:
        adapter.say_text(text)
        await u.message.reply_text(" Speaking...")
    else: await u.message.reply_text("Usage: /say <text>")

async def btn(u, c):
    q = u.callback_query
    await q.answer()
    d = q.data
    if d.startswith("ack_"):
        m = d[4:]
        if m in alert_states:
            alert_states[m]["acked"] = True
            await q.edit_message_text(q.message.text + "\n\n🤫 Acknowledged by admin.")
    elif d.startswith("kill_"):
        pid = int(d[5:])
        try:
            adapter.kill_process(pid)
            await q.edit_message_text(q.message.text + "\n\n💀 Kill signal sent to PID " + str(pid) + ".")
        except Exception: await q.edit_message_text(q.message.text + "\n\n❌ Could not kill PID " + str(pid) + ".")
    elif d.startswith("quit_") or d.startswith("force_"):
        action = "force_quit" if d.startswith("force_") else "quit"
        name = d[5:] if d.startswith("force_") else d[5:]
        adapter.control_app(name, action)
        await q.edit_message_text(q.message.text + "\n\n✅ Sent " + action + " to " + name + ".")

def main():
    send_tg(" " + HOSTNAME + " System Booted\n\n" + get_network_context())
    threading.Thread(target=watchdog_loop, daemon=True).start()
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()
    
    handlers = [
        ("start", start), ("status", status), ("top", top), ("pause", pause), ("resume", resume),
        ("sleep", sleep_cmd), ("thresholds", thresholds_cmd), ("setcpu", setcpu), ("setram", setram),
        ("setdisk", setdisk), ("setgpu", setgpu), ("interval", interval_cmd), ("sysinfo", sysinfo_cmd),
        ("shortcut", shortcut_cmd), ("cam", cam_cmd), ("clip", clip_cmd), ("apps", apps_cmd),
        ("netinfo", netinfo_cmd), ("vol", vol_cmd), ("bright", bright_cmd), ("battery", battery_cmd),
        ("shot", shot_cmd), ("media", media_cmd), ("say", say_cmd)
    ]
    for name, func in handlers: app.add_handler(CommandHandler(name, func))
    app.add_handler(CallbackQueryHandler(btn))
    app.run_polling()

if __name__ == "__main__":
    main()
