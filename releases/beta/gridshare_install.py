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
UPDATE_CHANNEL_URL = "https://raw.githubusercontent.com/space-ctrl-dot-co/Gridshare-node/main/releases/beta/version.json"
REQUIRED_PYTHON    = (3, 10)
MIN_RAM_GB         = 4.0
MIN_DISK_GB        = 8.0

DEPENDENCIES = [
    "llama-cpp-python",
    "fastapi",
    "uvicorn",
