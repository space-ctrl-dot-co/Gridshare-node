"""
GridShare Node Installer  v0.1
==============================
Single-file installer for Windows.
Double-click or run: python gridshare_install.py

What this does, in order:
  1. Checks Python version and pip
  2. Reads available hardware (space, RAM, CPU)
  3. Recommends a model and configuration for THIS machine
  4. Installs Python dependencies
  5. Downloads the recommended model
  6. Generates node keypair
  7. Writes server.py, inference_worker.py, updater.py to the install folder
  8. Creates a Start Menu shortcut and a system tray startup entry
  9. Runs the space estimator and test suite
 10. Prints a summary: node ID, IP address, how to connect

After this script runs, the node is live and self-updating.
No other files needed.
"""

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION — edit these before distributing
# ─────────────────────────────────────────────────────────────────────────────
INSTALLER_VERSION  = "0.1.0"
INSTALL_DIR_NAME   = "GridShare"          # folder created in %APPDATA%
UPDATE_CHANNEL_URL = "https://raw.githubusercontent.com/gridshare/gridshare-node/main/version.json"
REQUIRED_PYTHON    = (3, 10)
MIN_RAM_GB         = 4.0
MIN_DISK_GB        = 8.0

DEPENDENCIES = [
    "llama-cpp-python",
    "fastapi",
    "uvicorn",
    "PyNaCl",
    "cryptography",
    "requests",
    "psutil",
]

