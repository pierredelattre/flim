#!/usr/bin/env python3
"""
scrap_movies.py
Scrape films à l'affiche via get_movies_with_showtimes(cinema_id, date)
et insère / met à jour dans la table `movies`.
"""

import os
import time
import random
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError

# DB
import psycopg2

# HTML cleaning
from bs4 import BeautifulSoup

# ta fonction existante
from allocine_wrapper import get_movies_with_showtimes

# --- config logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("scrap_movies")

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL non défini dans .env")

# --- utilitaires

def clean_html(text):
    """Supprime balises HTML et retourne texte propre."""
    if not text:
        return None
    try:
        soup = BeautifulSoup(text, "html.parser")
        # get_text() supprime les balises et conserve les retours à la ligne
        cleaned = soup.get_text(separator=" ", strip=True)
        return cleaned
    except Exception:
        # fallback basique
        import re
        return re.sub(r"<[^>]+>", "", text).strip()

def safe_get(d, keys):
    """Retourne la première valeur non-None trouvée pour une liste de clés possibles."""
    if not isinstance(d, dict):
        return None
    for k in keys:
        if k in d and d[k] not in (None, "", []):
            return d[k]
    return None

def parse_date_maybe(s):
    """Essaye de parser une date en date Python (YYYY-MM-DD) sinon retourne None."""
    if not s:
        return None
    # si c'est déjà un date/datetime
    if isinstance(s, datetime):
        return s.date()
    try:
        # formats courants
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except Exception:
                pass
        # fallback: tente parse plus librement (peut lever)
        from dateutil.parser import parse as dp
        return dp(s).date()
    except Exception:
        return None

# --- DB helpers

def get_conn():
    return psycopg2.connect(DATABASE_URL)

def ensure_movie_columns(conn):
    """Ajoute les colonnes manquantes si nécessaire (languages, is_premiere, director, original_title)."""
    cur = conn.cursor()
    cur.execute("""
    ALTER TABLE films
    ADD COLUMN IF NOT EXISTS languages TEXT,
    ADD COLUMN IF NOT EXISTS is_premiere BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS director TEXT,
    ADD COLUMN IF NOT EXISTS original_title TEXT;
    """)
    conn.commit()
    cur.close()

def upsert_movie(conn, movie):
    """
    movie: dict avec clefs:
      id_allocine, title, original_title, release_date (date or None), genre, duration, synopsis, poster_url, languages, is_premiere, director
    """
    cur = conn.cursor()
    query = """
    INSERT INTO films
      (id_allocine, title, original_title, release_date, genre, duration, synopsis, poster_url, languages, is_premiere, director, last_update)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
    ON CONFLICT (id_allocine) DO UPDATE
    SET title = EXCLUDED.title,
        original_title = COALESCE(EXCLUDED.original_title, films.original_title),
        release_date = COALESCE(EXCLUDED.release_date, films.release_date),
        genre = COALESCE(EXCLUDED.genre, films.genre),
        duration = COALESCE(EXCLUDED.duration, films.duration),
        synopsis = COALESCE(EXCLUDED.synopsis, films.synopsis),
        poster_url = COALESCE(EXCLUDED.poster_url, films.poster_url),
        languages = COALESCE(EXCLUDED.languages, films.languages),
        is_premiere = EXCLUDED.is_premiere,
        director = COALESCE(EXCLUDED.director, films.director),
        last_update = NOW();
    """
    cur.execute(query, (
        movie.get("id_allocine"),
        movie.get("title"),
        movie.get("original_title"),
        movie.get("release_date"),
        movie.get("genre"),
        movie.get("duration"),
        movie.get("synopsis"),
        movie.get("poster_url"),
        movie.get("languages"),
        movie.get("is_premiere"),
        movie.get("director")
    ))
    cur.close()

# --- mapping & ingestion

