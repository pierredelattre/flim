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
import re

# DB
import psycopg2

# HTML cleaning
from bs4 import BeautifulSoup

# ta fonction existante
from allocine_wrapper import get_movies_with_showtimes

# --- config logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("scrap_movies")
logger.setLevel(logging.DEBUG)

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
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        logger.exception("❌ Échec connexion DB: %s", e)
        raise

def clean_entry(entry):
    if not entry:
        return None
    entry = re.sub(r"[{}]", "", entry)
    parts = [e.strip() for e in entry.split(",")]
    return parts[0] if parts else None

def get_or_create_genre(conn, name):
    if not name:
        return None
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM genre WHERE name = %s", (name,))
        result = cur.fetchone()
        if result:
            return result[0]
        cur.execute("INSERT INTO genre (name) VALUES (%s) RETURNING id", (name,))
        created = cur.fetchone()
        conn.commit()
        return created[0] if created else None
    except Exception as e:
        logger.exception("Erreur DB get_or_create_genre(%s): %s", name, e)
        raise
    finally:
        cur.close()

def get_or_create_language(conn, name):
    if not name:
        return None
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM language WHERE name = %s", (name,))
        result = cur.fetchone()
        if result:
            return result[0]
        cur.execute("INSERT INTO language (name) VALUES (%s) RETURNING id", (name,))
        created = cur.fetchone()
        conn.commit()
        return created[0] if created else None
    except Exception as e:
        logger.exception("Erreur DB get_or_create_language(%s): %s", name, e)
        raise
    finally:
        cur.close()