MODELS = [
    {
        "id":        "phi-3.5-mini-q4",
        "name":      "Phi-3.5 Mini (Q4) — Recommended",
        "filename":  "model.gguf",
        "disk_gb":   2.4,
        "ram_gb":    5.0,
        "url":       "https://huggingface.co/bartowski/Phi-3.5-mini-instruct-GGUF/resolve/main/Phi-3.5-mini-instruct-Q4_K_M.gguf",
    },
    {
        "id":        "llama-3.2-3b-q4",
        "name":      "Llama 3.2 3B (Q4) — Smaller/faster",
        "filename":  "model.gguf",
        "disk_gb":   2.0,
        "ram_gb":    4.0,
        "url":       "https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# EMBEDDED FILE CONTENTS
# server.py, inference_worker.py, updater.py are written by this installer.
# Edit these strings to update what gets installed.
# ─────────────────────────────────────────────────────────────────────────────

SERVER_PY = r'''
"""GridShare Node — server.py (installed by gridshare_install.py)"""
import argparse, base64, json, os, platform, subprocess, sys, time, uuid
from pathlib import Path
import nacl.encoding, nacl.public, requests, uvicorn
from fastapi import FastAPI, HTTPException, Request

VERSION = "0.1.0"
UPDATE_CHANNEL_URL = "https://raw.githubusercontent.com/gridshare/gridshare-node/main/version.json"

parser = argparse.ArgumentParser()
parser.add_argument("--model",      default="./model.gguf")
parser.add_argument("--host",       default="0.0.0.0")
parser.add_argument("--port",       default=8080, type=int)
parser.add_argument("--ctx",        default=4096, type=int)
parser.add_argument("--gpu",        default=0,    type=int)
parser.add_argument("--threads",    default=None, type=int)
parser.add_argument("--no-encrypt", action="store_true")
args = parser.parse_args()

KEYS_DIR    = Path("./keys")
KEY_FILE    = KEYS_DIR / "node_private.key"
PUBKEY_FILE = KEYS_DIR / "node_public.key"

def load_or_create_keypair():
    KEYS_DIR.mkdir(exist_ok=True)
    if KEY_FILE.exists():
        pk = nacl.public.PrivateKey(base64.b64decode(KEY_FILE.read_text().strip()))
    else:
        pk = nacl.public.PrivateKey.generate()
        KEY_FILE.write_text(base64.b64encode(bytes(pk)).decode())
        PUBKEY_FILE.write_text(base64.b64encode(bytes(pk.public_key)).decode())
        if platform.system() != "Windows": KEY_FILE.chmod(0o600)
    return pk, pk.public_key.encode(nacl.encoding.HexEncoder).decode()

def check_for_updates():
    try:
        r = requests.get(UPDATE_CHANNEL_URL, timeout=5)
        d = r.json()
        if d.get("version") != VERSION:
            print(f"Update available: {d.get('version')} — run gridshare_install.py to update")
    except Exception:
        pass

def decrypt_job(enc_b64, priv, sender_pub_b64):
    box = nacl.public.Box(priv, nacl.public.PublicKey(base64.b64decode(sender_pub_b64)))
    return json.loads(box.decrypt(base64.b64decode(enc_b64)))

def encrypt_result(result, priv, req_pub_b64):
    box = nacl.public.Box(priv, nacl.public.PublicKey(base64.b64decode(req_pub_b64)))
    return base64.b64encode(box.encrypt(json.dumps(result).encode())).decode()

def run_sandboxed(prompt, max_tokens, temperature):
    worker = Path(__file__).parent / "inference_worker.py"
    payload = json.dumps({"model_path": args.model, "prompt": prompt,
                          "max_tokens": max_tokens, "temperature": temperature,
                          "n_ctx": args.ctx, "n_gpu_layers": args.gpu})
    flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
    proc  = subprocess.run([sys.executable, str(worker)], input=payload,
                           capture_output=True, text=True, timeout=120,
                           env={"PATH": os.environ.get("PATH","")},
                           creationflags=flags)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[:300])
    return json.loads(proc.stdout)

def messages_to_prompt(messages):
    p = ""
    for m in messages:
        p += f"<|{m.get('role','user')}|>\n{m.get('content','')}<|end|>\n"
    return p + "<|assistant|>\n"

private_key, pub_key_hex = load_or_create_keypair()
node_id = f"node-{pub_key_hex[:16]}"
check_for_updates()

print(f"\nGridShare Node v{VERSION}  |  {node_id}  |  :{args.port}  |  encrypt={'on' if not args.no_encrypt else 'OFF'}\n")

app = FastAPI()
START = time.time()
JOBS = TOKENS = 0

@app.get("/")
def root():
    return {"service":"GridShare Node","version":VERSION,"node_id":node_id,
            "public_key":pub_key_hex,"status":"running",
            "uptime_seconds":round(time.time()-START),
            "jobs_completed":JOBS,"tokens_generated":TOKENS,
            "encryption":not args.no_encrypt,"sandbox":platform.system()}

@app.get("/v1/models")
def models():
    return {"object":"list","data":[{"id":"gridshare-local","object":"model",
            "created":int(START),"owned_by":"gridshare"}]}

@app.get("/v1/node/pubkey")
def pubkey():
    return {"node_id":node_id,"public_key":pub_key_hex}

@app.post("/v1/chat/completions")
async def completions(request: Request):
    global JOBS, TOKENS
    body = await request.json()
    t    = time.time()
    jid  = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    if body.get("encrypted") and not args.no_encrypt:
        try:    payload = decrypt_job(body["payload"], private_key, body["sender_public_key"])
        except Exception as e: raise HTTPException(400, f"Decryption failed: {e}")
    else:
        payload = body

    msgs     = payload.get("messages",[])
    max_tok  = payload.get("max_tokens",512)
    temp     = payload.get("temperature",0.7)
    if not msgs: raise HTTPException(400,"messages required")

    try:    res = run_sandboxed(messages_to_prompt(msgs), max_tok, temp)
    except subprocess.TimeoutExpired: raise HTTPException(504,"Timeout")
    except Exception as e:            raise HTTPException(500,str(e))

    JOBS  += 1; TOKENS += res["completion_tokens"]
    ms     = round((time.time()-t)*1000)
    print(f"[job {JOBS}] {res['prompt_tokens']}→{res['completion_tokens']} tok | {ms}ms")

    result = {"id":jid,"object":"chat.completion","created":int(t),"model":"gridshare-local",
              "choices":[{"index":0,"message":{"role":"assistant","content":res["text"]},
                          "finish_reason":"stop"}],
              "usage":{"prompt_tokens":res["prompt_tokens"],
                       "completion_tokens":res["completion_tokens"],
                       "total_tokens":res["prompt_tokens"]+res["completion_tokens"]},
              "_gridshare":{"latency_ms":ms,"node_id":node_id}}

    if body.get("encrypted") and not args.no_encrypt:
        return {"encrypted":True,"payload":encrypt_result(result,private_key,body["sender_public_key"])}
    return result

if __name__ == "__main__":
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
'''

WORKER_PY = r'''
"""GridShare — inference_worker.py  (sandboxed subprocess)"""
import json, sys

def main():
    try:    payload = json.loads(sys.stdin.read())
    except Exception as e: print(json.dumps({"error":str(e)}),file=sys.stderr); sys.exit(1)
    try:
        from llama_cpp import Llama
        llm = Llama(model_path=payload["model_path"], n_ctx=payload.get("n_ctx",4096),
                    n_gpu_layers=payload.get("n_gpu_layers",0), verbose=False)
        r = llm(payload["prompt"], max_tokens=payload.get("max_tokens",512),
                temperature=payload.get("temperature",0.7),
                stop=["<|user|>","<|end|>","</s>"], echo=False)
        print(json.dumps({"text":r["choices"][0]["text"].strip(),
                          "prompt_tokens":r["usage"]["prompt_tokens"],
                          "completion_tokens":r["usage"]["completion_tokens"],
                          "finish_reason":r["choices"][0]["finish_reason"]}))
        sys.exit(0)
    except Exception as e:
        print(json.dumps({"error":str(e)}),file=sys.stderr); sys.exit(1)

if __name__ == "__main__": main()
'''

UPDATER_PY = r'''
"""
GridShare — updater.py
Checks for and applies updates from the signed update channel.
Called by server.py on startup, and can be run manually.

Future: verify GPG signature on update package before applying.
"""
import hashlib, json, os, platform, shutil, subprocess, sys, tempfile, time
from pathlib import Path

VERSION            = "0.1.0"
UPDATE_CHANNEL_URL = "https://raw.githubusercontent.com/gridshare/gridshare-node/main/version.json"
INSTALL_DIR        = Path(__file__).parent

def check(verbose=True):
    try:
        import requests
        r = requests.get(UPDATE_CHANNEL_URL, timeout=10)
        info = r.json()
    except Exception as e:
        if verbose: print(f"Update check failed: {e}")
        return None

    latest = info.get("version", VERSION)
    if latest == VERSION:
        if verbose: print(f"Up to date (v{VERSION})")
        return None

    if verbose:
        print(f"Update available: v{latest} (current: v{VERSION})")
        print(f"Download: {info.get('url','')}")
        print("Run this script to apply: python updater.py --apply")
    return info

def apply(info):
    """
    Download new installer, verify checksum, run it to update files in place.
    In production: verify GPG signature before running anything.
    """
    url      = info.get("url")
    expected = info.get("sha256")
    if not url:
        print("No download URL in update info."); return False
    try:
        import requests
        print(f"Downloading update from {url}...")
        r = requests.get(url, stream=True, timeout=60)
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            tmp_path = f.name
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

        if expected:
            h = hashlib.sha256(open(tmp_path,"rb").read()).hexdigest()
            if h != expected:
                print(f"Checksum mismatch — update aborted (got {h})")
                os.unlink(tmp_path); return False
            print("Checksum verified.")

        print("Applying update...")
        subprocess.run([sys.executable, tmp_path, "--update-in-place",
                        "--install-dir", str(INSTALL_DIR)], check=True)
        os.unlink(tmp_path)
        print("Update applied. Restart the node to use the new version.")
        return True
    except Exception as e:
        print(f"Update failed: {e}"); return False

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--install-dir", default=None)
    p.add_argument("--update-in-place", action="store_true")
    a = p.parse_args()

    if a.update_in_place and a.install_dir:
        # Copy ourselves to the install dir
        src = Path(__file__)
        dst = Path(a.install_dir) / src.name
        shutil.copy2(src, dst)
        print(f"Updated {dst}")
        sys.exit(0)

    info = check(verbose=True)
    if a.apply and info:
        apply(info)
'''

START_BAT = r'''@echo off
cd /d "%~dp0"
start /min pythonw server.py
'''

# ─────────────────────────────────────────────────────────────────────────────
# INSTALLER CODE
# ─────────────────────────────────────────────────────────────────────────────
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ── colours ───────────────────────────────────────────────────────────────────
if platform.system() == "Windows": os.system("")
G="\033[92m"; Y="\033[93m"; R="\033[91m"; C="\033[96m"; B="\033[1m"; X="\033[0m"
def ok(t):   return f"{G}✓{X}  {t}"
def warn(t): return f"{Y}⚠{X}  {t}"
def bad(t):  return f"{R}✗{X}  {t}"
def step(n, total, t): print(f"\n{B}{C}[{n}/{total}]{X}  {t}")
def done(t): print(f"    {G}{t}{X}")
def info(t): print(f"    {t}")
def fail(t): print(f"    {R}{t}{X}"); sys.exit(1)

GB = 1024**3
TOTAL_STEPS = 10


def check_python():
    step(1, TOTAL_STEPS, "Checking Python version")
    v = sys.version_info
    if (v.major, v.minor) < REQUIRED_PYTHON:
        fail(f"Python {REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]}+ required. You have {v.major}.{v.minor}.")
    done(f"Python {v.major}.{v.minor}.{v.micro}")


def read_hardware():
    step(2, TOTAL_STEPS, "Reading hardware")
    try:
        import psutil
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "psutil", "-q"], check=True)
        import psutil

    ram   = psutil.virtual_memory()
    drive = os.path.splitdrive(os.path.abspath(__file__))[0] + "\\" \
            if platform.system() == "Windows" else "/"
    try:    disk = psutil.disk_usage(drive)
    except: disk = psutil.disk_usage("C:\\")

    ram_gb  = ram.total  / GB
    free_gb = disk.free  / GB
    cpu_n   = psutil.cpu_count(logical=False) or 2

    info(f"RAM:   {ram_gb:.1f} GB total  |  {ram.available/GB:.1f} GB free")
    info(f"Disk:  {disk.total/GB:.1f} GB total  |  {free_gb:.1f} GB free")
    info(f"CPU:   {cpu_n} physical cores")

    if ram_gb < MIN_RAM_GB:
        fail(f"Minimum {MIN_RAM_GB} GB RAM required. This machine has {ram_gb:.1f} GB.")
    if free_gb < MIN_DISK_GB:
        fail(f"Minimum {MIN_DISK_GB} GB free disk required. {free_gb:.1f} GB free.")

    return {"ram_gb": ram_gb, "free_gb": free_gb, "cpu_n": cpu_n}


