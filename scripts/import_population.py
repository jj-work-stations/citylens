#!/usr/bin/env python3
# scripts/import_population.py
"""
Usage:
    # import esfahan using rscp_mtn as the value column
    python scripts/import_population.py \
        --file data/esfahan.geojson \
        --province esfahan \
        --value-column rscp_mtn

    # import mashhad using rscp_mci
    python scripts/import_population.py \
        --file data/mashhad.geojson \
        --province mashhad \
        --value-column rscp_mci

    # dry run
    python scripts/import_population.py \
        --file data/esfahan.geojson \
        --province esfahan \
        --value-column rscp_mtn \
        --dry-run
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

import asyncpg
from app.core.config import settings
from app.models.population import PROVINCE_NAMES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger(__name__)

VALUE_COLUMNS = ["rscp_mtn", "rscp_mci"]


# ── Parsers ───────────────────────────────────────────────────

def parse_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_datetime(v) -> Optional[datetime]:
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v))
    except (ValueError, TypeError):
        return None


def iter_features(geojson: dict) -> Iterator[dict]:
    if geojson.get("type") == "FeatureCollection":
        yield from geojson.get("features", [])
    elif geojson.get("type") == "Feature":
        yield geojson
    else:
        raise ValueError(f"Unsupported GeoJSON type: {geojson.get('type')}")


def feature_to_row(feature: dict, value_column: str) -> Optional[dict]:
    """
    Convert GeoJSON feature to a DB row dict.
    value_column: which field to read — 'rscp_mtn' or 'rscp_mci'
    """
    try:
        props    = feature.get("properties", {})
        geometry = feature.get("geometry", {})

        if geometry.get("type") != "Point":
            return None

        coords = geometry.get("coordinates", [])
        if len(coords) < 2:
            return None

        lon = float(coords[0])
        lat = float(coords[1])

        # pick the selected value column
        value = parse_float(props.get('rscp_mtn')) or parse_float(props.get('rscp_mci'))

        return {
            "value": value,
            "lat":   lat,
            "lon":   lon,
            "geom":  f"SRID=4326;POINT({lon} {lat})",
            "time":  parse_datetime(props.get("time")),
        }

    except Exception as exc:
        logger.debug("Skipped malformed feature: %s", exc)
        return None


# ── DB ────────────────────────────────────────────────────────

async def ensure_postgis(conn: asyncpg.Connection) -> None:
    await conn.execute("CREATE EXTENSION IF NOT EXISTS postgis;")


async def insert_batch(
    conn: asyncpg.Connection,
    table: str,
    rows: list[dict],
) -> tuple[int, int]:
    sql = f"""
        INSERT INTO "{table}" (value, lat, lon, geom, time)
        VALUES ($1, $2, $3, ST_GeomFromEWKT($4), $5)
        ON CONFLICT DO NOTHING
    """
    records = [
        (r["value"], r["lat"], r["lon"], r["geom"], r["time"])
        for r in rows
    ]
    try:
        await conn.executemany(sql, records)
        return len(records), 0
    except Exception as exc:
        logger.error("Batch failed, falling back to row-by-row: %s", exc)
        ok = err = 0
        for rec in records:
            try:
                await conn.execute(sql, *rec)
                ok += 1
            except Exception:
                err += 1
        return ok, err


async def create_tile_function(conn: asyncpg.Connection, table: str) -> None:
    """
    Martin tile function for a population table.
    Supports optional bbox query param.
    """
    func_name = f"tile_{table}"
    sql = f"""
    CREATE OR REPLACE FUNCTION "{func_name}"(
        z            integer,
        x            integer,
        y            integer,
        query_params json DEFAULT '{{}}'::json
    )
    RETURNS bytea AS $$
    DECLARE
        mvt       bytea;
        bbox_text text    := query_params->>'bbox';
        tile_env  geometry := ST_TileEnvelope(z, x, y);
    BEGIN
        SELECT ST_AsMVT(tile_data, '{table}', 4096, 'geom')
        INTO mvt
        FROM (
            SELECT
                ST_AsMVTGeom(
                    ST_Transform(geom, 3857),
                    tile_env,
                    4096, 64, true
                )          AS geom,
                id,
                value,
                lat,
                lon,
                time::text AS time
            FROM "{table}"
            WHERE
                geom && ST_Transform(tile_env, 4326)
                AND (
                    bbox_text IS NULL
                    OR geom && ST_MakeEnvelope(
                        split_part(bbox_text,',',1)::float,
                        split_part(bbox_text,',',2)::float,
                        split_part(bbox_text,',',3)::float,
                        split_part(bbox_text,',',4)::float,
                        4326
                    )
                )
        ) AS tile_data
        WHERE geom IS NOT NULL;

        RETURN mvt;
    END;
    $$ LANGUAGE plpgsql STABLE PARALLEL SAFE;
    """
    await conn.execute(sql)
    logger.info("✅ Tile function created: %s", func_name)


# ── Main ──────────────────────────────────────────────────────

async def run_import(
    file:         Path,
    province:     str,
    value_column: str,
    batch_size:   int  = 2000,
    dry_run:      bool = False,
    truncate:     bool = False,
) -> dict:
    table = f"{province}_population"

    logger.info("📂 File         : %s", file)
    logger.info("🏙️  Province     : %s → table: %s", province, table)
    logger.info("📡 Value column : %s", value_column)

    with open(file, encoding="utf-8") as f:
        geojson = json.load(f)

    features = list(iter_features(geojson))
    logger.info("📊 Features     : %d", len(features))

    inserted = skipped = errors = 0

    if dry_run:
        logger.info("🔍 DRY RUN — parsing only, no DB writes")
        for feat in features:
            row = feature_to_row(feat, value_column)
            if row:
                inserted += 1
            else:
                skipped += 1
        return dict(
            province=province, value_column=value_column,
            total=len(features), inserted=inserted,
            skipped=skipped, errors=errors, duration_s=0,
        )

    conn = await asyncpg.connect(settings.SYNC_DATABASE_URL)
    t0 = time.monotonic()

    try:
        await ensure_postgis(conn)

        if truncate:
            logger.warning("⚠️  Truncating %s", table)
            await conn.execute(f'TRUNCATE TABLE "{table}" RESTART IDENTITY;')

        batch: list[dict] = []

        for feat in features:
            row = feature_to_row(feat, value_column)
            if row is None:
                skipped += 1
                continue
            batch.append(row)

            if len(batch) >= batch_size:
                ok, err = await insert_batch(conn, table, batch)
                inserted += ok
                errors   += err
                batch     = []
                done = inserted + skipped + errors
                logger.info(
                    "  progress: %d/%d (%.1f%%)",
                    done, len(features), done / len(features) * 100,
                )

        if batch:
            ok, err = await insert_batch(conn, table, batch)
            inserted += ok
            errors   += err

        await create_tile_function(conn, table)

    finally:
        await conn.close()

    return dict(
        province=province,
        value_column=value_column,
        total=len(features),
        inserted=inserted,
        skipped=skipped,
        errors=errors,
        duration_s=round(time.monotonic() - t0, 2),
    )


def main():
    p = argparse.ArgumentParser(
        description="Import GeoJSON into province population table",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--file",         required=True)
    p.add_argument("--province",     required=True, choices=PROVINCE_NAMES)
    p.add_argument(
        "--value-column",
        required=True,
        choices=VALUE_COLUMNS,
        help="Which signal column to use as 'value': rscp_mtn or rscp_mci",
    )
    p.add_argument("--batch-size", type=int, default=2000)
    p.add_argument("--dry-run",    action="store_true")
    p.add_argument("--truncate",   action="store_true")

    args = p.parse_args()

    result = asyncio.run(run_import(
        file         = Path(args.file),
        province     = args.province,
        value_column = args.value_column,
        batch_size   = args.batch_size,
        dry_run      = args.dry_run,
        truncate     = args.truncate,
    ))

    print("\n" + "═" * 50)
    print(f"  Province     : {result['province']}")
    print(f"  Value column : {result['value_column']}")
    print(f"  Total        : {result['total']:,}")
    print(f"  Inserted     : {result['inserted']:,}")
    print(f"  Skipped      : {result['skipped']:,}")
    print(f"  Errors       : {result['errors']:,}")
    if not args.dry_run:
        rate = result["inserted"] / result["duration_s"] if result["duration_s"] else 0
        print(f"  Duration     : {result['duration_s']}s ({rate:,.0f} rows/s)")
    print("═" * 50)

    sys.exit(1 if result["errors"] > 0 else 0)


if __name__ == "__main__":
    main()