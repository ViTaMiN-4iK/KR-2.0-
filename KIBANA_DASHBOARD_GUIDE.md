# Kibana UEBA Dashboard — Руководство по созданию

## Шаг 1: Index Patterns (уже созданы)
**Stack Management → Index Patterns** — убедитесь что три паттерна видны:
- `ueba-events*`
- `ueba-alerts*`
- `ueba-users*`

---

## Шаг 2: Создание 6 визуализаций

Перейдите в **Visualize → Create visualization → Aggregation-based**

### 1. Top-5 Users by Alert Count (Horizontal Bar)
- Index: **ueba-alerts\***
- Y-axis: Count (default)
- X-axis: Split series → Aggregation: **Terms**, Field: **username.keyword**, Size: **5**, Order by: **Count**, Order: **Descending**
- Сохранить: `vis-top-users-alerts`

### 2. Alerts by Severity (Pie)
- Index: **ueba-alerts\***
- Slice: Aggregation: **Terms**, Field: **severity.keyword**, Size: **10**
- Сохранить: `vis-alerts-severity`

### 3. Events by Hour of Day (Area)
- Index: **ueba-events\***
- X-axis: Aggregation: **Histogram**, Field: **hour**, Interval: **1**
- Сохранить: `vis-events-by-hour`

### 4. Alerts by User (Bar)
- Index: **ueba-alerts\***
- X-axis: Aggregation: **Terms**, Field: **user_id**, Size: **20**, Order by: **Count**, Order: **Descending**
- Сохранить: `vis-alerts-by-user`

### 5. Alerts by Risk Level (Donut)
- Index: **ueba-alerts\***
- Slice: Aggregation: **Terms**, Field: **risk_level.keyword**, Size: **6**
- Сохранить: `vis-risk-level`

### 6. Average Risk Score Over Time (Line)
- Index: **ueba-events\***
- Y-axis: Aggregation: **Average**, Field: **risk_score**
- X-axis: Aggregation: **Date Histogram**, Field: **timestamp**, Interval: **Auto**
- Сохранить: `vis-risk-over-time`

---

## Шаг 3: Создание дашборда

1. **Dashboard → Create dashboard**
2. Название: `UEBA Security Overview`
3. Добавить панели — выбрать по очереди все 6 сохранённых визуализаций
4. Расположить панели в сетке (Kibana автоматически предложит места)
5. **Save**

---

## Альтернатива: Экспорт готового дашборда

После создания вручную можно экспортировать:
**Stack Management → Saved Objects → Export**

Выгруженный `.ndjson` файл можно будет в будущем импортировать на другой системе.