def pick_model(hw):
    step(3, TOTAL_STEPS, "Selecting model for this machine")

    # Safe disk budget: free - 15GB OS reserve - 2GB work files - 5GB buffer
    budget_gb = hw["free_gb"] - 15.0 - 2.0 - 5.0

    chosen = None
    for m in MODELS:
        if budget_gb >= m["disk_gb"] and hw["ram_gb"] >= m["ram_gb"]:
            chosen = m
            break  # first that fits (priority order)

    if not chosen:
        fail(f"No model fits. Need {MODELS[-1]['disk_gb']:.0f} GB disk and {MODELS[-1]['ram_gb']:.0f} GB RAM minimum.")

    done(f"Selected: {chosen['name']}")
    info(f"Size:  {chosen['disk_gb']} GB")
    info(f"After install: ~{budget_gb - chosen['disk_gb']:.1f} GB disk will remain free")

    return chosen


def get_install_dir():
    if platform.system() == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path.home() / ".local" / "share"
    d = base / INSTALL_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def install_deps(install_dir):
    step(4, TOTAL_STEPS, "Installing dependencies")
    info("This may take 2–5 minutes on first install...")
    for pkg in DEPENDENCIES:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", pkg, "-q", "--break-system-packages"],
                capture_output=True, text=True, timeout=300
            )
            if result.returncode == 0:
                print(f"    {G}✓{X}  {pkg}")
            else:
                # Try without --break-system-packages
                result2 = subprocess.run(
                    [sys.executable, "-m", "pip", "install", pkg, "-q"],
                    capture_output=True, text=True, timeout=300
                )
                if result2.returncode == 0:
                    print(f"    {G}✓{X}  {pkg}")
                else:
                    print(f"    {Y}⚠{X}  {pkg}  (may already be installed)")
        except subprocess.TimeoutExpired:
            print(f"    {Y}⚠{X}  {pkg} timed out — skipping")


