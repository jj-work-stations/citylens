#!/usr/bin/env python3
# scripts/import_population.py

import argparse
import asyncio
import csv
import io
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

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

INSERT_HEAD_RE = re.compile(
    r'INSERT\s+INTO\s+(?P<table>(?:\"[^\"]+\"\.)?\"[^\"]+\"|[\w\.]+)\s*\((?P<columns>.*?)\)\s*VALUES\s*',
    re.IGNORECASE | re.DOTALL,
)

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
    except (TypeError, ValueError):
        return None

def parse_sql_value(v: str):
    v = v.strip()
    if v.upper() == "NULL":
        return None
    if v.startswith("'") and v.endswith("'"):
        return v[1:-1].replace("''", "'")
    if v.startswith('"') and v.endswith('"'):
        return v[1:-1].replace('""', '"')
    try:
        if "." in v or "e" in v.lower():
            return float(v)
        return int(v)
    except ValueError:
        return v

def split_sql_tuples(values_blob: str):
    tuples = []
    depth = 0
    start = None
    in_quote = False
    i = 0
    while i < len(values_blob):
        ch = values_blob[i]
        if ch == "'" and (i == 0 or values_blob[i - 1] != "\\"):
            if in_quote and i + 1 < len(values_blob) and values_blob[i + 1] == "'":
                i += 1
            else:
                in_quote = not in_quote
        elif not in_quote:
            if ch == "(":
                if depth == 0:
                    start = i + 1
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and start is not None:
                    tuples.append(values_blob[start:i])
                    start = None
        i += 1
    return tuples

def parse_insert_block(block: str):
    m = INSERT_HEAD_RE.search(block)
    if not m:
        return []

    columns = [c.strip().strip('"') for c in m.group("columns").split(",")]
    after_values = block[m.end():].strip().rstrip(";")

    rows = []
    for tup in split_sql_tuples(after_values):
        reader = csv.reader(
            io.StringIO(tup),
            delimiter=",",
            quotechar="'",
            escapechar="\\",
            skipinitialspace=True,
        )
        values = next(reader)
        parsed = [parse_sql_value(v) for v in values]
        rows.append(dict(zip(columns, parsed)))

    return rows

def ewkt_point_from_lonlat(lon: float, lat: float) -> str:
    return f"SRID=4326;POINT({lon} {lat})"

async def ensure_postgis(conn: asyncpg.Connection) -> None:
    await conn.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

async def insert_batch(conn: asyncpg.Connection, table: str, rows: list[dict]) -> tuple[int, int]:
    sql = f'''
        INSERT INTO "{table}" (value, lat, lon, geom, time)
        VALUES ($1, $2, $3, ST_GeomFromEWKT($4), $5)
        ON CONFLICT DO NOTHING
    '''
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

async def run_import(
    file: Path,
    province: str,
    batch_size: int = 2000,
    dry_run: bool = False,
    truncate: bool = False,
) -> dict:
    table = f"{province}_population"

    logger.info("File         : %s", file)
    logger.info("Province     : %s -> table: %s", province, table)

    sql_text = file.read_text(encoding="utf-8")

    blocks = []
    current = []
    in_insert = False

    for line in sql_text.splitlines():
        if line.strip().upper().startswith("INSERT INTO"):
            in_insert = True
            current = [line]
            if line.strip().endswith(";"):
                blocks.append("\n".join(current))
                in_insert = False
            continue

        if in_insert:
            current.append(line)
            if line.strip().endswith(";"):
                blocks.append("\n".join(current))
                in_insert = False

    rows = []
    for block in blocks:
        parsed_rows = parse_insert_block(block)
        for parsed in parsed_rows:
            lon = parsed.get("long")
            lat = parsed.get("lat")
            if lon is None or lat is None:
                continue

            value = parse_float(parsed.get("rscp_mtn"))
            if value is None:
                value = parse_float(parsed.get("rscp_mci"))

            rows.append({
                "value": value,
                "lat": float(lat),
                "lon": float(lon),
                "geom": ewkt_point_from_lonlat(float(lon), float(lat)),
                "time": parse_datetime(parsed.get("time")),
            })

    logger.info("Parsed rows  : %d", len(rows))

    if dry_run:
        inserted = sum(1 for r in rows if r["value"] is not None)
        skipped = len(rows) - inserted
        return {
            "province": province,
            "total": len(rows),
            "inserted": inserted,
            "skipped": skipped,
            "errors": 0,
            "duration_s": 0,
        }

    conn = await asyncpg.connect(settings.SYNC_DATABASE_URL)
    t0 = time.monotonic()
    inserted = skipped = errors = 0

    try:
        await ensure_postgis(conn)

        if truncate:
            logger.warning("Truncating %s", table)
            await conn.execute(f'TRUNCATE TABLE "{table}" RESTART IDENTITY;')

        batch = []
        for row in rows:
            if row["value"] is None:
                skipped += 1
                continue

            batch.append(row)
            if len(batch) >= batch_size:
                ok, err = await insert_batch(conn, table, batch)
                inserted += ok
                errors += err
                batch = []

        if batch:
            ok, err = await insert_batch(conn, table, batch)
            inserted += ok
            errors += err

    finally:
        await conn.close()

    return {
        "province": province,
        "total": len(rows),
        "inserted": inserted,
        "skipped": skipped,
        "errors": errors,
        "duration_s": round(time.monotonic() - t0, 2),
    }

def main():
    p = argparse.ArgumentParser(
        description="Import SQL dump into population table",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--file", required=True, help="Path to .sql file")
    p.add_argument("--province", required=True, choices=PROVINCE_NAMES)
    p.add_argument("--batch-size", type=int, default=2000)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--truncate", action="store_true")
    args = p.parse_args()

    result = asyncio.run(run_import(
        file=Path(args.file),
        province=args.province,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        truncate=args.truncate,
    ))

    print("\n" + "═" * 50)
    print(f"  Province     : {result['province']}")
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