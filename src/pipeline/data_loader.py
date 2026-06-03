"""Загрузка и нормализация данных из CSV и Elasticsearch."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, Optional

import pandas as pd
from loguru import logger


class DataLoader:
    """Загрузчик данных из CSV-файлов или Elasticsearch."""

    def __init__(self, es_client: Optional[Any] = None) -> None:
        self._es = es_client
        self._events_df: Optional[pd.DataFrame] = None
        self._users_df: Optional[pd.DataFrame] = None

    def load_from_csv(
        self,
        events_path: str | Path,
        users_path: str | Path,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Загружает события и пользователей из CSV-файлов."""
        events_path = Path(events_path)
        users_path = Path(users_path)

        if not events_path.exists():
            raise FileNotFoundError(f"Events file not found: {events_path}")
        if not users_path.exists():
            raise FileNotFoundError(f"Users file not found: {users_path}")

        logger.info(f"Loading events from {events_path}")
        self._events_df = pd.read_csv(events_path, parse_dates=["timestamp"])
        logger.info(f"Loaded {len(self._events_df)} events")

        logger.info(f"Loading users from {users_path}")
        self._users_df = pd.read_csv(users_path)
        logger.info(f"Loaded {len(self._users_df)} users")

        return self._events_df, self._users_df

    def load_from_elasticsearch(
        self,
        index: str = "ueba-events",
        size: int = 10000,
        query: Optional[dict[str, Any]] = None,
    ) -> pd.DataFrame:
        """Загружает события из Elasticsearch."""
        if self._es is None:
            raise RuntimeError("Elasticsearch client not initialized")

        logger.info(f"Loading events from Elasticsearch index '{index}'")
        body = query or {"query": {"match_all": {}}, "size": size}

        try:
            response = self._es.search(index=index, body=body)
            hits = response["hits"]["hits"]
            records = [hit["_source"] for hit in hits]

            if not records:
                logger.warning("No events found in Elasticsearch")
                self._events_df = pd.DataFrame()
                return self._events_df

            self._events_df = pd.DataFrame(records)
            if "timestamp" in self._events_df.columns:
                self._events_df["timestamp"] = pd.to_datetime(self._events_df["timestamp"])

            logger.info(f"Loaded {len(self._events_df)} events from ES")
            return self._events_df

        except Exception as e:
            logger.error(f"Failed to load from Elasticsearch: {e}")
            raise

    def index_events_to_es(
        self,
        df: pd.DataFrame,
        index: str = "ueba-events",
        chunk_size: int = 1000,
    ) -> int:
        """Индексирует события в Elasticsearch батчами."""
        if self._es is None:
            raise RuntimeError("Elasticsearch client not initialized")

        total = 0
        records = df.to_dict("records")

        for chunk in _chunked(records, chunk_size):
            actions = []
            for record in chunk:
                record["timestamp"] = record["timestamp"].isoformat()
                actions.append({"index": {"_index": index, "_id": record.get("event_id")}})
                actions.append(record)

            if actions:
                self._es.bulk(operations=actions, refresh=True)
                total += len(chunk)
                logger.debug(f"Indexed {total} events")

        logger.info(f"Total events indexed: {total}")
        return total

    def index_users_to_es(
        self,
        df: pd.DataFrame,
        index: str = "ueba-users",
    ) -> int:
        """Индексирует пользователей в Elasticsearch."""
        if self._es is None:
            raise RuntimeError("Elasticsearch client not initialized")

        records = df.to_dict("records")
        actions = []

        for record in records:
            actions.append({"index": {"_index": index, "_id": record.get("user_id")}})
            actions.append(record)

        if actions:
            self._es.bulk(operations=actions, refresh=True)

        logger.info(f"Indexed {len(df)} users")
        return len(df)

    def filter_by_timerange(
        self,
        df: pd.DataFrame,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Фильтрует события по временному диапазону."""
        result = df.copy()

        if start is not None:
            result = result[result["timestamp"] >= pd.Timestamp(start)]
        if end is not None:
            result = result[result["timestamp"] <= pd.Timestamp(end)]

        return result

    def filter_by_users(
        self,
        df: pd.DataFrame,
        user_ids: list[str],
    ) -> pd.DataFrame:
        """Фильтрует события по списку user_id."""
        return df[df["user_id"].isin(user_ids)]

    def get_user_profiles(self, df: pd.DataFrame) -> pd.DataFrame:
        """Агрегирует профили пользователей из событий."""
        return (
            df.groupby("user_id")
            .agg(
                total_events=("event_id", "count"),
                unique_actions=("action", "nunique"),
                unique_locations=("location_city", "nunique"),
                avg_hour=("hour", "mean"),
                unique_resources=("resource", "nunique"),
                avg_bytes_sent=("bytes_sent", "mean"),
                avg_bytes_received=("bytes_received", "mean"),
                failed_ratio=("status", lambda x: (x == "failed").mean()),
                anomaly_score_max=("risk_score", "max"),
                department=("department", "first"),
                role=("role", "first"),
                username=("username", "first"),
                full_name=("full_name", "first"),
            )
            .reset_index()
        )

    @property
    def events(self) -> Optional[pd.DataFrame]:
        return self._events_df

    @property
    def users(self) -> Optional[pd.DataFrame]:
        return self._users_df


def _chunked(iterable: list[Any], size: int) -> Generator[list[Any], None, None]:
    """Разбивает список на чанки заданного размера."""
    for i in range(0, len(iterable), size):
        yield iterable[i:i + size]