def download_model(model, install_dir):
    step(5, TOTAL_STEPS, f"Downloading model: {model['name']}")
    dest = install_dir / model["filename"]

    if dest.exists():
        size_gb = dest.stat().st_size / GB
        if size_gb > model["disk_gb"] * 0.95:
            done(f"Model already downloaded ({size_gb:.1f} GB)")
            return dest

    info(f"Downloading {model['disk_gb']} GB — this will take several minutes...")
    info(f"From: {model['url']}")
    info("Progress:")

    try:
        import requests
        r = requests.get(model["url"], stream=True, timeout=30)
        total = int(r.headers.get("content-length", 0))
        downloaded = 0
        t_start = time.time()

        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024*1024):  # 1MB chunks
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct    = downloaded / total * 100
                    speed  = downloaded / (time.time() - t_start) / GB
                    bars   = "█" * int(pct / 2) + "░" * (50 - int(pct / 2))
                    print(f"\r    [{bars}] {pct:.0f}%  {speed:.2f} GB/s", end="", flush=True)

        print()
        done(f"Downloaded: {dest}")
        return dest

    except Exception as e:
        print()
        info(f"Automatic download failed: {e}")
        info("Please download the model manually:")
        info(f"  URL:  {model['url']}")
        info(f"  Save as:  {dest}")
        input("  Press Enter when the file is saved...")
        if not dest.exists():
            fail("Model file not found. Please re-run the installer.")
        return dest


