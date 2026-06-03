# UEBA System - API Documentation

## Base URL

```
http://localhost:8000/api
```

## Authentication

Currently no authentication required (development mode).
For production, add JWT/OAuth2 middleware.

---

## Alerts

### List Alerts

```
GET /api/alerts
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status: `open`, `investigating`, `confirmed`, `false_positive`, `resolved` |
| `risk_level` | string | Filter by risk: `low`, `medium`, `high`, `critical` |
| `user_id` | string | Filter by user ID |
| `page` | integer | Page number (default: 1) |
| `page_size` | integer | Items per page (default: 20, max: 100) |

**Response:**

```json
{
  "total": 42,
  "alerts": [
    {
      "alert_id": "550e8400-e29b-41d4-a716-446655440000",
      "event_id": "evt_0042",
      "user_id": "user_003",
      "username": "user_003@company.local",
      "timestamp": "2026-01-15T03:30:00Z",
      "anomaly_score": 0.8472,
      "risk_level": "high",
      "detected_by_model": "isolation_forest",
      "reason": "действие в ночное время; необычное время активности",
      "status": "open",
      "severity": "high",
      "created_at": "2026-01-15T04:00:00Z",
      "updated_at": "2026-01-15T04:00:00Z",
      "investigation_notes": "",
      "resolved_by": ""
    }
  ],
  "page": 1,
  "page_size": 20
}
```

---

### Get Alert

```
GET /api/alerts/{alert_id}
```

**Response:** Single alert object (same structure as in list).

**Errors:**
- `404` - Alert not found

---

### Update Alert

```
PATCH /api/alerts/{alert_id}
```

**Request Body:**

```json
{
  "status": "investigating",
  "notes": "Looking into unusual login time",
  "resolved_by": "analyst_1"
}
```

All fields are optional.

**Response:** Updated alert object.

---

### Get Alert Stats

```
GET /api/alerts/stats
```

**Response:**

```json
{
  "total": 42,
  "open": 15,
  "investigating": 5,
  "confirmed": 3,
  "resolved": 17,
  "false_positive": 2,
  "by_status": {
    "open": 15,
    "investigating": 5,
    "confirmed": 3
  },
  "by_risk_level": {
    "critical": 2,
    "high": 8,
    "medium": 12,
    "low": 20
  },
  "avg_score": 0.5234
}
```

---

## Users

### List Users

```
GET /api/users
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `department` | string | Filter by department |
| `role` | string | Filter by role |
| `risk_status` | string | Filter: `normal`, `suspicious`, `compromised` |
| `page` | integer | Page number |
| `page_size` | integer | Items per page |

**Response:**

```json
{
  "total": 50,
  "users": [
    {
      "user_id": "user_001",
      "username": "user_001@company.local",
      "full_name": "User 1",
      "role": "developer",
      "department": "IT",
      "total_events": 234,
      "unique_actions": 7,
      "unique_locations": 3,
      "avg_hour": 10.5,
      "unique_resources": 15,
      "avg_bytes_sent": 15420.5,
      "avg_bytes_received": 87650.3,
      "failed_ratio": 0.03,
      "anomaly_score_max": 0.8231,
      "risk_status": "suspicious"
    }
  ]
}
```

---

### Get User

```
GET /api/users/{user_id}
```

Single user profile object.

---

### Get User Events

```
GET /api/users/{user_id}/events
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `start_date` | string | ISO datetime start |
| `end_date` | string | ISO datetime end |
| `page` | integer | Page number |
| `page_size` | integer | Items per page |

**Response:**

```json
{
  "total": 234,
  "events": [
    {
      "event_id": "evt_0001",
      "timestamp": "2026-01-15T10:30:00Z",
      "user_id": "user_001",
      "username": "user_001@company.local",
      "action": "login",
      "resource": "/srv/git/repos",
      "location_city": "Moscow",
      "location_country": "RU",
      "ip_address": "10.0.15.42",
      "device_type": "laptop",
      "risk_score": 0.1,
      "status": "success"
    }
  ]
}
```

---

## Reports

### Generate PDF Report

```
POST /api/reports/generate
```

**Request Body:**

```json
{
  "alert_id": "550e8400-e29b-41d4-a716-446655440000",
  "include_user_events": true,
  "include_comparison": true
}
```

**Response:**

```json
{
  "report_id": "rep_abc123",
  "alert_id": "550e8400-e29b-41d4-a716-446655440000",
  "generated_at": "2026-01-20T14:30:00Z",
  "pdf_url": "/api/reports/download/rep_abc123"
}
```

---

### Download Report

```
GET /api/reports/download/{report_id}
```

Returns PDF file with `Content-Type: application/pdf`.

---

## Training

### Train Model

```
POST /api/train
```

**Request Body:**

```json
{
  "events_file": "data/events.csv",
  "label_column": null,
  "contamination": 0.1
}
```

**Response:**

```json
{
  "status": "trained",
  "best_model": "isolation_forest",
  "f1_score": 0.8734,
  "precision": 0.8231,
  "recall": 0.9305,
  "accuracy": 0.9012,
  "anomaly_count": 156,
  "total_count": 1560,
  "training_time_seconds": 4.23
}
```

---

### Model Evaluation

```
GET /api/models/evaluation
```

Returns comparison of all trained models with their metrics.

---

## Webhook

### Configure Webhook

```
POST /api/webhook/configure
```

**Request Body:**

```json
{
  "url": "https://your-webhook-endpoint.com/hook",
  "enabled": true
}
```

---

### Test Webhook

```
POST /api/webhook/test
```

**Response:**

```json
{
  "success": true,
  "message": "Webhook OK (status 200)"
}
```

---

## Health Check

### Health

```
GET /health
```

**Response:**

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "service": "ueba-api"
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error description"
}
```

Common HTTP status codes:
- `200` - Success
- `201` - Created
- `400` - Bad Request
- `404` - Not Found
- `422` - Validation Error
- `500` - Internal Server Error
- `503` - Service Unavailable