def ensure_movie_columns(conn):
    """Ajoute les colonnes manquantes si nécessaire (languages, is_premiere, director, original_title)."""
    cur = conn.cursor()
    cur.execute("""
    ALTER TABLE films
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
      (id_allocine, title, original_title, release_date, duration, synopsis, poster_url, is_premiere, director, last_update, genre_id, language_id)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s)
    ON CONFLICT (id_allocine) DO UPDATE
    SET title = EXCLUDED.title,
        original_title = COALESCE(EXCLUDED.original_title, films.original_title),
        release_date = COALESCE(EXCLUDED.release_date, films.release_date),
        duration = COALESCE(EXCLUDED.duration, films.duration),
        synopsis = COALESCE(EXCLUDED.synopsis, films.synopsis),
        poster_url = COALESCE(EXCLUDED.poster_url, films.poster_url),
        is_premiere = EXCLUDED.is_premiere,
        director = COALESCE(EXCLUDED.director, films.director),
        genre_id = COALESCE(EXCLUDED.genre_id, films.genre_id),
        language_id = COALESCE(EXCLUDED.language_id, films.language_id),
        last_update = NOW();
    """
    params = (
        movie.get("id_allocine"),
        movie.get("title"),
        movie.get("original_title"),
        movie.get("release_date"),
        movie.get("duration"),
        movie.get("synopsis"),
        movie.get("poster_url"),
        movie.get("is_premiere"),
        movie.get("director"),
        movie.get("genre_id"),
        movie.get("language_id")
    )
    try:
        cur.execute(query, params)
    except Exception as e:
        logger.exception("Erreur upsert_movie pour film %s: %s", movie.get("id_allocine"), e)
        logger.error("Params: %s", params)
        if hasattr(cur, "statusmessage"):
            logger.error("Cur status: %s", cur.statusmessage)
        raise
    finally:
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
        logger.warning("⛔️ build_movie_dict_from_allocine -> id_allocine invalide: %s", raw)
        return None
    id_allocine = str(id_allocine).strip()
    if not id_allocine:
        logger.warning("⛔️ build_movie_dict_from_allocine -> id_allocine invalide: %s", raw)
        return None

    title = safe_get(raw, ["title", "name", "originalTitle", "original_title"])
    original_title = safe_get(raw, ["originalTitle", "original_title", "originalTitleFR", "titleOriginal"])
    # genre: peut être chaine ou liste
    genre = safe_get(raw, ["genre", "genres", "category"])
    if isinstance(genre, list):
        genre = [str(g).strip() for g in genre if g]
    elif isinstance(genre, str):
        genre = [g.strip() for g in genre.split(",") if g.strip()]
    else:
        genre = []
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
        languages = [str(l).strip() for l in languages if l]
    elif isinstance(languages, str):
        languages = [l.strip() for l in languages.split(",") if l.strip()]
    else:
        languages = []

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

    # Générer la liste des 7 jours à partir d'aujourd'hui (J0 → J+6)
    today_date = datetime.today()
    days = [(today_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
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
                for future in as_completed(future_to_task):
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
                    logger.info("🎬 Films récupérés pour %s à la date %s : %s", cinema_name, day, len(movies))
                    if not movies:
                        logger.info(" -> aucun film renvoyé pour %s à la date %s", cinema_name, day)
                        continue

                    for raw_movie in movies:
                        movie_dict = build_movie_dict_from_allocine(raw_movie)
                        if not movie_dict:
                            logger.warning("⚠️ film ignoré (pas d'id_allocine ou parsing échoué): %s", raw_movie)
                            continue

                        # Normalize genres/languages into lists
                        genres = movie_dict.get("genre")
                        if isinstance(genres, str):
                            genres = [g.strip() for g in re.sub(r"[{}]", "", genres).split(",") if g.strip()]
                        elif not isinstance(genres, list):
                            genres = []

                        languages = movie_dict.get("languages")
                        if isinstance(languages, str):
                            languages = [l.strip() for l in re.sub(r"[{}]", "", languages).split(",") if l.strip()]
                        elif not isinstance(languages, list):
                            languages = []

                        # set primary genre_id from first genre if present
                        if genres:
                            primary_genre = genres[0]
                            movie_dict["genre_id"] = get_or_create_genre(conn, primary_genre)
                        else:
                            movie_dict["genre_id"] = None
                        # set primary language_id from first language if present
                        if languages:
                            primary_language = languages[0]
                            movie_dict["language_id"] = get_or_create_language(conn, primary_language)
                        else:
                            movie_dict["language_id"] = None

                        movie_key = movie_dict["id_allocine"]
                        if movie_key in seen:
                            # déjà inséré (ou mis à jour) par un autre cinéma ou jour
                            continue

                        logger.info("Tentative insertion film %s (%s)", movie_dict.get("title"), movie_dict.get("id_allocine"))
                        try:
                            upsert_movie(conn, movie_dict)
                            try:
                                conn.commit()  # commit immédiat après insertion
                            except Exception as e:
                                logger.exception("❌ Erreur commit film %s: %s", movie_dict.get("id_allocine"), e)
                                failed += 1
                                continue

                            # Insère les relations genres/langues
                            try:
                                with conn.cursor() as cur:
                                    for g in genres:
                                        genre_id = get_or_create_genre(conn, g)
                                        cur.execute(
                                            "INSERT INTO film_genre (film_id, genre_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                                            (movie_dict["id_allocine"], genre_id)
                                        )
                                    for l in languages:
                                        language_id = get_or_create_language(conn, l)
                                        cur.execute(
                                            "INSERT INTO film_language (film_id, language_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                                            (movie_dict["id_allocine"], language_id)
                                        )
                                    conn.commit()
                                    # Now safe to remove genre and languages from movie_dict
                                    movie_dict.pop("genre", None)
                                    movie_dict.pop("languages", None)
                            except Exception as e:
                                logger.exception("❌ Erreur insertion relations pour film %s: %s", movie_dict.get("id_allocine"), e)

                            seen.add(movie_key)
                            inserted += 1
                            logger.info("✅ + film inséré/maj: %s (%s)", movie_dict.get("title"), movie_key)

                            # Vérification immédiate
                            try:
                                with conn.cursor() as vcur:
                                    vcur.execute("SELECT id_allocine FROM films WHERE id_allocine = %s", (movie_dict["id_allocine"],))
                                    res = vcur.fetchone()
                            except Exception as e:
                                logger.exception("❌ Erreur vérif film en BDD: %s", e)

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