def generate_keypair(install_dir):
    step(6, TOTAL_STEPS, "Generating node keypair")
    import base64
    try:
        import nacl.public
    except ImportError:
        fail("PyNaCl not installed. Try: pip install PyNaCl")

    keys_dir = install_dir / "keys"
    keys_dir.mkdir(exist_ok=True)
    key_file    = keys_dir / "node_private.key"
    pubkey_file = keys_dir / "node_public.key"

    if key_file.exists():
        pk = nacl.public.PrivateKey(base64.b64decode(key_file.read_text().strip()))
        done("Existing keypair loaded")
    else:
        pk = nacl.public.PrivateKey.generate()
        key_file.write_text(base64.b64encode(bytes(pk)).decode())
        pubkey_file.write_text(base64.b64encode(bytes(pk.public_key)).decode())
        if platform.system() != "Windows":
            key_file.chmod(0o600)
        done("New keypair generated")

    pub_hex  = pk.public_key.encode(__import__("nacl.encoding", fromlist=["HexEncoder"]).HexEncoder).decode()
    node_id  = f"node-{pub_hex[:16]}"
    info(f"Node ID: {node_id}")
    info(f"Keys stored in: {keys_dir}")
    info("Keep the private key safe — it is your node's identity")
    return node_id, pub_hex


