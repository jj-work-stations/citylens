# scripts/create_tracking_tile_function.py
"""
Creates a PostgreSQL function that Martin uses to serve 
location_history tiles with dynamic filtering.

Run:
    python scripts/create_tracking_tile_function.py
"""
import asyncio
import asyncpg
from dotenv import load_dotenv
import os

load_dotenv()

SQL = """
CREATE OR REPLACE FUNCTION tile_location_history(
    z            integer,
    x            integer,
    y            integer,
    query_params json DEFAULT '{}'::json
)
RETURNS bytea AS $$
DECLARE
    mvt            bytea;
    tile_env       geometry := ST_TileEnvelope(z, x, y);

    -- ── Extract filter params from query_params ─────────────
    p_gender       text    := query_params->>'gender';
    p_age_min      int     := (query_params->>'age_min')::int;
    p_age_max      int     := (query_params->>'age_max')::int;
    p_city_id      int     := (query_params->>'city_id')::int;
    p_ts_from      timestamptz := (query_params->>'timestamp_from')::timestamptz;
    p_ts_to        timestamptz := (query_params->>'timestamp_to')::timestamptz;
    p_bbox         text    := query_params->>'bbox';
    bbox_geom      geometry;
BEGIN
    -- Parse bbox if provided
    IF p_bbox IS NOT NULL THEN
        bbox_geom := ST_MakeEnvelope(
            split_part(p_bbox, ',', 1)::float,
            split_part(p_bbox, ',', 2)::float,
            split_part(p_bbox, ',', 3)::float,
            split_part(p_bbox, ',', 4)::float,
            4326
        );
    END IF;

    SELECT ST_AsMVT(tile_data, 'location_history', 4096, 'geom')
    INTO mvt
    FROM (
        SELECT
            ST_AsMVTGeom(
                ST_Transform(lh.location, 3857),
                tile_env,
                4096, 64, true
            )                               AS geom,
            lh.id,
            lh.person_id,
            to_char(lh.timestamp, 'YYYY-MM-DD"T"HH24:MI:SSZ') AS timestamp,
            p.gender,
            p.age,
            c.name                          AS city_name
        FROM location_history lh
        JOIN people p ON p.id = lh.person_id
        JOIN cities c ON c.id = p.city_id
        WHERE
            -- ── Tile envelope filter (always applied) ────────
            lh.location && ST_Transform(tile_env, 4326)

            -- ── Gender filter ─────────────────────────────────
            AND (p_gender  IS NULL OR p.gender = p_gender)

            -- ── Age filter ────────────────────────────────────
            AND (p_age_min IS NULL OR p.age >= p_age_min)
            AND (p_age_max IS NULL OR p.age <= p_age_max)

            -- ── City filter ───────────────────────────────────
            AND (p_city_id IS NULL OR p.city_id = p_city_id)

            -- ── Timestamp filter ──────────────────────────────
            AND (p_ts_from IS NULL OR lh.timestamp >= p_ts_from)
            AND (p_ts_to   IS NULL OR lh.timestamp <= p_ts_to)

            -- ── BBox filter ───────────────────────────────────
            AND (p_bbox IS NULL OR lh.location && bbox_geom)

    ) AS tile_data
    WHERE geom IS NOT NULL;

    RETURN mvt;
END;
$$ LANGUAGE plpgsql STABLE PARALLEL SAFE;
"""


async def main():
    dsn = os.getenv("SYNC_DATABASE_URL", "postgresql://postgres:postgres@localhost:5430/mapdb")
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(SQL)
        print("✅ tile_location_history function created")
        print("\nTest tile URL:")
        print("  http://localhost:3001/tile_location_history/10/0/0")
        print("\nWith filters:")
        print("  http://localhost:3001/tile_location_history/10/0/0?gender=M&age_min=25&age_max=40")
        print("  http://localhost:3001/tile_location_history/10/0/0?city_id=1&timestamp_from=2024-06-10&timestamp_to=2024-06-12")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())