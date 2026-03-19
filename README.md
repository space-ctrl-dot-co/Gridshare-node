# GridShare Node
**Distributed AI compute network — node software**

[![Status](https://img.shields.io/badge/status-MVP%20live-brightgreen)](https://github.com/space-ctrl-dot-co/Gridshare-node)
[![Version](https://img.shields.io/badge/version-0.1.0-blue)](https://github.com/space-ctrl-dot-co/Gridshare-node/releases)

Turn idle laptops into revenue-generating AI inference nodes.
Requesters get affordable AI. Providers earn GRID tokens.

---

## Quick install (Windows)

```bash
# Download gridshare_install.py from releases/stable/ then:
python gridshare_install.py
```

One file. Checks your hardware, downloads the right model, sets up auto-start.

---

## Update channels

| Channel | Version | URL |
|---------|---------|-----|
| Stable | 0.1.0 | `releases/stable/version.json` |
| Beta | 0.1.0 | `releases/beta/version.json` |

Nodes check for updates on every startup via the raw GitHub URLs.
To publish a new release: bump version in `version.json`, update the SHA-256, push.

---

## Repo structure

```
releases/
  stable/
    version.json          # update channel manifest
    gridshare_install.py  # installer for stable channel
  beta/
    version.json
    gridshare_install.py
updater.py                # standalone auto-update client
README.md
```

---

## What the installer does

1. Checks Python 3.10+ and pip
2. Reads hardware — RAM, disk, CPU, GPU
3. Picks the right model (Phi-3.5 Mini or Llama 3.2 3B)
4. Installs all Python dependencies
5. Downloads the model file (~2.4 GB)
6. Generates a node keypair (your identity on the network)
7. Writes `server.py`, `inference_worker.py`, `updater.py` to `%APPDATA%\\GridShare\\`
8. Creates a Windows startup entry — node runs in background on boot
9. Verifies installation
10. Prints node ID and connection details

---

## Architecture

- **Encryption**: NaCl Box — prompts encrypted end-to-end, providers never see plaintext
- **Sandbox**: Subprocess isolation (MVP) → Wasmtime WASM (Phase 1)
- **API**: OpenAI-compatible — drop-in replacement, change one URL
- **Updates**: SHA-256 verified, silent, wireless

Full specification: `GridShare_Specification_v0.2.docx` (see project files)

---

*Part of the GridShare project — [spacectrl.co](https://www.spacectrl.co)*
