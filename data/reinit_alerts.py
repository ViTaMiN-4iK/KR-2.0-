import sys
from pathlib import Path
sys.path.insert(0, "/app")
from data.init_elasticsearch import create_indices, seed_alerts, es_get

info = es_get("/")
print(f"ES version: {info.get('version', {}).get('number', '?')}")
create_indices()
seed_alerts()
