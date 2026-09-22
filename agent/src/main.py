import os, datetime, json, datetime, logging, threading, time, requests, paramiko, json
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from os_adapter import OSAdapter

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("TELEGRAM_ADMIN_CHAT_ID"))
OPENWRT_IP = os.getenv("OPENWRT_IP")
OPENWRT_USER = os.getenv("OPENWRT_USER")
HEALTHCHECK_URL = os.getenv("HEALTHCHECK_URL", "")
HOSTNAME = os.getenv("HOSTNAME", "unknown")
adapter = OSAdapter()

# State tracking for watchdog
alert_states = {
    'cpu': {'active': False, 'acked': False, 'last_alert': 0},
    'ram': {'active': False, 'acked': False, 'last_alert': 0},
    'disk': {'active': False, 'acked': False, 'last_alert': 0}
}

def manage_router_lock(action):
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(OPENWRT_IP, username=OPENWRT_USER, look_for_keys=True)
        lock_file = f"/tmp/{HOSTNAME}_paused"
        if action == 'pause': client.exec_command(f"touch {lock_file}")
        elif action == 'resume': client.exec_command(f"rm -f {lock_file}")
        client.close()
        return True
    except Exception as e:
        logger.error(f"Router lock error: {e}")
        return False


def heartbeat_loop():
    if not HEALTHCHECK_URL: return
    logger.info("Healthcheck heartbeat started.")
    while True:
        try:
            requests.get(HEALTHCHECK_URL, timeout=10)
        except Exception as e:
            logger.error(f"Heartbeat failed: {e}")
        time.sleep(300)  # Send heartbeat every 5 minutes


def get_network_context():
    try:
        import requests
        resp = requests.get('http://ip-api.com/json/', timeout=5).json()
        lat, lon = resp.get('lat', 0), resp.get('lon', 0)
        maps_link = f"https://maps.google.com/?q={lat},{lon}"
        ts = datetime.datetime.now().strftime('%d/%m/%Y, %H:%M:%S')
        return (
            f"Time: {ts}\n"
            f"ISP Location: {resp.get('city')}, {resp.get('country')} _(Data Exchange)_\n"
            f"Coords: {lat}, {lon} ({maps_link})\n"
            f"IP: {resp.get('query')} · {resp.get('isp')}"
        )
    except Exception as e:
        return f"Context Error: {e}"
def watchdog_loop():
    logger.info("Watchdog started.")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    while True:
        time.sleep(60)
        s = adapter.get_status()
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        metrics = {'cpu': s['cpu'], 'ram': s['ram'], 'disk': s['disk']}
        
        for metric, value in metrics.items():
            state = alert_states[metric]
            if value > 90:
                if not state['active']:
                    # New alert
                    state['active'] = True
                    state['acked'] = False
                    state['last_alert'] = time.time()
                    kb = [[InlineKeyboardButton("Acknowledge", callback_data=f"ack_{metric}")]]
                    try:
                        requests.post(url, data={
                            "chat_id": ADMIN_CHAT_ID, 
                            "text": f"⚠️ {HOSTNAME} {metric.upper()} Critical: {value}%\nTime: {ts}",
                            "reply_markup": json.dumps({"inline_keyboard": kb})
                        })
                    except Exception as e: logger.error(e)
                elif not state['acked']:
                    # Repeat alert every 5 mins if not acked
                    if time.time() - state['last_alert'] > 300:
                        state['last_alert'] = time.time()
                        kb = [[InlineKeyboardButton("Acknowledge", callback_data=f"ack_{metric}")]]
                        try:
                            requests.post(url, data={
                                "chat_id": ADMIN_CHAT_ID, 
                                "text": f"🔁 {HOSTNAME} {metric.upper()} Still Critical: {value}%\nTime: {ts}",
                                "reply_markup": json.dumps({"inline_keyboard": kb})
                            })
                        except Exception as e: logger.error(e)
            else:
                if state['active']:
                    # Resolved
                    state['active'] = False
                    state['acked'] = False
                    try:
                        requests.post(url, data={
                            "chat_id": ADMIN_CHAT_ID, 
                            "text": f"✅ {HOSTNAME} {metric.upper()} Resolved: {value}%\nTime: {ts}"
                        })
                    except Exception as e: logger.error(e)

async def start(u, c): await u.message.reply_text(f"ARMOR online for {HOSTNAME}.")
async def status(u, c):
    s = adapter.get_status()
    await u.message.reply_text(f"🖥 *{HOSTNAME}*\nCPU: {s['cpu']}%\nRAM: {s['ram']}%\nDisk: {s['disk']}%\nUp: {s['uptime']}m", parse_mode='Markdown')
async def top(u, c):
    procs = adapter.get_top_processes()
    kb = [[InlineKeyboardButton(f"Kill {p['name']} ({p['pid']})", callback_data=f"k_{p['pid']}")] for p in procs]
    txt = "🔝 *Top:*\n" + "\n".join([f"• `{p['name']}` ({p['pid']}) - {p['cpu_percent']:.1f}%" for p in procs])
    await u.message.reply_text(txt, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
async def btn(u, c):
    q = u.callback_query; await q.answer()
    data = q.data
    if data.startswith("k_"):
        pid = int(data.split("_")[1])
        await q.edit_message_text(f"{'✅' if adapter.kill_process(pid) else '❌'} PID {pid}")
    elif data.startswith("ack_"):
        metric = data.split("_")[1]
        if metric in alert_states:
            alert_states[metric]['acked'] = True
            await q.edit_message_text(text=f"🔕 {metric.upper()} alert acknowledged. Will notify again when resolved.")
async def pause(u, c):
    await u.message.reply_text("⏸" if manage_router_lock('pause') else "❌")
async def resume(u, c):
    await u.message.reply_text("▶️" if manage_router_lock('resume') else "❌")
async def sleep_cmd(u, c):
    await u.message.reply_text("💤"); manage_router_lock('pause'); adapter.sleep()

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    threading.Thread(target=watchdog_loop, daemon=True).start()
    for h in [CommandHandler("start", start), CommandHandler("status", status), CommandHandler("top", top),
              CommandHandler("pause", pause), CommandHandler("resume", resume), CommandHandler("sleep", sleep_cmd),
              CallbackQueryHandler(btn)]:
        app.add_handler(h)
    
    # Send Startup Alert
    context = get_network_context()
    startup_msg = f"🟢 *{HOSTNAME} System Booted*\n\n{context}"
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                      data={"chat_id": ADMIN_CHAT_ID, "text": startup_msg, "parse_mode": "Markdown"})
    except Exception as e:
        logger.error(f"Startup alert failed: {e}")

    app.run_polling()

if __name__ == '__main__': main()
