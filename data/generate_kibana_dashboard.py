#!/usr/bin/env python3
"""Генерация Kibana Saved Objects (ndjson) для UEBA Dashboard."""

import json
from datetime import datetime

KB_VERSION = "8.15.0"
KB_SPACE = "default"
TIMESTAMP = datetime.utcnow().isoformat() + "Z"

def ref(type_, id_):
    return {"id": id_, "name": type_ + "_" + id_, "type": type_}

# ── Index Patterns ─────────────────────────────────────────────
def make_index_pattern(index, id_, title, time_field):
    return {
        "id": id_,
        "type": "index-pattern",
        "attributes": {
            "title": index,
            "timeFieldName": time_field,
            "fields": "[]",
            "runtimeFieldMap": "{}",
            "sourceFilters": "[]",
            "titleObject": {"label": index, "name": index},
        },
        "references": [],
        "coreMigrationVersion": KB_VERSION,
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
    }

# ── Lens Visualizations (LENS type) ───────────────────────────
def lens_vis(id_, title, state_datasource):
    return {
        "id": id_,
        "type": "lens",
        "attributes": {
            "title": title,
            "description": "",
            "state": json.dumps(state_datasource),
            "references": [],
        },
        "references": [],
        "coreMigrationVersion": KB_VERSION,
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
    }

# ── Dashboard ─────────────────────────────────────────────────
def make_dashboard(panels_json):
    return {
        "id": "ueba-dashboard",
        "type": "dashboard",
        "attributes": {
            "title": "UEBA Security Overview",
            "description": "User and Entity Behavior Analytics overview",
            "panelsJSON": json.dumps(panels_json),
            "optionsJSON": json.dumps({
                "useMargins": True,
                "hidePanelTitles": False,
                "syncColors": False,
                "syncCursor": True,
                "syncTooltips": False,
                "hideExportAsPdf": False,
            }),
            "timeRange": json.dumps({"to": "now", "from": "now-30d"}),
            "refreshInterval": json.dumps({
                "pause": False,
                "value": 60000,
            }),
            "kibanaSavedObjectMeta": json.dumps({
                "searchSourceJSON": "{}",
            }),
            "version": 1,
        },
        "references": [],
        "coreMigrationVersion": KB_VERSION,
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
    }


# ── Build objects ──────────────────────────────────────────────

objects = []

# Index patterns
objects.append(make_index_pattern("ueba-events",  "ip-ueba-events",  "ueba-events",  "timestamp"))
objects.append(make_index_pattern("ueba-alerts",  "ip-ueba-alerts",  "ueba-alerts",  "timestamp"))
objects.append(make_index_pattern("ueba-users",   "ip-ueba-users",   "ueba-users",   None))

# ── 1. Top-5 пользователей по алертам (Bar, ueba-alerts) ────────
objects.append(lens_vis(
    "vis-top-users-alerts",
    "Top-5 Users by Alert Count",
    {
        "datasourceStates": {
            "indexpattern:ip-ueba-alerts": {
                "layers": {
                    "layer-1": {
                        "columnOrder": ["user_id", "alert_id"],
                        "columns": {
                            "user_id": {"label": "User ID", "dataType": "string", "operationType": "terms", "params": {"size": 5, "orderBy": {"columnId": "alert_count"}, "orderDirection": "desc"}},
                            "alert_count": {"label": "Count", "dataType": "number", "operationType": "count"},
                        }
                    }
                }
            }
        },
        "visualization": {
            "axisTitlesVisibilitySettings": {"x": True, "yLeft": True, "yRight": True},
            "layers": [{
                "layerId": "layer-1",
                "accessors": ["alert_count"],
                "position": "top",
                "seriesType": "bar_horizontal",
                "showGridlines": False,
                "layerType": "data",
                "xAccessor": "user_id",
                "splitAccessor": "alert_count",
            }],
            "legend": {"isVisible": False},
            "preferredSeriesType": "bar_horizontal",
            "title": "Top-5 Users by Alert Count",
            "valueLabels": "show",
        }
    }
))

# ── 2. Распределение по severity (Pie, ueba-alerts) ─────────────
objects.append(lens_vis(
    "vis-alerts-severity",
    "Alerts by Severity",
    {
        "datasourceStates": {
            "indexpattern:ip-ueba-alerts": {
                "layers": {
                    "layer-1": {
                        "columns": {
                            "severity": {"label": "Severity", "dataType": "string", "operationType": "terms", "params": {"size": 10}},
                            "count": {"label": "Count", "dataType": "number", "operationType": "count"},
                        }
                    }
                }
            }
        },
        "visualization": {
            "layers": [{
                "layerId": "layer-1",
                "accessors": ["count"],
                "seriesType": "pie",
                "xAccessor": "severity",
                "layerType": "data",
            }],
            "legend": {"isVisible": True, "position": "right"},
            "preferredSeriesType": "pie",
            "title": "Alerts by Severity",
            "valueLabels": "show",
        }
    }
))

