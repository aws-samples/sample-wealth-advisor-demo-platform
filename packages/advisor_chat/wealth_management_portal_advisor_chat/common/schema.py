"""Dynamic Redshift schema discovery — queries information_schema, caches in-process."""

import logging

from .redshift import execute_query

logger = logging.getLogger(__name__)

_cached_schema: str | None = None


def get_schema(tables: list[str] | None = None) -> str:
    """Return a text description of public tables/columns.

    Args:
        tables: Optional whitelist of table names. If provided, only those tables are included.
    """
    global _cached_schema
    if _cached_schema is None:
        try:
            rows = execute_query(
                "SELECT table_name, column_name, data_type "
                "FROM information_schema.columns "
                "WHERE table_schema = 'public' "
                "ORDER BY table_name, ordinal_position"
            )
            current = ""
            lines: list[str] = []
            for r in rows:
                t = r["table_name"]
                if t != current:
                    lines.append(f"\n{t}:")
                    current = t
                lines.append(f"  {r['column_name']} ({r['data_type']})")
            _cached_schema = "\n".join(lines).strip()
            logger.info("Schema discovered: %d tables", len({r["table_name"] for r in rows}))
        except Exception:
            logger.exception("Failed to discover schema")
            _cached_schema = ""

    if not tables or not _cached_schema:
        return _cached_schema

    filtered: list[str] = []
    include = False
    for line in _cached_schema.split("\n"):
        if line and not line.startswith("  "):
            include = line.rstrip(":") in tables
        if include:
            filtered.append(line)
    return "\n".join(filtered).strip()