def build_movie_dict_from_allocine(raw):
    """
    Prend la dict 'raw' renvoyée par get_movies_with_showtimes et mappe vers la table movies.
    On essaie différentes clés possibles pour être robuste.
    """
    # id_allocine possible keys, check raw.get("id_allocine") first
    id_allocine = raw.get("id_allocine")
    if not id_allocine:
        id_allocine = safe_get(raw, ["code", "id", "idAllocine", "movieId", "ID"])
    if not id_allocine:
        return None
    id_allocine = str(id_allocine).strip()
    if not id_allocine:
        return None

    title = safe_get(raw, ["title", "name", "originalTitle", "original_title"])
    original_title = safe_get(raw, ["originalTitle", "original_title", "originalTitleFR", "titleOriginal"])
    # genre: peut être chaine ou liste
    genre = safe_get(raw, ["genre", "genres", "category"])
    if isinstance(genre, list):
        genre = ", ".join([str(g) for g in genre])
    # duration: runtime, duration, length
    duration_raw = safe_get(raw, ["runtime", "duration", "length"])
    duration = None
    if isinstance(duration_raw, int):
        duration = duration_raw
    elif isinstance(duration_raw, str):
        # parse duration string like "1h 55min" or "115 min"
        import re
        h_match = re.search(r"(\d+)\s*h", duration_raw)
        m_match = re.search(r"(\d+)\s*min", duration_raw)
        if h_match or m_match:
            h = int(h_match.group(1)) if h_match else 0
            m = int(m_match.group(1)) if m_match else 0
            duration = h * 60 + m
        else:
            # try to parse as integer minutes if possible
            try:
                duration = int(duration_raw.strip())
            except Exception:
                duration = None
    elif isinstance(duration_raw, float):
        duration = int(duration_raw)

    # poster
    poster_url = safe_get(raw, ["urlPoster", "poster_url", "poster", "image"])
    # synopsis (avec html), check "synopsisFull" too
    synopsis_raw = safe_get(raw, ["synopsis", "synopsisShort", "shortSynopsis", "longSynopsis"])
    if not synopsis_raw:
      synopsis_raw = raw.get("synopsisFull")
    synopsis = clean_html(synopsis_raw) if synopsis_raw else None

    # release date
    rd_raw = safe_get(raw, ["releaseDate", "release_date", "release", "dateRelease"])
    if not rd_raw:
      # try releases list first element releaseDate
      rd_raw = None
      releases = raw.get("releases")
      if isinstance(releases, (list, tuple)) and len(releases) > 0 and isinstance(releases[0], dict):
        rd_raw = releases[0].get("releaseDate")
    release_date = parse_date_maybe(rd_raw)

    # languages, director, is_premiere
    languages = safe_get(raw, ["languages", "language", "originalLanguage"])
    if isinstance(languages, list):
      lolanguages = ", ".join([str(l) for l in languages if l])

    director = None
    # certains wrappers renvoient 'casting' ou 'directors'
    if safe_get(raw, ["directors", "director"]):
        director = safe_get(raw, ["directors", "director"])
        if isinstance(director, list):
            director = ", ".join([str(d) for d in director])
    else:
        # regarder dans castingShort, credits, etc.
        cast = safe_get(raw, ["castingShort", "casting", "credits"])
        if isinstance(cast, (list, tuple)):
            # prendre premier identifé comme réalisateur si présent (heuristique)
            director = ", ".join([str(x) for x in cast])

    # is_premiere heuristique
    is_premiere = False
    ip = safe_get(raw, ["isPremiere", "premiere"])
    if isinstance(ip, bool):
        is_premiere = ip
    elif isinstance(ip, str):
        is_premiere = ip.lower() in ("true", "1", "yes", "oui", "premiere")

    return {
        "id_allocine": id_allocine,
        "title": title,
        "original_title": original_title,
        "release_date": release_date,
        "genre": genre,
        "duration": duration,
        "synopsis": synopsis,
        "poster_url": poster_url,
        "languages": languages,
        "is_premiere": is_premiere,
        "director": director
    }


def scrape_cinema(cinema_id, cinema_name, day, task_counter, total_tasks, cinema_counter, total_cinemas):
    """Helper function to scrape movies for a single cinema and a single day."""
    logger.info("[cinema %d/%d | task %d/%d] Scraping films pour %s (%s) à la date %s", cinema_counter, total_cinemas, task_counter, total_tasks, cinema_name, cinema_id, day)
    import concurrent.futures
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(get_movies_with_showtimes, cinema_id, day)
        try:
            movies = future.result(timeout=15)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(f"Timeout exceeded for get_movies_with_showtimes({cinema_id}, {day})")
    return movies


