# scripts/optimize_tiles.py
"""
Run this once after creating tables and importing data.

Usage:
    docker compose exec api python scripts/optimize_tiles.py
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

DSN = os.getenv("SYNC_DATABASE_URL")

STEPS = [
    # ── 1. Indexes ─────────────────────────────────────────────
    (
        "Composite index: location + timestamp",
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lh_location_timestamp
        ON location_history USING GIST (location)
        WHERE timestamp IS NOT NULL;
        """
    ),
    (
        "Composite index: person filter",
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_people_gender_age_city
        ON people (gender, age, city_id);
        """
    ),

    # ── 2. Materialized view ───────────────────────────────────
    (
        "Create materialized view",
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_location_history_tiles AS
        SELECT
            lh.id,
            lh.person_id,
            lh.timestamp,
            lh.location,
            p.gender,
            p.age,
            p.city_id,
            c.name AS city_name
        FROM location_history lh
        JOIN people p ON p.id = lh.person_id
        JOIN cities c ON c.id = p.city_id
        WITH DATA;
        """
    ),
    (
        "GIST index on materialized view",
        """
        CREATE INDEX IF NOT EXISTS idx_mv_lh_location_gist
        ON mv_location_history_tiles USING GIST (location);
        """
    ),
    (
        "Filter indexes on materialized view",
        """
        CREATE INDEX IF NOT EXISTS idx_mv_lh_gender    ON mv_location_history_tiles (gender);
        CREATE INDEX IF NOT EXISTS idx_mv_lh_age       ON mv_location_history_tiles (age);
        CREATE INDEX IF NOT EXISTS idx_mv_lh_city_id   ON mv_location_history_tiles (city_id);
        CREATE INDEX IF NOT EXISTS idx_mv_lh_timestamp ON mv_location_history_tiles (timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_mv_lh_gender_age ON mv_location_history_tiles (gender, age);
        """
    ),

    # ── 3. Tile function ───────────────────────────────────────
    (
        "Create optimized tile function",
        """
        CREATE OR REPLACE FUNCTION tile_location_history(
            z integer, x integer, y integer,
            query_params json DEFAULT '{}'::json
        )
        RETURNS bytea AS $$
        DECLARE
            mvt        bytea;
            tile_env   geometry := ST_TileEnvelope(z, x, y);
            p_gender   text        := query_params->>'gender';
            p_age_min  int         := (query_params->>'age_min')::int;
            p_age_max  int         := (query_params->>'age_max')::int;
            p_city_id  int         := (query_params->>'city_id')::int;
            p_ts_from  timestamptz := (query_params->>'timestamp_from')::timestamptz;
            p_ts_to    timestamptz := (query_params->>'timestamp_to')::timestamptz;
            p_bbox     text        := query_params->>'bbox';
            bbox_geom  geometry;
            simplify_tolerance float := CASE
                WHEN z <= 6  THEN 0.01
                WHEN z <= 8  THEN 0.005
                WHEN z <= 10 THEN 0.001
                ELSE 0.0
            END;
        BEGIN
            IF p_bbox IS NOT NULL THEN
                bbox_geom := ST_MakeEnvelope(
                    split_part(p_bbox,',',1)::float,
                    split_part(p_bbox,',',2)::float,
                    split_part(p_bbox,',',3)::float,
                    split_part(p_bbox,',',4)::float, 4326
                );
            END IF;

            SELECT ST_AsMVT(tile_data, 'location_history', 4096, 'geom')
            INTO mvt
            FROM (
                SELECT
                    ST_AsMVTGeom(
                        CASE WHEN simplify_tolerance > 0
                            THEN ST_Transform(ST_Simplify(location, simplify_tolerance), 3857)
                            ELSE ST_Transform(location, 3857)
                        END,
                        tile_env, 4096, 64, true
                    ) AS geom,
                    id, person_id,
                    to_char(timestamp, 'YYYY-MM-DD"T"HH24:MI:SSZ') AS timestamp,
                    gender, age, city_name
                FROM mv_location_history_tiles
                WHERE
                    location && ST_Transform(tile_env, 4326)
                    AND (p_gender  IS NULL OR gender    =  p_gender)
                    AND (p_age_min IS NULL OR age       >= p_age_min)
                    AND (p_age_max IS NULL OR age       <= p_age_max)
                    AND (p_city_id IS NULL OR city_id   =  p_city_id)
                    AND (p_ts_from IS NULL OR timestamp >= p_ts_from)
                    AND (p_ts_to   IS NULL OR timestamp <= p_ts_to)
                    AND (p_bbox    IS NULL OR location  && bbox_geom)
                LIMIT CASE
                    WHEN z <= 6  THEN 1000
                    WHEN z <= 8  THEN 5000
                    WHEN z <= 10 THEN 20000
                    ELSE 100000
                END
            ) AS tile_data
            WHERE geom IS NOT NULL;
            RETURN mvt;
        END;
        $$ LANGUAGE plpgsql STABLE PARALLEL SAFE;
        """
    ),

    # ── 4. Analyze ─────────────────────────────────────────────
    (
        "Analyze tables",
        """
        ANALYZE location_history;
        ANALYZE people;
        ANALYZE cities;
        ANALYZE mv_location_history_tiles;
        """
    ),
]


async def main():
    conn = await asyncpg.connect(DSN)

    for name, sql in STEPS:
        print(f"⏳ {name}...")
        try:
            # Run each statement separately
            for stmt in sql.strip().split(";"):
                stmt = stmt.strip()
                if stmt:
                    await conn.execute(stmt)
            print(f"✅ Done: {name}")
        except Exception as e:
            print(f"⚠️  {name}: {e}")

    await conn.close()

    print("\n" + "═" * 55)
    print("✅ All optimizations applied!")
    print("\nRestart Martin to pick up tile function changes:")
    print("  docker compose restart martin")
    print("\nRefresh materialized view when data changes:")
    print("  REFRESH MATERIALIZED VIEW CONCURRENTLY mv_location_history_tiles;")
    print("═" * 55)


if __name__ == "__main__":
    asyncio.run(main())