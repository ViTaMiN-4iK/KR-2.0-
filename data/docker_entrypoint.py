#!/usr/bin/env python3
"""Entry point for the API container."""
from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path

os.chdir("/app")

data_dir = Path("data")
if not (data_dir / "events.csv").exists():
    print("[UEBA] Generating synthetic data...")
    result = subprocess.run([sys.executable, "data/generate_logs.py"], capture_output=True, text=True)
    if result.returncode == 0:
        print("[UEBA] Data generated successfully")
    else:
        print(f"[UEBA] Data generation failed: {result.stderr}")

try:
    print("[UEBA] Setting up Elasticsearch indices...")
    sys.path.insert(0, "/app")
    from data.init_elasticsearch import create_indices, seed_events, seed_users, seed_alerts
    create_indices()
    seed_events()
    seed_users()
    seed_alerts()
except SystemExit:
    pass
except Exception as e:
    print(f"[UEBA] ES init warning: {e}")

print("[UEBA] Starting API server on port 8000...")
os.execvp("uvicorn", ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"])