# ── 3. Активность по часам (Line, ueba-events) ─────────────────
objects.append(lens_vis(
    "vis-activity-by-hour",
    "Event Activity by Hour",
    {
        "datasourceStates": {
            "indexpattern:ip-ueba-events": {
                "layers": {
                    "layer-1": {
                        "columns": {
                            "hour": {"label": "Hour", "dataType": "number", "operationType": "range", "params": {"ranges": [{"from": 0, "to": 6, "label": "Night (0-6)"}, {"from": 6, "to": 18, "label": "Day (6-18)"}, {"from": 18, "to": 24, "label": "Evening (18-24)"}]}},
                            "count": {"label": "Events", "dataType": "number", "operationType": "count"},
                        }
                    }
                }
            }
        },
        "visualization": {
            "layers": [{
                "layerId": "layer-1",
                "accessors": ["count"],
                "seriesType": "area_stacked",
                "xAccessor": "hour",
                "layerType": "data",
            }],
            "legend": {"isVisible": True},
            "preferredSeriesType": "area_stacked",
            "title": "Event Activity by Hour",
        }
    }
))

# ── 4. Алерты по департаментам (Bar, ueba-alerts) ───────────────
objects.append(lens_vis(
    "vis-alerts-department",
    "Alerts by Department",
    {
        "datasourceStates": {
            "indexpattern:ip-ueba-alerts": {
                "layers": {
                    "layer-1": {
                        "columns": {
                            "department": {"label": "Department", "dataType": "string", "operationType": "terms", "params": {"size": 10}},
                            "count": {"label": "Alerts", "dataType": "number", "operationType": "count"},
                        }
                    }
                }
            }
        },
        "visualization": {
            "layers": [{
                "layerId": "layer-1",
                "accessors": ["count"],
                "seriesType": "bar",
                "xAccessor": "department",
                "layerType": "data",
            }],
            "legend": {"isVisible": False},
            "preferredSeriesType": "bar",
            "title": "Alerts by Department",
            "valueLabels": "show",
        }
    }
))

# ── 5. Типы атак / action (Tag cloud / Bar, ueba-alerts) ──────
objects.append(lens_vis(
    "vis-top-actions",
    "Top Detected Actions",
    {
        "datasourceStates": {
            "indexpattern:ip-ueba-alerts": {
                "layers": {
                    "layer-1": {
                        "columns": {
                            "action": {"label": "Action", "dataType": "string", "operationType": "terms", "params": {"size": 15}},
                            "count": {"label": "Count", "dataType": "number", "operationType": "count"},
                        }
                    }
                }
            }
        },
        "visualization": {
            "layers": [{
                "layerId": "layer-1",
                "accessors": ["count"],
                "seriesType": "bar",
                "xAccessor": "action",
                "layerType": "data",
            }],
            "legend": {"isVisible": False},
            "preferredSeriesType": "bar",
            "title": "Top Detected Actions",
            "valueLabels": "show",
        }
    }
))

# ── 6. Риск-скор по дням (Line, ueba-events) ──────────────────
objects.append(lens_vis(
    "vis-risk-over-time",
    "Average Risk Score Over Time",
    {
        "datasourceStates": {
            "indexpattern:ip-ueba-events": {
                "layers": {
                    "layer-1": {
                        "columns": {
                            "timestamp": {"label": "Timestamp", "dataType": "date", "operationType": "date_histogram", "params": {"interval": "1d"}},
                            "risk_score": {"label": "Avg Risk Score", "dataType": "number", "operationType": "average"},
                        }
                    }
                }
            }
        },
        "visualization": {
            "layers": [{
                "layerId": "layer-1",
                "accessors": ["risk_score"],
                "seriesType": "line",
                "xAccessor": "timestamp",
                "layerType": "data",
            }],
            "legend": {"isVisible": True},
            "preferredSeriesType": "line",
            "title": "Average Risk Score Over Time",
        }
    }
))

# ── Dashboard ───────────────────────────────────────────────────
panels = [
    {"version": KB_VERSION, "type": "lens",       "gridData": {"x": 0,  "y": 0,  "w": 24, "h": 8},  "panelIndex": "panel-1", "embeddableConfig": {"attributes": {}, "enhancements": {}}, "panelRefName": "panel_1"},
    {"version": KB_VERSION, "type": "lens",       "gridData": {"x": 24, "y": 0,  "w": 24, "h": 8},  "panelIndex": "panel-2", "embeddableConfig": {"attributes": {}, "enhancements": {}}, "panelRefName": "panel_2"},
    {"version": KB_VERSION, "type": "lens",       "gridData": {"x": 0,  "y": 8,  "w": 16, "h": 8},  "panelIndex": "panel-3", "embeddableConfig": {"attributes": {}, "enhancements": {}}, "panelRefName": "panel_3"},
    {"version": KB_VERSION, "type": "lens",       "gridData": {"x": 16, "y": 8,  "w": 32, "h": 8},  "panelIndex": "panel-4", "embeddableConfig": {"attributes": {}, "enhancements": {}}, "panelRefName": "panel_4"},
    {"version": KB_VERSION, "type": "lens",       "gridData": {"x": 0,  "y": 16, "w": 24, "h": 8},  "panelIndex": "panel-5", "embeddableConfig": {"attributes": {}, "enhancements": {}}, "panelRefName": "panel_5"},
    {"version": KB_VERSION, "type": "lens",       "gridData": {"x": 24, "y": 16, "w": 24, "h": 8},  "panelIndex": "panel-6", "embeddableConfig": {"attributes": {}, "enhancements": {}}, "panelRefName": "panel_6"},
]

objects.append(make_dashboard(panels))

# ── Write NDJSON ────────────────────────────────────────────────
output = Path(__file__).parent / "kibana_ueba_dashboard.ndjson"
with open(output, "w", encoding="utf-8") as f:
    for obj in objects:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

print(f"Written {len(objects)} objects to {output}")
