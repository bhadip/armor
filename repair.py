import pathlib, os, sys

if os.path.exists('/root/armor/agent/src/main.py'):
    p = pathlib.Path('/root/armor/agent/src/main.py')
else:
    p = pathlib.Path(os.path.expanduser('~/armor/agent/src/main.py'))

GOOD = "alert_states = {'cpu': {'state': 'normal', 'acked': False, 'last_alert': 0}, 'ram': {'state': 'normal', 'acked': False, 'last_alert': 0}, 'disk': {'state': 'normal', 'acked': False, 'last_alert': 0}, 'gpu': {'state': 'normal', 'acked': False, 'last_alert': 0}}"

lines = p.read_text().splitlines()
out = []
skip = False
fixed = False
for line in lines:
    if line.startswith('alert_states = '):
        out.append(GOOD)
        skip = True
        fixed = True
        continue
    if skip:
        s = line.strip()
        if s.startswith("'ram':") or s.startswith("'disk':") or s == '}':
            continue
        skip = False
    out.append(line)

src = '\n'.join(out) + '\n'
try:
    compile(src, 'main.py', 'exec')
except SyntaxError as e:
    print(f"❌ Still broken: {e}")
    sys.exit(1)

p.write_text(src)
print("✅ Repaired and syntax-checked!" if fixed else "⚠️ alert_states not found")
