"""Serveur de monitoring + détection du téléphone.

- Lit LibreHardwareMonitor (http://localhost:8085/data.json) + psutil
- Sert la page de monitoring sur http://localhost:8765
- Dès que le téléphone est branché en USB : adb reverse + bascule de l'app en mode monitoring
"""
import json, os, re, shutil, subprocess, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import psutil
import requests

PORT = 8765
LHM = "http://localhost:8085/data.json"
HERE = Path(__file__).resolve().parent
ADB = shutil.which("adb") or os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe")
NOWIN = 0x08000000  # pas de fenêtre console qui clignote
STATS = {}


def num(s):
    m = re.search(r"-?\d+(?:[.,]\d+)?", str(s))
    return float(m.group().replace(",", ".")) if m else None


def read_lhm():
    try:
        root = requests.get(LHM, timeout=1.5).json()
    except Exception:
        return None
    found = []

    def walk(n):
        for c in n.get("Children", []):
            if c.get("SensorId"):
                found.append(c)
            walk(c)

    walk(root)
    sens = []
    for c in found:
        p = c["SensorId"].split("/")
        v = num(c.get("Value"))
        raw = num(c.get("RawValue"))  # valeur brute (octets/s pour le débit)
        if len(p) >= 4 and v is not None:
            sens.append({"grp": "/".join(p[1:3]), "kind": p[-2], "name": c.get("Text", ""), "v": v, "raw": raw})

    def pick(items, prefs):
        for n in prefs:
            for i in items:
                if i["name"] == n:
                    return i["v"]
        return max((i["v"] for i in items), default=None)

    cpu = [s for s in sens if s["grp"].startswith(("amdcpu", "intelcpu"))]
    gpus = {}
    for s in sens:
        if s["grp"].startswith("gpu"):
            gpus.setdefault(s["grp"], []).append(s)
    best, best_load = None, -1
    for g, items in gpus.items():
        ld = pick([i for i in items if i["kind"] == "load"], ["GPU Core"]) or 0
        if ld >= best_load:
            best, best_load = g, ld
    gp = gpus.get(best, [])
    nic = [s for s in sens if s["grp"].startswith("nic") and s["kind"] == "throughput" and s["raw"] is not None]
    up = [s["raw"] for s in nic if s["name"] == "Upload Speed"]
    dn = [s["raw"] for s in nic if s["name"] == "Download Speed"]
    pw = [s["v"] for s in cpu if s["kind"] == "power" and s["name"] == "Package"]
    ssd = [s["v"] for s in sens if s["grp"].startswith("nvme") and s["kind"] == "temperature" and s["name"] == "Composite Temperature"]
    bat = [s["v"] for s in sens if s["grp"].startswith("battery") and s["kind"] == "level" and s["name"] == "Charge Level"]
    return {
        "cpu_load": pick([s for s in cpu if s["kind"] == "load"], ["CPU Total"]),
        "cpu_temp": pick([s for s in cpu if s["kind"] == "temperature"],
                         ["Core (Tctl/Tdie)", "CPU Package", "Core Max", "Tdie", "Tctl"]),
        "gpu_load": max((s["v"] for s in gp if s["kind"] == "load" and s["name"] in ("GPU Core", "D3D 3D")), default=None) if gp else None,
        "gpu_temp": pick([s for s in gp if s["kind"] == "temperature"], ["GPU Core", "GPU Hot Spot"]) if gp else None,
        "fans": [{"name": s["name"], "rpm": round(s["v"])} for s in sens if s["kind"] == "fan"],
        "net_up": sum(up) if up else None,
        "net_down": sum(dn) if dn else None,
        "cpu_power": pw[0] if pw else None,
        "ssd_temp": max(ssd) if ssd else None,
        "battery": bat[0] if bat else None,
    }


def read_disks():
    out = []
    for p in psutil.disk_partitions(all=False):
        if "fixed" not in p.opts.lower():
            continue
        try:
            u = psutil.disk_usage(p.mountpoint)
            out.append({"mount": p.mountpoint, "used": u.used, "total": u.total, "pct": u.percent})
        except OSError:
            pass
    return out


def sampler():
    global STATS
    psutil.cpu_percent(None)
    prev, t0, disks, td = psutil.net_io_counters(), time.time(), [], 0
    while True:
        time.sleep(1)
        try:
            now, t = psutil.net_io_counters(), time.time()
            dt = max(t - t0, 0.001)
            up, down = (now.bytes_sent - prev.bytes_sent) / dt, (now.bytes_recv - prev.bytes_recv) / dt
            prev, t0 = now, t
            if t - td > 30:
                disks, td = read_disks(), t
            vm, l = psutil.virtual_memory(), read_lhm() or {}
            STATS = {
                "cpu": {"load": l.get("cpu_load") if l.get("cpu_load") is not None else psutil.cpu_percent(None), "temp": l.get("cpu_temp")},
                "gpu": {"load": l.get("gpu_load"), "temp": l.get("gpu_temp")},
                "ram": {"pct": vm.percent, "used": vm.used, "total": vm.total},
                "net": {
                    "up": l["net_up"] if l.get("net_up") is not None else up,
                    "down": l["net_down"] if l.get("net_down") is not None else down,
                    "src": "lhm" if l.get("net_up") is not None else "psutil",
                },
                "extra": {"cpu_power": l.get("cpu_power"), "ssd": l.get("ssd_temp"), "battery": l.get("battery")},
                "fans": l.get("fans", []), "disks": disks, "lhm": bool(l), "ts": t,
            }
        except Exception as e:
            print("sampler:", e)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/stats"):
            body, ct = json.dumps(STATS).encode(), "application/json"
        else:
            body, ct = (HERE / "monitor.html").read_bytes(), "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def adb(*a):
    return subprocess.run([ADB, *a], capture_output=True, text=True, timeout=20, creationflags=NOWIN)


def watch_phone():
    was = False
    while True:
        try:
            lines = adb("devices").stdout.splitlines()[1:]
            ok = any(l.strip().endswith("device") for l in lines)
            if ok and not was:
                print("Téléphone détecté -> mode monitoring")
                adb("reverse", f"tcp:{PORT}", f"tcp:{PORT}")
                adb("shell", "input", "keyevent", "KEYCODE_WAKEUP")
                adb("shell", "am", "start", "-n", "com.ludo.dashboard/.MainActivity", "--es", "mode", "monitor")
            was = ok
        except Exception as e:
            print("adb:", e)
        time.sleep(3)


if __name__ == "__main__":
    threading.Thread(target=sampler, daemon=True).start()
    threading.Thread(target=watch_phone, daemon=True).start()
    print(f"Monitoring sur http://localhost:{PORT}  (ADB : {ADB})")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
