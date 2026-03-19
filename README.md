# GridShare_Setup.exe

Single executable for the spare machine.
No Python, no dependencies, no internet setup required on the spare machine.
Double-click and it runs.

---

## What it does (in order)

1. **Checks internet** — confirms GitHub is reachable
2. **Pulls latest installer** from `github.com/space-ctrl-dot-co/Gridshare-node`
   - Downloads `releases/stable/gridshare_install.py`
   - Verifies the SHA-256 checksum before doing anything
3. **Finds your host machine** automatically
   - Scans the local network for a running GridShare node (port 8080)
   - If not found, asks you to enter the IP manually
4. **Runs the test suite**
   - Ping / connectivity check
   - Models endpoint
   - Encryption pubkey exchange
   - Full inference round-trip: sends `12 × 8 = ?`, expects `96`
   - Reports latency for each phase
5. **Installs the GridShare node on the spare machine**
   - Runs the installer (checks hardware, downloads model, sets up auto-start)
   - Optional — can be skipped
6. **Prints a summary** — green ticks or warnings for each step

---

## How to build the .exe (on your main Windows machine)

**You need:** Python 3.10+, internet access, ~5 minutes.

```
# Option A: one-click
Double-click build_exe.bat

# Option B: manual
pip install pyinstaller
pyinstaller gridshare_setup.spec --clean --noconfirm
```

Output: `dist\GridShare_Setup.exe` (~8-12 MB)

Copy `GridShare_Setup.exe` to the spare machine (USB, network share, email).
The spare machine needs **no Python** and **no setup** — just double-click.

---

## Before running on the spare machine

Make sure the host machine (your laptop) is running the GridShare server:
```
cd %APPDATA%\GridShare
python server.py
```

The exe will scan the local network and find it automatically if both machines
are on the same Wi-Fi or ethernet network.

---

## Files

| File | Purpose |
|------|---------|
| `gridshare_setup.py` | Source — the Python script that becomes the exe |
| `gridshare_setup.spec` | PyInstaller build config |
| `build_exe.bat` | One-click build script |
| `dist/GridShare_Setup.exe` | The output — copy this to the spare machine |
