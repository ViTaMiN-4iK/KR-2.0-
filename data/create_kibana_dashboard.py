import json, subprocess, time

KIBANA_URL = "http://kibana:5601"

def curl(path, method="GET", body=None):
    cmd = ["docker", "exec", "kibana", "curl", "-s", "-X", method,
           KIBANA_URL + path,
           "-H", "Content-Type: application/json",
           "-H", "kbn-xsrf: true"]
    if body:
        cmd += ["-d", json.dumps(body)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(r.stdout) if r.stdout else {}
    except Exception:
        return {"raw": r.stdout[:500]}

print("Waiting for Kibana...")
for _ in range(20):
    r = curl("/api/status")
    lvl = r.get("status", {}).get("overall", {}).get("level", "")
    if lvl == "available":
        print("Kibana ready!")
        break
    time.sleep(2)
else:
    print("Continuing anyway...")


def create_index_pattern(id_, title, time_field=None):
    body = {"attributes": {"title": title, "timeFieldName": time_field,
                           "fields": "[]", "runtimeFieldMap": "{}", "sourceFilters": "[]"}}
    r = curl("/api/index-patterns/" + id_, "POST", body)
    print("  IP", title, ":", "OK" if r.get("id") else str(r.get("error", r))[:80])

print("Creating index patterns...")
create_index_pattern("ip-ueba-events", "ueba-events", "timestamp")
create_index_pattern("ip-ueba-alerts", "ueba-alerts", "timestamp")
create_index_pattern("ip-ueba-users",  "ueba-users",  None)


def create_vis(id_, title, vis_type, index, aggs):
    vis_state = {"title": title, "type": vis_type, "aggs": aggs}
    body = {
        "attributes": {
            "title": title,
            "description": "",
            "visState": json.dumps(vis_state),
            "uiStateJSON": "{}",
            "kibanaSavedObjectMeta": json.dumps({"searchSourceJSON": {"index": index}}),
        }
    }
    r = curl("/api/saved_objects/visualization/" + id_, "POST", body)
    status = "OK" if r.get("id") else str(r.get("error", r))[:80]
    print("  Vis [" + title + "]:", status)
    return r.get("id", "")

print("Creating visualizations...")

create_vis("vis-top-users-alerts", "Top-5 Users by Alert Count", "horizontal_bar", "ueba-alerts", [
    {"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"},
    {"id": "2", "enabled": True, "type": "terms",
     "params": {"field": "username.keyword", "orderBy": "1", "order": "desc", "size": 5},
     "schema": "segment"},
])

create_vis("vis-alerts-severity", "Alerts by Severity", "pie", "ueba-alerts", [
    {"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"},
    {"id": "2", "enabled": True, "type": "terms",
     "params": {"field": "severity.keyword", "orderBy": "1", "order": "desc", "size": 10},
     "schema": "segment"},
])

create_vis("vis-events-by-hour", "Events by Hour of Day", "area", "ueba-events", [
    {"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"},
    {"id": "2", "enabled": True, "type": "histogram",
     "params": {"field": "hour", "interval": 1, "minDocCount": 0},
     "schema": "segment"},
])

create_vis("vis-alerts-user", "Alerts by User ID", "bar", "ueba-alerts", [
    {"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"},
    {"id": "2", "enabled": True, "type": "terms",
     "params": {"field": "user_id", "orderBy": "1", "order": "desc", "size": 20},
     "schema": "segment"},
])

create_vis("vis-risk-level", "Alerts by Risk Level", "pie", "ueba-alerts", [
    {"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"},
    {"id": "2", "enabled": True, "type": "terms",
     "params": {"field": "risk_level.keyword", "orderBy": "1", "order": "desc", "size": 6},
     "schema": "segment"},
])

create_vis("vis-risk-over-time", "Average Risk Score Over Time", "line", "ueba-events", [
    {"id": "1", "enabled": True, "type": "avg", "params": {"field": "risk_score"}, "schema": "metric"},
    {"id": "2", "enabled": True, "type": "date_histogram",
     "params": {"field": "timestamp", "interval": "auto", "minDocCount": 1},
     "schema": "segment"},
])

print("Creating dashboard...")
panels = [
    {"version": "8.15.0", "gridData": {"x": 0,  "y": 0,  "w": 24, "h": 12, "i": "1"}, "panelIndex": "1", "panelRefName": "panel_1", "embeddableConfig": {}, "enhancements": {}},
    {"version": "8.15.0", "gridData": {"x": 24, "y": 0,  "w": 24, "h": 12, "i": "2"}, "panelIndex": "2", "panelRefName": "panel_2", "embeddableConfig": {}, "enhancements": {}},
    {"version": "8.15.0", "gridData": {"x": 0,  "y": 12, "w": 16, "h": 12, "i": "3"}, "panelIndex": "3", "panelRefName": "panel_3", "embeddableConfig": {}, "enhancements": {}},
    {"version": "8.15.0", "gridData": {"x": 16, "y": 12, "w": 32, "h": 12, "i": "4"}, "panelIndex": "4", "panelRefName": "panel_4", "embeddableConfig": {}, "enhancements": {}},
    {"version": "8.15.0", "gridData": {"x": 0,  "y": 24, "w": 24, "h": 12, "i": "5"}, "panelIndex": "5", "panelRefName": "panel_5", "embeddableConfig": {}, "enhancements": {}},
    {"version": "8.15.0", "gridData": {"x": 24, "y": 24, "w": 24, "h": 12, "i": "6"}, "panelIndex": "6", "panelRefName": "panel_6", "embeddableConfig": {}, "enhancements": {}},
]

body = {
    "attributes": {
        "title": "UEBA Security Overview",
        "description": "User and Entity Behavior Analytics dashboard",
        "hits": 0,
        "panelsJSON": json.dumps(panels),
        "optionsJSON": json.dumps({"useMargins": True, "hidePanelTitles": False}),
        "version": 1,
        "timeRange": json.dumps({"from": "now-30d", "to": "now"}),
        "refreshInterval": json.dumps({"pause": False, "value": 60000}),
    },
    "references": [
        {"id": "vis-top-users-alerts", "name": "panel_1", "type": "visualization"},
        {"id": "vis-alerts-severity",  "name": "panel_2", "type": "visualization"},
        {"id": "vis-events-by-hour",    "name": "panel_3", "type": "visualization"},
        {"id": "vis-alerts-user",        "name": "panel_4", "type": "visualization"},
        {"id": "vis-risk-level",         "name": "panel_5", "type": "visualization"},
        {"id": "vis-risk-over-time",     "name": "panel_6", "type": "visualization"},
    ]
}

r = curl("/api/saved_objects/dashboard/ueba-dashboard", "POST", body)
if r.get("id"):
    did = r["id"]
    print("Dashboard created! Open: http://localhost:5601/app/dashboards#/view/" + did)
else:
    print("Dashboard error:", str(r.get("error", r))[:200])
