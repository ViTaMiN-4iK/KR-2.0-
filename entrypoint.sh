#!/usr/bin/env python3
"""Entry point for the API container."""
import os
import sys
import time
from pathlib import Path

os.chdir("/app")

# Generate data
data_dir = Path("data")
if not (data_dir / "events.csv").exists():
    print("[UEBA] Generating synthetic data...")
    sys.path.insert(0, "/app")
    from data.generate_logs import generate_dataset
    generate_dataset(output_dir="data")

# Try to init ES (may fail if ES not ready yet)
try:
    print("[UEBA] Setting up Elasticsearch indices...")
    sys.path.insert(0, "/app")
    from data.init_elasticsearch import create_indices
    es_url = os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")
    create_indices(es_url)
except Exception as e:
    print(f"[UEBA] ES init warning: {e}")

# Run the API
print("[UEBA] Starting API server on port 8000...")
os.execvp("uvicorn", ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"])
