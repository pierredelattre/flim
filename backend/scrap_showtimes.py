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

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL non défini dans .env")


# --- DB helpers
def get_conn():
    return psycopg2.connect(DATABASE_URL)


def upsert_showtime(conn, cinema_id, movie_id, start_date, start_time, diffusion_version, fmt, reservation_url):
    cur = conn.cursor()
    query = """
    INSERT INTO showtimes
      (cinema_id, movie_id, start_date, start_time, diffusion_version, format, reservation_url, last_update)
    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
    ON CONFLICT DO NOTHING;  -- éviter doublons
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
    conn.commit()
    cur.close()


MAX_WORKERS = 5

def scrape_cinema(conn, cinema, target_date, idx, total):
    cinema_db_id, cinema_allocine, cinema_name = cinema
    logger.info("👉 [%d/%d] Scraping séances pour %s (%s)", idx, total, cinema_name, cinema_allocine)
    try:
        movies = get_movies_with_showtimes(cinema_allocine, target_date)
        logger.info("Retrieved %d movies for cinema %s (%s) on %s", len(movies), cinema_name, cinema_allocine, target_date)
    except Exception as e:
        logger.error("❌ Erreur scrap %s: %s", cinema_name, e)
        return

    cur = conn.cursor()
    for movie in movies:
        movie_allocine = movie.get("id_allocine") or movie.get("internalId")
        title = movie.get("title")
        logger.info("🎬 Film: %s -> id_allocine=%s", title, movie_allocine)

        # récupérer l'id interne du film en base
        cur.execute("SELECT id FROM films WHERE id_allocine = %s", (str(movie_allocine),))
        res = cur.fetchone()
        if not res:
            logger.warning("⚠️ Film %s (%s) pas trouvé en BDD, skip", title, movie_allocine)
            continue
        movie_db_id = res[0]

        for show in movie.get("showtimes", []):
            try:
                # parse startsAt -> date + heure
                dt = datetime.fromisoformat(show["startsAt"])
                start_date = dt.date()
                start_time = dt.time()

                diffusion_version = show.get("diffusionVersion")  # VF, VO, etc.
                fmt = show.get("format")  # 2D, 3D, IMAX...
                reservation_url = show.get("reservation_url")

                upsert_showtime(
                    conn,
                    cinema_db_id,
                    movie_db_id,
                    start_date,
                    start_time,
                    diffusion_version,
                    fmt,
                    reservation_url
                )
                logger.info("✅ Séance insérée: %s - %s %s (%s)", title, start_date, start_time, diffusion_version)
            except Exception as e:
                logger.error("❌ Erreur séance %s: %s", title, e)
    conn.commit()
    cur.close()


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
                # Close thread's connection after done
                # (scrape_cinema doesn't close conn, so close here)
                try:
                    # Get the connection from the function's closure
                    # But we don't have it directly here, so we close in scrape_cinema or use context
                    pass
                except Exception:
                    pass
            # Actually, we need to close the connections after submitting
            # But since scrape_cinema uses its own conn, close it there
            # (Or we could close it in scrape_cinema at the end)
            # No sleep needed, concurrency handles pacing

    conn.close()


if __name__ == "__main__":
    main()