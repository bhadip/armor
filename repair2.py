import pathlib, os, sys

if os.path.exists('/root/armor/agent/src/main.py'):
    p = pathlib.Path('/root/armor/agent/src/main.py')
else:
    p = pathlib.Path(os.path.expanduser('~/armor/agent/src/main.py'))

GOOD = "alert_states = {'cpu': {'state': 'normal', 'acked': False, 'last_alert': 0}, 'ram': {'state': 'normal', 'acked': False, 'last_alert': 0}, 'disk': {'state': 'normal', 'acked': False, 'last_alert': 0}, 'gpu': {'state': 'normal', 'acked': False, 'last_alert': 0}}"

GEO = [
 'def get_network_context():',
 '    try:',
 '        import requests',
 "        resp = requests.get('http://ip-api.com/json/', timeout=5).json()",
 "        lat, lon = resp.get('lat', 0), resp.get('lon', 0)",
 '        maps_link = f"https://maps.google.com/?q={lat},{lon}"',
 "        ts = datetime.datetime.now().strftime('%d/%m/%Y, %H:%M:%S')",
 '        return (',
 '            f"Time: {ts}\\n"',
 '            f"ISP Location: {resp.get(\'city\')}, {resp.get(\'country\')} (Data Exchange)\\n"',
 '            f"Coords: {lat}, {lon} ({maps_link})\\n"',
 '            f"IP: {resp.get(\'query\')} · {resp.get(\'isp\')}"',
 '        )',
 '    except Exception as e:',
 '        return f"Context Error: {e}"',
]

lines = p.read_text().splitlines()
out = []
skip_geo = False
skip_states = False
for line in lines:
    if line.startswith('def get_network_context():'):
        out.extend(GEO)
        skip_geo = True
        continue
    if skip_geo:
        if line.startswith('def ') or line.startswith('async def ') or line.strip().startswith('# Send Startup Alert'):
            skip_geo = False
        else:
            continue
    if line.startswith('alert_states = '):
        out.append(GOOD)
        skip_states = True
        continue
    if skip_states:
        s = line.strip()
        if s.startswith("'ram':") or s.startswith("'disk':") or s == '}':
            continue
        skip_states = False
    out.append(line)

src = '\n'.join(out) + '\n'
try:
    compile(src, 'main.py', 'exec')
except SyntaxError as e:
    print(f"❌ Still broken at line {e.lineno}: {e.msg}")
    sys.exit(1)

p.write_text(src)
print("✅ Repaired + syntax OK")
