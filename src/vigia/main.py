from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
from typing import Annotated

from fastapi import FastAPI, Query
from fastapi.responses import RedirectResponse

from vigia.database import connect, initialize_database
from vigia.schemas import EventIn, Incident, Level, Metrics, ServiceMetric


def create_app(database_path: Path | None = None) -> FastAPI:
    db_path = database_path or Path(os.getenv("VIGIA_DB_PATH", "data/vigia.db"))

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        initialize_database(db_path)
        yield

    app = FastAPI(
        title="Vigia API",
        description="Ingestão e consolidação de erros de aplicações.",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url="/docs", status_code=307)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        with connect(db_path) as connection:
            connection.execute("SELECT 1")
        return {"status": "ok", "database": "connected"}

    @app.post("/api/v1/events", response_model=Incident, tags=["events"])
    def ingest_event(event: EventIn) -> Incident:
        normalized_message = re.sub(r"\s+", " ", event.message.casefold()).strip()
        fingerprint_source = "\0".join((event.service, event.level, normalized_message))
        fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")

        with connect(db_path) as connection:
            row = connection.execute(
                """
                INSERT INTO incidents (
                    service, level, message, fingerprint, first_seen, last_seen
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(fingerprint) DO UPDATE SET
                    last_seen = excluded.last_seen,
                    occurrences = incidents.occurrences + 1
                RETURNING id, service, level, message, fingerprint,
                          first_seen, last_seen, occurrences
                """,
                (event.service, event.level, event.message, fingerprint, now, now),
            ).fetchone()

        return Incident(**dict(row))

    @app.get("/api/v1/incidents", response_model=list[Incident], tags=["incidents"])
    def list_incidents(
        level: Level | None = None,
        service: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> list[Incident]:
        conditions: list[str] = []
        parameters: list[object] = []
        if level is not None:
            conditions.append("level = ?")
            parameters.append(level)
        if service is not None:
            conditions.append("service = ?")
            parameters.append(service)
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with connect(db_path) as connection:
            rows = connection.execute(
                f"SELECT * FROM incidents {where_clause} "
                "ORDER BY last_seen DESC LIMIT ? OFFSET ?",
                (*parameters, limit, offset),
            ).fetchall()
        return [Incident(**dict(row)) for row in rows]

    @app.get("/api/v1/metrics", response_model=Metrics, tags=["metrics"])
    def get_metrics() -> Metrics:
        with connect(db_path) as connection:
            totals = connection.execute(
                "SELECT COUNT(*) AS incidents, COALESCE(SUM(occurrences), 0) AS occurrences "
                "FROM incidents"
            ).fetchone()
            levels = connection.execute(
                "SELECT level, COUNT(*) AS incidents FROM incidents GROUP BY level"
            ).fetchall()
            services = connection.execute(
                """
                SELECT service, COUNT(*) AS incidents, SUM(occurrences) AS occurrences
                FROM incidents
                GROUP BY service
                ORDER BY occurrences DESC, service ASC
                LIMIT 5
                """
            ).fetchall()

        return Metrics(
            total_incidents=totals["incidents"],
            total_occurrences=totals["occurrences"],
            by_level={row["level"]: row["incidents"] for row in levels},
            top_services=[ServiceMetric(**dict(row)) for row in services],
        )

    return app


app = create_app()