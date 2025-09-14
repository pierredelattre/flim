#!/usr/bin/env python3
"""
scrap_showtimes.py
Scrape les séances (showtimes) pour chaque cinéma et enregistre en BDD
"""

import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
import psycopg2
from allocine_wrapper import get_movies_with_showtimes
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- config logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("scrap_showtimes")

# Reduce third‑party verbosity
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL non défini dans .env")


# --- DB helpers
def get_conn():
    return psycopg2.connect(DATABASE_URL)


def upsert_showtime(cur, cinema_id, movie_id, start_date, start_time, diffusion_version, fmt, reservation_url):
    """
    Upsert a single showtime. Requires a UNIQUE index on
    (cinema_id, movie_id, start_date, start_time, diffusion_version).
    Returns True if a row was inserted or updated.
    """
    query = """
    INSERT INTO showtimes
      (cinema_id, movie_id, start_date, start_time, diffusion_version, format, reservation_url, last_update)
    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
    ON CONFLICT (cinema_id, movie_id, start_date, start_time, diffusion_version)
    DO UPDATE SET
      diffusion_version = EXCLUDED.diffusion_version,
      format = EXCLUDED.format,
      reservation_url = EXCLUDED.reservation_url,
      last_update = NOW()
    RETURNING id;
    """
    cur.execute(query, (
        cinema_id,
        movie_id,
        start_date,
        start_time,
        diffusion_version,
        fmt,
        reservation_url
    ))
    # If a row was affected, RETURNING yields one row; otherwise None.
    return cur.fetchone() is not None


MAX_WORKERS = 5

def scrape_cinema(conn, cinema, target_date, idx, total):
    cinema_db_id, cinema_allocine, cinema_name = cinema
    logger.info("👉 [%d/%d] Scraping séances pour %s (%s)", idx, total, cinema_name, cinema_allocine)
    upserts = 0
    try:
        movies = get_movies_with_showtimes(cinema_allocine, target_date)
    except Exception as e:
        logger.error("❌ Erreur scrap %s (%s) %s : %s", cinema_name, cinema_allocine, target_date, e)
        try:
            conn.close()
        except Exception:
            pass
        return

    try:
        cur = conn.cursor()
        for movie in movies:
            movie_allocine = movie.get("id_allocine") or movie.get("internalId")
            title = movie.get("title")

            if not movie_allocine:
                logger.warning("⚠️ Film %s sans id_allocine, skip", title)
                continue

            # récupérer l'id interne du film en base
            cur.execute("SELECT id FROM films WHERE id_allocine = %s", (str(movie_allocine),))
            res = cur.fetchone()
            if not res:
                logger.warning("⚠️ Film %s (%s) pas trouvé en BDD, skip", title, movie_allocine)
                continue
            movie_db_id = res[0]

            for show in movie.get("showtimes", []):
                try:
                    starts_at = show.get("startsAt")
                    if not starts_at:
                        continue
                    # parse startsAt -> date + heure
                    dt = datetime.fromisoformat(starts_at)
                    start_date = dt.date()
                    start_time = dt.time()

                    diffusion_version = show.get("diffusionVersion")  # VF, VO, etc.
                    fmt = show.get("format")  # 2D, 3D, IMAX...
                    reservation_url = show.get("reservation_url")

                    if upsert_showtime(
                        cur,
                        cinema_db_id,
                        movie_db_id,
                        start_date,
                        start_time,
                        diffusion_version,
                        fmt,
                        reservation_url
                    ):
                        upserts += 1
                except Exception as e:
                    logger.error("❌ Erreur séance %s: %s", title, e)

        conn.commit()
        logger.info("✅ [%s] %s - %d séances upsertées", target_date, cinema_name, upserts)
    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


def main():
    conn = get_conn()

    # récupérer tous les cinémas
    cur = conn.cursor()
    cur.execute("SELECT id, id_allocine, name FROM cinemas")
    cinemas = cur.fetchall()
    cur.close()

    for offset in range(0, 7):
        target_date = (datetime.today() + timedelta(days=offset)).strftime("%Y-%m-%d")
        logger.info("🗓️ Scraping séances pour la date %s", target_date)

        total = len(cinemas)
        # Use ThreadPoolExecutor to scrape cinemas concurrently
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = []
            for idx, cinema in enumerate(cinemas, start=1):
                # Each thread gets its own connection
                thread_conn = get_conn()
                futures.append(executor.submit(scrape_cinema, thread_conn, cinema, target_date, idx, total))
            for f in as_completed(futures):
                try:
                    f.result()
                except Exception as e:
                    logger.error("Thread error: %s", e)

    conn.close()


if __name__ == "__main__":
    main()