def main():
    logger.info("Démarrage scrap films -> BDD")

    conn = get_conn()
    ensure_movie_columns(conn)

    # récupérer la liste des cinémas en BDD
    cur = conn.cursor()
    cur.execute("SELECT id_allocine, name FROM cinemas")
    cinemas = cur.fetchall()
    cur.close()
    logger.info("Nombre de cinémas en BDD: %s", len(cinemas))

    # Générer la liste d'un seul jour (J+7)
    today_date = datetime.today()
    days = [(today_date + timedelta(days=7)).strftime("%Y-%m-%d")]
    total_tasks = len(cinemas) * len(days)

    seen = set()
    inserted = 0
    failed = 0
    task_counter = 0
    cinema_counter = 0
    done = 0

    batch_size = 300
    total_cinemas = len(cinemas)

    for batch_start in range(0, total_cinemas, batch_size):
        batch_end = min(batch_start + batch_size, total_cinemas)
        batch_cinemas = cinemas[batch_start:batch_end]
        logger.info("Début du batch de cinémas %d à %d", batch_start + 1, batch_end)

        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_task = {}
            cinema_counter_batch = batch_start
            for cinema_id, cinema_name in batch_cinemas:
                cinema_counter_batch += 1
                logger.info("[%d/%d] Scraping films pour %s (%s)", cinema_counter_batch, total_cinemas, cinema_name, cinema_id)
                for day in days:
                    task_counter += 1
                    future = executor.submit(scrape_cinema, cinema_id, cinema_name, day, task_counter, total_tasks, cinema_counter_batch, total_cinemas)
                    future_to_task[future] = (cinema_id, cinema_name, day)

            try:
                for future in as_completed(future_to_task, timeout=30):
                    cinema_id, cinema_name, day = future_to_task[future]
                    done += 1
                    if done % 100 == 0:
                        logger.info("Progression: %d/%d tâches terminées", done, total_tasks)
                    try:
                        movies = future.result()
                    except TimeoutError as e:
                        logger.exception("❌ Timeout pour get_movies_with_showtimes pour %s (%s) à la date %s: %s", cinema_name, cinema_id, day, e)
                        failed += 1
                        continue
                    except Exception as e:
                        logger.exception("❌ Erreur get_movies_with_showtimes pour %s (%s) à la date %s: %s", cinema_name, cinema_id, day, e)
                        failed += 1
                        continue

                    if not movies:
                        logger.info(" -> aucun film renvoyé pour %s à la date %s", cinema_name, day)
                        continue

                    for raw_movie in movies:
                        movie_dict = build_movie_dict_from_allocine(raw_movie)
                        # print("RAW MOVIE:", raw_movie)

                        if not movie_dict:
                            logger.info(" -> film sans id, skip: %s", raw_movie)
                            continue

                        movie_key = movie_dict["id_allocine"]
                        if movie_key in seen:
                            # déjà inséré (ou mis à jour) par un autre cinéma ou jour
                            continue

                        try:
                            upsert_movie(conn, movie_dict)
                            seen.add(movie_key)
                            inserted += 1
                            logger.info("✅ + film inséré/maj: %s (%s)", movie_dict.get("title"), movie_key)
                        except Exception as e:
                            logger.exception("❌ Erreur insertion film %s: %s", movie_dict.get("title"), e)
                            failed += 1

                    try:
                        conn.commit()
                    except Exception as e:
                        logger.exception("❌ Erreur commit pour cinéma %s (%s) à la date %s: %s", cinema_name, cinema_id, day, e)
                        failed += 1
            except FuturesTimeoutError:
                logger.warning("Timeout global sur l'attente des tâches asynchrones, certaines tâches peuvent ne pas être terminées.")

        logger.info("Fin du batch de cinémas %d à %d", batch_start + 1, batch_end)
        if batch_end < total_cinemas:
            logger.info("Pause de 10 secondes entre les batches pour limiter la charge")
            time.sleep(10)
        # Pause après chaque cinéma complet dans le batch to smooth load
        # But here we do it after batch, so also add small sleep here
        time.sleep(random.uniform(0.3, 0.8))

    conn.close()
    logger.info("Terminé. Insérés/maj: %d, échoués: %d", inserted, failed)


if __name__ == "__main__":
    main()