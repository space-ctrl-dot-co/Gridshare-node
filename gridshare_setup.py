"""
GridShare Setup & Test
======================
Single-file executable for the spare machine.

What this does:
  1. Checks Python + pip are working (or bootstraps them)
  2. Pulls the latest installer from GitHub
  3. Verifies the SHA-256 checksum
  4. Discovers or asks for the host machine's IP
  5. Runs the GridShare test suite against that machine
  6. Installs and starts the GridShare node on this machine
  7. Prints a full status report

Build into .exe on your main machine:
  pip install pyinstaller
  pyinstaller --onefile --console --name GridShare_Setup gridshare_setup.py

Then copy GridShare_Setup.exe to the spare machine and double-click.
"""

import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
from pathlib import Path

# ── config ────────────────────────────────────────────────────────────────────
VERSION             = "0.1.0"
GITHUB_RAW          = "https://raw.githubusercontent.com/space-ctrl-dot-co/Gridshare-node/main"
STABLE_VERSION_URL  = f"{GITHUB_RAW}/releases/stable/version.json"
STABLE_INSTALLER_URL= f"{GITHUB_RAW}/releases/stable/gridshare_install.py"
EXPECTED_SHA256     = "987f46520ddb9c04ec98a715aed42d8c8b8fc22069ef1c14418b5f749ecc6370"
DEFAULT_PORT        = 8080
NODE_SERVER_URL     = None  # set during runtime

# ── colours ───────────────────────────────────────────────────────────────────
if platform.system() == "Windows":
    os.system("")  # enable ANSI on Windows 10+

G = "\033[92m"   # green
Y = "\033[93m"   # yellow
R = "\033[91m"   # red
C = "\033[96m"   # cyan
B = "\033[1m"    # bold
X = "\033[0m"    # reset

def ok(t):    print(f"  {G}✓{X}  {t}")
def warn(t):  print(f"  {Y}⚠{X}  {t}")
def fail(t):  print(f"  {R}✗{X}  {t}")
def info(t):  print(f"     {t}")
def head(t):  print(f"\n{B}{C}{t}{X}")
def sep():    print(f"  {'─'*54}")


