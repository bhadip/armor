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
                      "disk_warn": 85, "disk_crit": 95, "gpu_warn": 80, "gpu_crit": 95}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from os_adapter import OSAdapter
adapter = OSAdapter()

alert_states = {'cpu': {'state': 'normal', 'acked': False, 'last_alert': 0}, 'ram': {'state': 'normal', 'acked': False, 'last_alert': 0}, 'disk': {'state': 'normal', 'acked': False, 'last_alert': 0}, 'gpu': {'state': 'normal', 'acked': False, 'last_alert': 0}}

TG_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"


def load_thresholds():
    try:
        with open(THRESHOLDS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        with open(THRESHOLDS_FILE, "w") as f:
            json.dump(DEFAULT_THRESHOLDS, f, indent=2)
        return dict(DEFAULT_THRESHOLDS)


def get_network_context():
    try:
        resp = requests.get("http://ip-api.com/json/", timeout=5).json()
        lat, lon = resp.get("lat", 0), resp.get("lon", 0)
        maps = f"https://maps.google.com/?q={lat},{lon}"
        ts = datetime.datetime.now().strftime("%d/%m/%Y, %H:%M:%S")
        return (f"Time: {ts}\n"
                f"ISP Location: {resp.get('city')}, {resp.get('country')} (Data Exchange)\n"
                f"Coords: {lat}, {lon} ({maps})\n"
                f"IP: {resp.get('query')} - {resp.get('isp')}")
    except Exception as e:
        return f"Context Error: {e}"


def send_tg(text, kb=None):
    data = {"chat_id": ADMIN_CHAT_ID, "text": text}
    if kb:
        data["reply_markup"] = json.dumps({"inline_keyboard": kb})
    try:
        requests.post(TG_URL, data=data, timeout=10)
    except Exception as e:
        logger.error(f"TG send failed: {e}")


def heartbeat_loop():
    if not HEALTHCHECK_URL:
        return
    logger.info("Healthcheck heartbeat started.")
    while True:
        try:
            requests.get(HEALTHCHECK_URL, timeout=10)
        except Exception as e:
            logger.error(f"Heartbeat failed: {e}")
        time.sleep(60)


def watchdog_loop():
    logger.info("Watchdog started (Multi-Tier).")
    while True:
        time.sleep(60)
        try:
            s = adapter.get_status()
            gpu = adapter.get_gpu_usage() if hasattr(adapter, "get_gpu_usage") else -1
            metrics = {"cpu": s["cpu"], "ram": s["ram"], "disk": s["disk"]}
            if gpu >= 0:
                metrics["gpu"] = gpu
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
                        send_tg(f"✅ {HOSTNAME} {metric.upper()} Resolved: {value}%")
                    else:
                        icon = "🔴" if tier == "critical" else "🟡"
                        kb = [[{"text": "Acknowledge", "callback_data": f"ack_{metric}"}]]
                        send_tg(f"{icon} {HOSTNAME} {metric.upper()} {tier.upper()}: {value}%\n\n{get_network_context()}", kb)
                elif tier != "normal" and not st["acked"] and (time.time() - st["last_alert"] > 300):
                    st["last_alert"] = time.time()
                    icon = "🔴" if tier == "critical" else "🟡"
                    kb = [[{"text": "Acknowledge", "callback_data": f"ack_{metric}"}]]
                    send_tg(f"🔁 {HOSTNAME} {metric.upper()} Still {tier.upper()}: {value}%", kb)
        except Exception as e:
            logger.error(f"Watchdog error: {e}")


async def start(u, c):
    await u.message.reply_text(f"🛡 ARMOR agent online: {HOSTNAME}")


async def status(u, c):
    s = adapter.get_status()
    gpu = adapter.get_gpu_usage() if hasattr(adapter, "get_gpu_usage") else -1
    msg = f"🖥 {HOSTNAME}\nCPU: {s['cpu']}%\nRAM: {s['ram']}%\nDisk: {s['disk']}%\nUp: {s['uptime']}"
    if gpu >= 0:
        msg += f"\nGPU: {gpu}%"
    await u.message.reply_text(msg)


async def top(u, c):
    procs = adapter.get_top_processes()
    kb = [[InlineKeyboardButton(f"Kill {p.get('name')} ({p.get('pid')})", callback_data=f"kill_{p.get('pid')}")] for p in procs]
    lines = [f"{p.get('name')} | CPU {p.get('cpu')}% | RAM {p.get('mem')}%" for p in procs]
    await u.message.reply_text("Top processes:\n" + "\n".join(lines), reply_markup=InlineKeyboardMarkup(kb))


async def pause(u, c):
    subprocess.run(["ssh", f"{OPENWRT_USER}@{OPENWRT_IP}", f"touch /tmp/{HOSTNAME}_paused"])
    await u.message.reply_text("⏸ Offline monitoring paused.")


async def resume(u, c):
    subprocess.run(["ssh", f"{OPENWRT_USER}@{OPENWRT_IP}", f"rm -f /tmp/{HOSTNAME}_paused"])
    await u.message.reply_text("▶️ Offline monitoring resumed.")


async def sleep_cmd(u, c):
    subprocess.run(["ssh", f"{OPENWRT_USER}@{OPENWRT_IP}", f"touch /tmp/{HOSTNAME}_paused"])
    await u.message.reply_text("😴 Sleeping...")
    adapter.sleep()


async def thresholds_cmd(u, c):
    t = load_thresholds()
    msg = "⚙️ Thresholds (warn/crit):\n"
    for m in ["cpu", "ram", "disk", "gpu"]:
        msg += f"{m.upper()}: {t.get(m + '_warn')}% / {t.get(m + '_crit')}%\n"
    msg += "\nUsage: /setcpu 80 95"
    await u.message.reply_text(msg)


async def set_metric(u, c, metric):
    try:
        a = u.message.text.split()
        w, cr = int(a[1]), int(a[2])
        t = load_thresholds()
        t[metric + "_warn"] = w
        t[metric + "_crit"] = cr
        with open(THRESHOLDS_FILE, "w") as f:
            json.dump(t, f, indent=2)
        await u.message.reply_text(f"✅ {metric.upper()} set: warn {w}% / crit {cr}%")
    except Exception:
        await u.message.reply_text(f"Usage: /set{metric} <warn> <crit>")


async def setcpu(u, c): await set_metric(u, c, "cpu")
async def setram(u, c): await set_metric(u, c, "ram")
async def setdisk(u, c): await set_metric(u, c, "disk")
async def setgpu(u, c): await set_metric(u, c, "gpu")


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
            await q.edit_message_text(q.message.text + f"\n\n💀 Kill signal sent to PID {pid}.")
        except Exception:
            await q.edit_message_text(q.message.text + f"\n\n❌ Could not kill PID {pid}.")


def main():
    send_tg(f"🟢 {HOSTNAME} System Booted\n\n{get_network_context()}")
    threading.Thread(target=watchdog_loop, daemon=True).start()
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CommandHandler("pause", pause))
    app.add_handler(CommandHandler("resume", resume))
    app.add_handler(CommandHandler("sleep", sleep_cmd))
    app.add_handler(CommandHandler("thresholds", thresholds_cmd))
    app.add_handler(CommandHandler("setcpu", setcpu))
    app.add_handler(CommandHandler("setram", setram))
    app.add_handler(CommandHandler("setdisk", setdisk))
    app.add_handler(CommandHandler("setgpu", setgpu))
    app.add_handler(CallbackQueryHandler(btn))
    app.run_polling()


if __name__ == "__main__":
    main()
