# Generic repository executing parameterized SQL via a PEP 249 connection factory
from collections.abc import Callable

from pydantic import BaseModel


class BaseRepository[T: BaseModel]:
    """Generic repository with basic query helpers."""

    def __init__(self, conn_factory: Callable, model: type[T], table_name: str, valid_columns: set[str]):
        self._conn_factory = conn_factory
        self._model = model
        self._table_name = table_name
        self._valid_columns = valid_columns

    def get(self, **filters) -> list[T]:
        """Select rows matching all filters."""
        for col in filters:
            if col not in self._valid_columns:
                raise ValueError(f"Unknown column: {col}")
        where = " AND ".join(f"{col} = %s" for col in filters)
        sql = f"SELECT * FROM {self._table_name}"
        if where:
            sql += f" WHERE {where}"
        with self._conn_factory() as conn, conn.cursor() as cur:
            cur.execute(sql, list(filters.values()))
            cols = [d[0] for d in cur.description]
            return [self._model.model_validate(dict(zip(cols, row, strict=True))) for row in cur.fetchall()]

    def get_one(self, **filters) -> T | None:
        """Select a single row matching all filters."""
        results = self.get(**filters)
        return results[0] if results else None
