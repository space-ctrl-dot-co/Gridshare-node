"""
GridShare — updater.py  v0.1

Checks GitHub for a newer version of the node software and applies it safely.
Called automatically by server.py on startup. Can also be run manually.

Usage:
    python updater.py                  # check only
    python updater.py --apply          # check and apply if update available
    python updater.py --force          # apply even if version matches (testing)
    python updater.py --channel beta   # use the beta update channel
"""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CURRENT_VERSION = "0.1.0"
INSTALL_DIR     = Path(__file__).parent.resolve()

UPDATE_CHANNELS = {
    "stable": "https://raw.githubusercontent.com/space-ctrl-dot-co/Gridshare-node/main/releases/stable/version.json",
    "beta":   "https://raw.githubusercontent.com/space-ctrl-dot-co/Gridshare-node/main/releases/beta/version.json",
}

if platform.system() == "Windows": os.system("")
G="\033[92m"; Y="\033[93m"; R="\033[91m"; X="\033[0m"
def ok(t):   return f"{G}\u2713{X}  {t}"
def warn(t): return f"{Y}\u26a0{X}  {t}"
def bad(t):  return f"{R}\u2717{X}  {t}"

def load_config():
    cfg = INSTALL_DIR / "config.json"
    if cfg.exists():
        try: return json.loads(cfg.read_text())
        except: pass
    return {}

def sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""): h.update(chunk)
    return h.hexdigest()

def version_tuple(v):
    try: return tuple(int(x) for x in v.strip().split("."))
    except: return (0, 0, 0)

def is_newer(remote, local):
    return version_tuple(remote) > version_tuple(local)

def fetch_version_info(channel):
    config   = load_config()
    channels = config.get("update_channels", UPDATE_CHANNELS)
    url      = channels.get(channel, UPDATE_CHANNELS.get("stable"))
    if not url: return None
    try:
        import requests
        r = requests.get(url, timeout=10)
        if r.status_code != 200: return None
        data = r.json()
        if not all(k in data for k in ("version", "url", "sha256")): return None
        return data
    except: return None

def download_update(info):
    url = info["url"]; expected = info["sha256"]
    try:
        import requests
        print(f"  Downloading v{info['version']}...")
        r = requests.get(url, stream=True, timeout=60)
        if r.status_code != 200: print(bad(f"Download failed: HTTP {r.status_code}")); return None
        total = int(r.headers.get("content-length", 0)); downloaded = 0
        tmp = tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="wb")
        try:
            for chunk in r.iter_content(chunk_size=65536):
                tmp.write(chunk); downloaded += len(chunk)
                if total: print(f"\r  {downloaded/total*100:.0f}%", end="", flush=True)
            tmp_path = Path(tmp.name)
        finally: tmp.close()
        print()
        actual = sha256_of_file(tmp_path)
        if actual != expected:
            print(bad(f"Checksum mismatch — update aborted")); tmp_path.unlink(missing_ok=True); return None
        print(ok("Checksum verified")); return tmp_path
    except Exception as e: print(bad(f"Download error: {e}")); return None

def apply_update(tmp, info):
    try:
        print(f"  Applying v{info['version']}...")
        result = subprocess.run([sys.executable, str(tmp), "--update-in-place",
            "--install-dir", str(INSTALL_DIR), "--from-version", CURRENT_VERSION],
            capture_output=True, text=True, timeout=120)
        if result.returncode == 0: print(ok("Update applied")); return True
        print(bad(f"Installer failed (exit {result.returncode})")); return False
    except Exception as e: print(bad(f"Apply failed: {e}")); return False
    finally: tmp.unlink(missing_ok=True)

def restart_node():
    server = INSTALL_DIR / "server.py"
    if not server.exists(): print(warn("server.py not found — restart manually")); return
    print("  Restarting node...")
    if platform.system() == "Windows":
        subprocess.Popen([sys.executable, str(server)],
            creationflags=subprocess.CREATE_NO_WINDOW, cwd=str(INSTALL_DIR))
        sys.exit(0)
    else:
        os.execv(sys.executable, [sys.executable, str(server)])

def record_update(from_v, to_v, success):
    log = INSTALL_DIR / "update_history.jsonl"
    entry = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "from_version": from_v, "to_version": to_v, "success": success}
    with open(log, "a") as f: f.write(json.dumps(entry) + "\n")

def check_and_apply(channel="stable", auto_apply=False, force=False, restart=True):
    info = fetch_version_info(channel)
    if info is None: return False
    remote = info["version"]
    if not force and not is_newer(remote, CURRENT_VERSION): return False
    print(f"\n  {Y}Update available: v{remote}{X}  (current: v{CURRENT_VERSION})")
    if not auto_apply: return False
    tmp = download_update(info)
    if tmp is None: return False
    success = apply_update(tmp, info)
    record_update(CURRENT_VERSION, remote, success)
    if success and restart: restart_node()
    return success

def _do_in_place_update(install_dir):
    src = Path(__file__)
    dst = install_dir / "updater.py"
    shutil.copy2(src, dst)
    print(f"Updated: {dst.name}")
    sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GridShare updater")
    parser.add_argument("--apply",           action="store_true")
    parser.add_argument("--force",           action="store_true")
    parser.add_argument("--channel",         default="stable")
    parser.add_argument("--no-restart",      action="store_true")
    parser.add_argument("--update-in-place", action="store_true")
    parser.add_argument("--install-dir",     default=None)
    parser.add_argument("--from-version",    default=None)
    args = parser.parse_args()

    if args.update_in_place and args.install_dir:
        _do_in_place_update(Path(args.install_dir))

    print(f"\nGridShare updater  |  v{CURRENT_VERSION}  |  channel: {args.channel}\n")
    info = fetch_version_info(args.channel)

    if info is None:
        print(warn("Could not reach update channel — check internet connection"))
        sys.exit(0)

    remote = info["version"]
    if not args.force and not is_newer(remote, CURRENT_VERSION):
        print(ok(f"Up to date  (v{CURRENT_VERSION})")); sys.exit(0)

    print(f"  Remote: v{remote}  |  Current: v{CURRENT_VERSION}")
    notes = info.get("release_notes", "")
    if notes: print(f"  {notes}")

    if not args.apply and not args.force:
        print(warn(f"Update available. Run with --apply to install.")); sys.exit(0)

    tmp = download_update(info)
    if tmp is None: sys.exit(1)
    success = apply_update(tmp, info)
    record_update(CURRENT_VERSION, remote, success)
    if success and not args.no_restart: restart_node()
    sys.exit(0 if success else 1)