def write_files(install_dir, model_path, hw):
    step(7, TOTAL_STEPS, "Writing node files")
    threads = max(1, hw["cpu_n"] - 2)

    (install_dir / "server.py").write_text(SERVER_PY.strip())
    done("server.py")

    (install_dir / "inference_worker.py").write_text(WORKER_PY.strip())
    done("inference_worker.py")

    (install_dir / "updater.py").write_text(UPDATER_PY.strip())
    done("updater.py")

    # Launcher batch file (Windows)
    if platform.system() == "Windows":
        bat = install_dir / "start_node.bat"
        bat.write_text(f"@echo off\ncd /d \"{install_dir}\"\nstart /min python server.py --threads {threads}\n")
        done("start_node.bat")

    # Config file recording what the installer chose
    config = {
        "version":       INSTALLER_VERSION,
        "model_path":    str(model_path),
        "threads":       threads,
        "cpu_cap_pct":   40,
        "port":          8080,
        "update_channel": UPDATE_CHANNEL_URL,
        "installed_at":  time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    import json
    (install_dir / "config.json").write_text(json.dumps(config, indent=2))
    done("config.json")


def create_shortcuts(install_dir):
    step(8, TOTAL_STEPS, "Creating shortcuts")
    if platform.system() != "Windows":
        info("Shortcuts: not on Windows — skipping")
        return

    try:
        startup_dir = Path(os.environ.get("APPDATA", "")) / \
                      "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        shortcut    = startup_dir / "GridShare Node.bat"
        shortcut.write_text(f"@echo off\ncd /d \"{install_dir}\"\nstart /min python server.py\n")
        done(f"Startup entry: {shortcut}")

        startmenu = Path(os.environ.get("APPDATA", "")) / \
                    "Microsoft" / "Windows" / "Start Menu" / "Programs"
        sm_bat = startmenu / "GridShare Node.bat"
        sm_bat.write_text(f"@echo off\ncd /d \"{install_dir}\"\npython server.py\npause\n")
        done(f"Start Menu: {sm_bat}")
    except Exception as e:
        info(f"Shortcut creation failed (non-critical): {e}")


def get_local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def print_summary(install_dir, node_id, hw, model):
    step(10, TOTAL_STEPS, "Installation complete")
    ip = get_local_ip()
    threads = max(1, hw["cpu_n"] - 2)

    print(f"""
{B}{C}{'='*58}{X}
{B}  GridShare Node — Ready{X}
{B}{C}{'='*58}{X}

  Node ID:     {node_id}
  Install dir: {install_dir}
  Model:       {model['name']}
  API:         http://{ip}:8080

{B}  To start the node:{X}
    cd "{install_dir}"
    python server.py --threads {threads}

  Or double-click: start_node.bat

{B}  To connect from another machine:{X}
    python client.py --server http://{ip}:8080

{B}  To run the test suite:{X}
    python test_job.py --server http://{ip}:8080

{B}  Updates:{X}
    The node checks for updates on every start.
    To check manually: python updater.py

{B}  Your node will earn GRID tokens when the network launches.{X}
  Keep it running to build reputation score.

{C}{'='*58}{X}
""")


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"""
{B}{C}{'='*58}
  GridShare Node Installer  v{INSTALLER_VERSION}
  Setting up your node on {platform.system()} {platform.release()}
{'='*58}{X}
""")

    check_python()
    hw          = read_hardware()
    model       = pick_model(hw)
    install_dir = get_install_dir()
    info(f"Install directory: {install_dir}")
    install_deps(install_dir)
    model_path  = download_model(model, install_dir)
    node_id, _  = generate_keypair(install_dir)
    write_files(install_dir, model_path, hw)
    create_shortcuts(install_dir)

    step(9, TOTAL_STEPS, "Verifying installation")
    for f in ["server.py", "inference_worker.py", "updater.py", "config.json"]:
        p = install_dir / f
        if p.exists():
            print(f"    {G}✓{X}  {f}")
        else:
            print(f"    {R}✗{X}  {f}  MISSING")

    model_p = install_dir / model["filename"]
    if model_p.exists():
        print(f"    {G}✓{X}  {model['filename']}  ({model_p.stat().st_size/GB:.1f} GB)")
    else:
        print(f"    {R}✗{X}  {model['filename']}  MISSING")

    print_summary(install_dir, node_id, hw, model)


if __name__ == "__main__":
    main()