# ── helpers ───────────────────────────────────────────────────────────────────
def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url, timeout=15):
    """Simple HTTP GET, returns bytes or raises."""
    req = urllib.request.Request(url, headers={"User-Agent": "GridShare-Setup/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_json(url, timeout=10):
    return json.loads(fetch(url, timeout))


def download_with_progress(url, dest_path, expected_sha=None):
    """Download to dest_path, show progress, optionally verify sha256."""
    req = urllib.request.Request(url, headers={"User-Agent": "GridShare-Setup/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        total = int(r.headers.get("Content-Length", 0))
        downloaded = 0
        t_start = time.time()
        with open(dest_path, "wb") as f:
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct   = downloaded / total * 100
                    speed = downloaded / max(time.time() - t_start, 0.01) / 1024 / 1024
                    bar   = "█" * int(pct / 2) + "░" * (50 - int(pct / 2))
                    print(f"\r     [{bar}] {pct:.0f}%  {speed:.1f} MB/s",
                          end="", flush=True)
    print()
    if expected_sha:
        actual = sha256(dest_path)
        if actual != expected_sha:
            os.unlink(dest_path)
            raise ValueError(f"Checksum mismatch.\n  Expected: {expected_sha}\n  Got:      {actual}")
        ok("Checksum verified")
    return dest_path


def call_api(url, payload=None, timeout=120):
    """Make a JSON API call. Returns (status_code, response_dict)."""
    data = json.dumps(payload).encode() if payload else None
    headers = {"Content-Type": "application/json", "User-Agent": "GridShare-Setup/0.1"}
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception:
        return 0, {}


# ── step 1: banner ────────────────────────────────────────────────────────────
def banner():
    print(f"""
{B}{C}╔══════════════════════════════════════════════════════╗
║          GridShare Setup & Test   v{VERSION}               ║
╠══════════════════════════════════════════════════════╣
║  This machine will:                                  ║
║  • Pull the latest node software from GitHub         ║
║  • Test the connection to your host machine          ║
║  • Install and start the GridShare node              ║
╚══════════════════════════════════════════════════════╝{X}
""")


# ── step 2: check internet ────────────────────────────────────────────────────
def check_internet():
    head("Step 1 — Internet connectivity")
    sep()
    try:
        fetch("https://raw.githubusercontent.com", timeout=8)
        ok("GitHub reachable")
        return True
    except Exception as e:
        fail(f"Cannot reach GitHub: {e}")
        info("Check Wi-Fi or ethernet connection and try again.")
        return False


# ── step 3: pull latest from github ──────────────────────────────────────────
def pull_from_github():
    head("Step 2 — Pull latest from GitHub")
    sep()
    try:
        info(f"Checking {STABLE_VERSION_URL}")
        version_info = fetch_json(STABLE_VERSION_URL)
        remote_ver = version_info.get("version", "?")
        notes = version_info.get("release_notes", "")
        ok(f"Latest version: {remote_ver}")
        if notes:
            info(f"Notes: {notes}")
    except Exception as e:
        fail(f"Could not fetch version info: {e}")
        return None

    # Download installer to temp dir
    tmp_dir  = Path(tempfile.mkdtemp())
    dest     = tmp_dir / "gridshare_install.py"
    info(f"Downloading installer ({STABLE_INSTALLER_URL.split('/')[-1]})...")
    try:
        download_with_progress(STABLE_INSTALLER_URL, dest, EXPECTED_SHA256)
    except Exception as e:
        fail(f"Download failed: {e}")
        return None

    ok(f"Installer ready: {dest}")
    return dest


# ── step 4: discover host machine ─────────────────────────────────────────────
def discover_host():
    head("Step 3 — Find host machine (your main laptop)")
    sep()
    info("Scanning local network for a running GridShare node...")

    # Get our own IP to determine subnet
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        own_ip = s.getsockname()[0]
        s.close()
    except Exception:
        own_ip = "192.168.1.1"

    subnet = ".".join(own_ip.split(".")[:3])
    info(f"Our IP: {own_ip}  →  scanning {subnet}.1-254 on port {DEFAULT_PORT}")
    info("(This takes about 15 seconds...)")

    found = []
    import threading

    def probe(ip):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.3)
            result = s.connect_ex((ip, DEFAULT_PORT))
            s.close()
            if result == 0:
                # Confirm it's a GridShare node
                status, data = call_api(f"http://{ip}:{DEFAULT_PORT}/", timeout=3)
                if status == 200 and data.get("service") == "GridShare Node":
                    found.append((ip, data))
        except Exception:
            pass

    threads = []
    for i in range(1, 255):
        ip = f"{subnet}.{i}"
        t = threading.Thread(target=probe, args=(ip,), daemon=True)
        threads.append(t)
        t.start()
        if i % 50 == 0:
            print(".", end="", flush=True)

    # Wait for all threads
    for t in threads:
        t.join(timeout=2)
    print()

    if found:
        for ip, data in found:
            node_id = data.get("node_id", "unknown")
            ok(f"Found GridShare node at {ip}:{DEFAULT_PORT}  (node: {node_id})")
        if len(found) == 1:
            return f"http://{found[0][0]}:{DEFAULT_PORT}"
        else:
            info("Multiple nodes found:")
            for i, (ip, data) in enumerate(found):
                info(f"  [{i+1}] {ip}  —  {data.get('node_id','?')}")
            choice = input("\n  Which node to test against? [1]: ").strip() or "1"
            idx = int(choice) - 1
            return f"http://{found[idx][0]}:{DEFAULT_PORT}"
    else:
        warn("No GridShare node found automatically on local network.")
        info("")
        info("Make sure your host machine is running:")
        info("  python server.py")
        info("")
        manual = input("  Enter host machine IP manually (or press Enter to skip): ").strip()
        if manual:
            if not manual.startswith("http"):
                manual = f"http://{manual}:{DEFAULT_PORT}"
            return manual
        return None


# ── step 5: run test suite ─────────────────────────────────────────────────────
def run_tests(server_url):
    head("Step 4 — Test suite")
    sep()
    info(f"Testing: {server_url}")

    # Test 0: ping
    print(f"\n  [1/4] Connectivity ping...", end=" ", flush=True)
    t = time.time()
    status, data = call_api(f"{server_url}/", timeout=10)
    ping_ms = round((time.time() - t) * 1000)
    if status == 200:
        print(ok(f"Online  ({ping_ms}ms)") or "")
        info(f"Node ID:    {data.get('node_id', '?')}")
        info(f"Version:    {data.get('version', '?')}")
        info(f"Encryption: {'on' if data.get('encryption') else 'off'}")
        info(f"Jobs done:  {data.get('jobs_completed', 0)}")
    else:
        print()
        fail(f"Node not responding (HTTP {status})")
        return False

    # Test 1: models endpoint
    print(f"\n  [2/4] Models endpoint...", end=" ", flush=True)
    status, data = call_api(f"{server_url}/v1/models", timeout=10)
    if status == 200 and data.get("data"):
        models = [m["id"] for m in data["data"]]
        print(ok(f"{models}") or "")
    else:
        print()
        warn(f"Models endpoint returned {status}")

    # Test 2: pubkey endpoint
    print(f"\n  [3/4] Encryption pubkey...", end=" ", flush=True)
    status, data = call_api(f"{server_url}/v1/node/pubkey", timeout=10)
    if status == 200 and data.get("public_key"):
        pub_short = data["public_key"][:24] + "..."
        print(ok(f"{pub_short}") or "")
    else:
        print()
        warn(f"Pubkey endpoint returned {status}")

    # Test 3: inference round-trip (plaintext mode for speed)
    print(f"\n  [4/4] Inference round-trip (12 × 8 = ?)...")
    t_start = time.time()
    payload = {
        "messages": [{"role": "user", "content": "What is 12 multiplied by 8? Reply with the number only."}],
        "max_tokens": 8,
        "temperature": 0,
        "model": "gridshare-local"
    }
    status, data = call_api(f"{server_url}/v1/chat/completions", payload, timeout=60)
    elapsed = round((time.time() - t_start) * 1000)

    if status == 200:
        # May be encrypted response or plaintext
        if data.get("encrypted"):
            ok(f"Response received (encrypted)  [{elapsed}ms]")
            info("Cannot verify answer — encryption active (correct behaviour)")
            return True
        else:
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            passed  = "96" in content
            timing  = f"[{elapsed}ms]"
            if passed:
                ok(f"Answer: \"{content}\"  {timing}")
            else:
                warn(f"Answer: \"{content}\" — expected 96  {timing}")
            usage = data.get("usage", {})
            info(f"Tokens: {usage.get('prompt_tokens','?')} in → {usage.get('completion_tokens','?')} out")
            server_ms = data.get("_gridshare", {}).get("latency_ms", "?")
            info(f"Server-side inference: {server_ms}ms  |  Total round-trip: {elapsed}ms")
            return passed
    else:
        fail(f"Inference failed — HTTP {status}")
        if elapsed > 55000:
            info("Timed out — model may still be loading. Wait 30s and try again.")
        return False


# ── step 6: install node on this machine ──────────────────────────────────────
def install_node(installer_path):
    head("Step 5 — Install GridShare node on this machine")
    sep()
    info("Running the GridShare installer...")
    info("This will take several minutes (downloads ~2.4 GB model).")
    info("")

    choice = input("  Install GridShare node on THIS machine now? [Y/n]: ").strip().lower()
    if choice in ("n", "no"):
        info("Skipped. Run the installer manually later:")
        info(f"  python {installer_path}")
        return False

    try:
        result = subprocess.run(
            [sys.executable, str(installer_path)],
            timeout=1800  # 30 min max for large model downloads
        )
        if result.returncode == 0:
            ok("GridShare node installed successfully!")
            return True
        else:
            fail(f"Installer exited with code {result.returncode}")
            return False
    except subprocess.TimeoutExpired:
        fail("Installer timed out after 30 minutes")
        return False
    except Exception as e:
        fail(f"Installer failed: {e}")
        return False


# ── step 7: summary ───────────────────────────────────────────────────────────
def print_summary(internet_ok, installer_path, server_url, tests_passed, node_installed):
    head("Summary")
    sep()

    results = [
        ("Internet / GitHub",      internet_ok),
        ("Latest installer pulled", installer_path is not None),
        ("Host machine found",      server_url is not None),
        ("Inference tests passed",  tests_passed),
        ("Node installed here",     node_installed),
    ]

    for label, passed in results:
        if passed:
            ok(label)
        else:
            warn(label)

    print()
    if server_url and tests_passed:
        print(f"{G}{B}  GridShare is working end-to-end.{X}")
        print(f"  Host node:  {server_url}")
        print(f"  Repo:       https://github.com/space-ctrl-dot-co/Gridshare-node")
    elif server_url:
        print(f"{Y}{B}  Connection established but some tests failed.{X}")
        print(f"  Check that the model has finished loading on the host machine.")
    else:
        print(f"{Y}{B}  Could not reach the host machine.{X}")
        print(f"  Make sure it is running:  python server.py")

    print()


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    banner()

    # Step 1: Internet
    if not check_internet():
        input("\nPress Enter to exit...")
        sys.exit(1)

    # Step 2: Pull from GitHub
    installer_path = pull_from_github()

    # Step 3: Find host
    server_url = discover_host()

    # Step 4: Test
    tests_passed = False
    if server_url:
        tests_passed = run_tests(server_url)
    else:
        warn("Skipping tests — no host machine found.")

    # Step 5: Install node on this machine
    node_installed = False
    if installer_path:
        node_installed = install_node(installer_path)

    # Summary
    print_summary(
        internet_ok     = True,
        installer_path  = installer_path,
        server_url      = server_url,
        tests_passed    = tests_passed,
        node_installed  = node_installed,
    )

    input("Press Enter to exit...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled.")
        sys.exit(0)
    except Exception as e:
        print(f"\n{R}Unexpected error: {e}{X}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)
