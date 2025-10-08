import logging
import os
from datetime import date, datetime, timedelta
from typing import List, Optional, Set

import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, model_validator
import unicodedata

load_dotenv()

GENRE_OPTIONS = [
  "Action",
  "Animation",
  "Aventure",
  "Biopic",
  "Comédie",
  "Comédie dramatique",
  "Comédie musicale",
  "Court métrage",
  "Documentaire",
  "Drame",
  "Epouvante-Horreur",
  "Espionnage",
  "Famille",
  "Fantastique",
  "Guerre",
  "Historique",
  "Judiciaire",
  "Musical",
  "Policier",
  "Romance",
  "Science-fiction",
  "Thriller",
  "Western",
  "Expérimental",
  "Sport",
  "Péplum",
  "Arts martiaux",
  "Road movie",
  "Film noir",
  "Super-héros",
  "Satire",
  "Fiction",
  "Animation 3D",
  "Drame psychologique",
  "Film d’auteur",
  "Film musical",
  "Film politique",
  "Drame social",
  "Conte",
  "Enquête",
  "Adaptation littéraire",
  "Mystère",
  "Suspense",
  "Animation japonaise",
  "Animation jeunesse",
  "Film historique",
  "Dystopie",
  "Chronique",
  "Aventure humaine",
  "Cinéma engagé",
]

SUBTITLE_OPTIONS = ["ORIGINAL", "SUBS", "DUBBED"]

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
  logging.warning("DATABASE_URL environment variable is not set")

app = FastAPI()

app.add_middleware(
  CORSMiddleware,
  allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)


def get_connection() -> psycopg2.extensions.connection:
  if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not configured")
  return psycopg2.connect(DATABASE_URL)


def distance_sql(lat_expr: str, lon_expr: str) -> str:
  return f"""
    2 * 6371 * ASIN(
      SQRT(
        LEAST(
          1.0,
          POWER(SIN(RADIANS({lat_expr} - %(center_lat)s) / 2), 2) +
          COS(RADIANS(%(center_lat)s)) * COS(RADIANS({lat_expr})) *
          POWER(SIN(RADIANS({lon_expr} - %(center_lon)s) / 2), 2)
        )
      )
    )
  """

# --- Accent-stripping helper for fallback LIKE matching ---
def _strip_accents(text: str) -> str:
  """Return a lowercase, accent-stripped version of text (for fallback LIKE)."""
  if not isinstance(text, str):
    return text
  # Normalize then remove combining marks
  normalized = unicodedata.normalize("NFD", text)
  no_accents = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
  return no_accents.lower()


def split_to_list(value) -> List[str]:
  if value is None:
    return []
  if isinstance(value, list):
    result: List[str] = []
    for item in value:
      if item is None:
        continue
      text = str(item).strip()
      if text:
        result.append(text)
    return result
  if isinstance(value, str):
    return [segment.strip() for segment in value.split(",") if segment.strip()]
  return []


def showtime_timestamp(start_date_value, start_time_value) -> Optional[float]:
  try:
    if isinstance(start_date_value, date):
      day = start_date_value
    elif isinstance(start_date_value, str):
      day = date.fromisoformat(start_date_value)
    else:
      return None

    if hasattr(start_time_value, "hour") and hasattr(start_time_value, "minute"):
      hour = int(start_time_value.hour)
      minute = int(start_time_value.minute)
      second = int(getattr(start_time_value, "second", 0))
    elif isinstance(start_time_value, str):
      parts = start_time_value.split(":")
      if len(parts) < 2:
        return None
      hour = int(parts[0])
      minute = int(parts[1])
      second = int(parts[2]) if len(parts) > 2 else 0
    else:
      return None

    dt_value = datetime(day.year, day.month, day.day, hour, minute, second)
    return dt_value.timestamp()
  except Exception:
    return None


class MoviesNearbyRequest(BaseModel):
  lat: Optional[float] = None
  lon: Optional[float] = None
  radius_km: Optional[float] = None
  movie_id: Optional[int] = None
  cinema_id: Optional[int] = None
  override_location: bool = False
  center_lat: Optional[float] = None
  center_lon: Optional[float] = None
  date: Optional[str] = None
  genres: Optional[List[str]] = None
  languages: Optional[List[str]] = None
  subtitles: Optional[List[str]] = None
  duration_max_minutes: Optional[int] = None
  sort_by: Optional[str] = None

  @model_validator(mode="after")
  def ensure_coordinates(self):
    # Guard against NaN values getting through as floats
    def _is_nan(x):
      try:
        return isinstance(x, float) and x != x
      except Exception:
        return False

    if self.lat is not None and _is_nan(self.lat):
      raise ValueError("lat must be a number")
    if self.lon is not None and _is_nan(self.lon):
      raise ValueError("lon must be a number")
    if self.center_lat is not None and _is_nan(self.center_lat):
      raise ValueError("center_lat must be a number")
    if self.center_lon is not None and _is_nan(self.center_lon):
      raise ValueError("center_lon must be a number")

    if self.override_location:
      if self.center_lat is None or self.center_lon is None:
        raise ValueError("center_lat and center_lon are required when override_location is true")
    else:
      if self.lat is None or self.lon is None:
        raise ValueError("lat and lon are required unless override_location is true")

    return self


class MovieDetailsRequest(BaseModel):
  lat: float
  lon: float
  radius_km: float = 5
  date: Optional[str] = None
  genres: Optional[List[str]] = None
  languages: Optional[List[str]] = None
  subtitles: Optional[List[str]] = None
  duration_max_minutes: Optional[int] = None
  sort_by: Optional[str] = None


def ensure_search_schema() -> None:
  """Create the geo_cities table, pg_trgm extension, and required indexes if missing."""
  try:
    conn = get_connection()
  except Exception as exc:
    logging.error("Unable to connect to database while ensuring schema: %s", exc)
    return

  try:
    conn.autocommit = True
    with conn.cursor() as cur:
      cur.execute("CREATE EXTENSION IF NOT EXISTS unaccent;")
      cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
      cur.execute(
        """
        CREATE TABLE IF NOT EXISTS geo_cities (
          id SERIAL PRIMARY KEY,
          name TEXT NOT NULL,
          zipcode TEXT,
          lat DOUBLE PRECISION NOT NULL,
          lon DOUBLE PRECISION NOT NULL
        );
        """
      )
      index_commands: List[sql.SQL] = [
        sql.SQL("CREATE INDEX IF NOT EXISTS idx_films_title_trgm ON films USING gin (title gin_trgm_ops);")
      ]
      index_commands.append(
        sql.SQL("CREATE INDEX IF NOT EXISTS idx_films_original_title_trgm ON films USING gin (original_title gin_trgm_ops);")
      )
      index_commands.append(
        sql.SQL("CREATE INDEX IF NOT EXISTS idx_cinemas_name_trgm ON cinemas USING gin (name gin_trgm_ops);")
      )
      index_commands.append(
        sql.SQL("CREATE INDEX IF NOT EXISTS idx_cities_name_trgm ON geo_cities USING gin (name gin_trgm_ops);")
      )
      index_commands.append(
        sql.SQL("CREATE INDEX IF NOT EXISTS idx_cities_zipcode_trgm ON geo_cities USING gin (zipcode gin_trgm_ops);")
      )
      for statement in index_commands:
        cur.execute(statement)
  except Exception as exc:
    logging.error("Error ensuring search schema: %s", exc)
  finally:
    conn.close()


@app.on_event("startup")
def on_startup() -> None:
  ensure_search_schema()


@app.get("/api/filters_options")
def filters_options():
  languages: Set[str] = set()
  conn = None

  try:
    conn = get_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
      cur.execute(
        """
        SELECT languages
        FROM films
        WHERE languages IS NOT NULL
          AND TRIM(languages) <> ''
        """
      )
      rows = cur.fetchall()
      for row in rows:
        for entry in split_to_list(row.get("languages")):
          if entry:
            languages.add(entry)
  except Exception as exc:
    logging.error("Error while retrieving filter options: %s", exc)
  finally:
    if conn is not None:
      conn.close()

  normalized_languages = sorted({lang.strip() for lang in languages if isinstance(lang, str) and lang.strip()}, key=lambda s: s.lower())

  return {
    "genres": GENRE_OPTIONS,
    "languages": normalized_languages,
    "subtitles": SUBTITLE_OPTIONS,
  }


@app.get("/api/search_suggest")
def search_suggest(q: str = Query(..., min_length=1), limit: int = Query(10, ge=1, le=25)):
  query_text = q.strip()
  if not query_text:
    return {"suggestions": []}

  # SQL pattern (keeps wildcards) and normalized fallback (accent-stripped, lowercase)
  pattern = "%" + query_text.replace("%", "\\%").replace("_", "\\_") + "%"
  pattern_norm = "%" + _strip_accents(query_text).replace("%", "").replace("_", "") + "%"
  params = {"pattern": pattern, "pattern_norm": pattern_norm, "limit": limit}

  try:
    conn = get_connection()
  except Exception as exc:
    logging.error("Database connection error during search_suggest: %s", exc)
    raise HTTPException(status_code=500, detail="Database connection error")

  films: List[dict] = []
  cinemas: List[dict] = []
  cities: List[dict] = []

  try:
    # --- FILMS ---
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
      cur.execute(
        """
        SELECT id,
               title,
               COALESCE(NULLIF(original_title, ''), '') AS original_title
        FROM films
        WHERE
          -- accent-insensitive match
          unaccent(lower(title)) LIKE unaccent(lower(%(pattern)s))
          OR unaccent(lower(COALESCE(original_title, ''))) LIKE unaccent(lower(%(pattern)s))
          -- fallback: python-normalized text LIKE (for safety if extension unavailable on read replica)
          OR lower(title) LIKE %(pattern_norm)s
          OR lower(COALESCE(original_title, '')) LIKE %(pattern_norm)s
        ORDER BY title ASC
        LIMIT %(limit)s;
        """,
        params,
      )
      films = cur.fetchall()

    # --- CINEMAS ---
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
      try:
        cur.execute(
          f"""
          SELECT id,
                 name,
                 COALESCE(lat, latitude) AS lat,
                 COALESCE(lon, longitude) AS lon
          FROM cinemas
          WHERE
            unaccent(lower(name)) LIKE unaccent(lower(%(pattern)s))
            OR lower(name) LIKE %(pattern_norm)s
          ORDER BY name ASC
          LIMIT %(limit)s;
          """,
          params,
        )
        cinemas = cur.fetchall()
      except Exception as e:
        logging.warning("Cinemas query without lat/lon fallback due to schema mismatch: %s", e)
        cur.execute(
          """
          SELECT id, name
          FROM cinemas
          WHERE
            unaccent(lower(name)) LIKE unaccent(lower(%(pattern)s))
            OR lower(name) LIKE %(pattern_norm)s
          ORDER BY name ASC
          LIMIT %(limit)s;
          """,
          params,
        )
        rows = cur.fetchall()
        cinemas = [{"id": r["id"], "name": r["name"], "lat": None, "lon": None} for r in rows]

    # --- CITIES ---
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
      cur.execute(
        """
        SELECT id,
               name,
               COALESCE(zipcode, '') AS zipcode,
               lat,
               lon
        FROM geo_cities
        WHERE
          unaccent(lower(name)) LIKE unaccent(lower(%(pattern)s))
          OR lower(name) LIKE %(pattern_norm)s
          OR lower(COALESCE(zipcode, '')) LIKE %(pattern_norm)s
        ORDER BY name ASC
        LIMIT %(limit)s;
        """,
        params,
      )
      cities = cur.fetchall()
  finally:
    conn.close()

  suggestions: List[dict] = []

  for row in films:
    suggestion = {
      "type": "film",
      "id": row["id"],
      "label": row["title"],
    }
    if row.get("original_title") and row["original_title"].lower() != row["title"].lower():
      suggestion["sublabel"] = row["original_title"]
    suggestions.append(suggestion)
    if len(suggestions) >= limit:
      return {"suggestions": suggestions}

  for row in cinemas:
    suggestion = {
      "type": "cinema",
      "id": row["id"],
      "label": row["name"],
    }
    if row.get("lat") is not None and row.get("lon") is not None:
      suggestion["lat"] = float(row["lat"])
      suggestion["lon"] = float(row["lon"])
    suggestions.append(suggestion)
    if len(suggestions) >= limit:
      return {"suggestions": suggestions}

  for row in cities:
    suggestion = {
      "type": "city",
      "id": row["id"],
      "label": row["name"],
      "lat": float(row["lat"]),
      "lon": float(row["lon"]),
    }
    if row.get("zipcode"):
      suggestion["sublabel"] = row["zipcode"]
    suggestions.append(suggestion)
    if len(suggestions) >= limit:
      return {"suggestions": suggestions}

  return {"suggestions": suggestions}


@app.post("/api/movies_nearby")
def movies_nearby(req: MoviesNearbyRequest = Body(...)):
  radius = req.radius_km if req.radius_km and req.radius_km > 0 else 5
  center_lat = req.center_lat if req.override_location else req.lat
  center_lon = req.center_lon if req.override_location else req.lon
  sort_options = {"relevance", "distance", "earliest_showtime", "title_asc", "duration_asc"}
  sort_by = (req.sort_by or "relevance").lower()
  if sort_by not in sort_options:
    sort_by = "relevance"

  filter_date = None
  if req.date:
    try:
      filter_date = date.fromisoformat(req.date)
    except ValueError:
      logging.warning("Invalid date filter received: %s", req.date)

  subtitles_filter = [str(sub).strip().upper() for sub in (req.subtitles or []) if isinstance(sub, str) and str(sub).strip()]
  duration_max = req.duration_max_minutes if req.duration_max_minutes and req.duration_max_minutes > 0 else None
  languages_filter = [str(lang).strip().lower() for lang in (req.languages or []) if isinstance(lang, str) and str(lang).strip()]
  genres_filter = [str(genre).strip().lower() for genre in (req.genres or []) if isinstance(genre, str) and str(genre).strip()]
  subtitles_set = set(subtitles_filter)
  languages_filter_set = set(languages_filter)
  genres_filter_set = set(genres_filter)

  # Extra guard in case NaN slips through
  if isinstance(center_lat, float) and center_lat != center_lat:
    raise HTTPException(status_code=422, detail="Invalid latitude")
  if isinstance(center_lon, float) and center_lon != center_lon:
    raise HTTPException(status_code=422, detail="Invalid longitude")

  if center_lat is None or center_lon is None:
    raise HTTPException(status_code=400, detail="Missing coordinates")

  cinema_lat_expr = "COALESCE(c.lat, c.latitude)"
  cinema_lon_expr = "COALESCE(c.lon, c.longitude)"
  dist_expr = distance_sql(cinema_lat_expr, cinema_lon_expr)

  where_clauses = [f"{cinema_lat_expr} IS NOT NULL", f"{cinema_lon_expr} IS NOT NULL"]
  params = {
    "center_lat": center_lat,
    "center_lon": center_lon,
    "radius_km": radius,
  }

  if filter_date:
    where_clauses.append("s.start_date = %(filter_date)s")
    params["filter_date"] = filter_date
  else:
    where_clauses.append("s.start_date >= %(today)s")
    params["today"] = date.today()

  if subtitles_filter:
    where_clauses.append("UPPER(COALESCE(s.diffusion_version, '')) = ANY(%(subtitles)s)")
    params["subtitles"] = subtitles_filter

  if duration_max is not None:
    where_clauses.append("(m.duration IS NULL OR m.duration <= %(duration_max)s)")
    params["duration_max"] = duration_max

  if languages_filter:
    params["languages_like"] = [f"%{lang}%" for lang in languages_filter]
    where_clauses.append("(m.languages IS NULL OR m.languages = '' OR LOWER(m.languages) LIKE ANY(%(languages_like)s))")

  if genres_filter:
    params["genres_like"] = [f"%{genre}%" for genre in genres_filter]
    where_clauses.append("(m.genre IS NULL OR LOWER(m.genre) LIKE ANY(%(genres_like)s))")

  if req.movie_id is not None:
    where_clauses.append("s.movie_id = %(movie_id)s")
    params["movie_id"] = req.movie_id

  if req.cinema_id is not None:
    where_clauses.append("s.cinema_id = %(cinema_id)s")
    params["cinema_id"] = req.cinema_id
  else:
    where_clauses.append(f"{dist_expr} <= %(radius_km)s")

  query = f"""
    SELECT
      m.id AS film_id,
      m.title,
      COALESCE(m.original_title, '') AS original_title,
      m.poster_url,
      m.duration,
      m.release_date,
      m.synopsis,
      m.genre,
      m.languages,
      c.id AS cinema_id,
      c.name AS cinema_name,
      c.address,
      {cinema_lat_expr} AS lat,
      {cinema_lon_expr} AS lon,
      {dist_expr} AS distance_km,
      s.start_date,
      s.start_time,
      s.diffusion_version,
      s.format,
      s.reservation_url
    FROM showtimes s
    JOIN cinemas c ON c.id = s.cinema_id
    JOIN films m ON m.id = s.movie_id
    WHERE {' AND '.join(where_clauses)}
    ORDER BY m.title ASC, c.name ASC, s.start_date ASC, s.start_time ASC;
  """

  try:
    conn = get_connection()
  except Exception as exc:
    logging.error("Database connection error during movies_nearby: %s", exc)
    raise HTTPException(status_code=500, detail="Database connection error")

  movies = {}
  try:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
      cur.execute(query, params)
      rows = cur.fetchall()
  finally:
    conn.close()

  for row in rows:
    film_id = row["film_id"]
    movie = movies.get(film_id)
    if not movie:
      genres_list = split_to_list(row.get("genre"))
      languages_list = split_to_list(row.get("languages"))
      movie = {
        "id": film_id,
        "title": row["title"],
        "original_title": row.get("original_title") or None,
        "poster": row.get("poster_url"),
        "duration": row.get("duration"),
        "release_date": row.get("release_date"),
        "synopsis": row.get("synopsis"),
        "genre": row.get("genre"),
        "genres": genres_list,
        "languages": languages_list,
        "language": languages_list[0] if languages_list else None,
        "cinemas": [],
      }
      movies[film_id] = movie

    cinemas_list = movie["cinemas"]
    cinema = next((c for c in cinemas_list if c["id"] == row["cinema_id"]), None)
    if not cinema:
      cinema = {
        "id": row["cinema_id"],
        "name": row["cinema_name"],
        "address": row.get("address"),
        "lat": float(row["lat"]) if row.get("lat") is not None else None,
        "lon": float(row["lon"]) if row.get("lon") is not None else None,
        "distance_km": float(row["distance_km"]) if row.get("distance_km") is not None else None,
        "showtimes": [],
      }
      cinemas_list.append(cinema)

    cinema["showtimes"].append({
      "start_date": row["start_date"].isoformat() if isinstance(row["start_date"], date) else row["start_date"],
      "start_time": row["start_time"].isoformat() if hasattr(row["start_time"], "isoformat") else row["start_time"],
      "diffusion_version": row.get("diffusion_version"),
      "format": row.get("format"),
      "reservation_url": row.get("reservation_url"),
    })

  subtitle_set = set(subtitles_filter)
  languages_filter_set = set(languages_filter)
  genres_filter_set = set(genres_filter)
  processed_movies: List[dict] = []

  for movie in movies.values():
    movie_duration = movie.get("duration")
    if duration_max is not None and isinstance(movie_duration, int) and movie_duration > duration_max:
      continue

    if languages_filter_set:
      movie_languages = [lang.lower() for lang in (movie.get("languages") or [])]
      if movie_languages and not languages_filter_set.intersection(movie_languages):
        continue

    if genres_filter_set:
      movie_genres = [genre.lower() for genre in (movie.get("genres") or [])]
      if movie_genres and not genres_filter_set.intersection(movie_genres):
        continue

    new_cinemas = []
    min_distance = None
    earliest_ts = None

    for cinema in movie.get("cinemas", []):
      showtimes = []
      for show in cinema.get("showtimes", []):
        if filter_date and show.get("start_date") != filter_date.isoformat():
          continue
        if subtitle_set:
          subtitle_value = (show.get("diffusion_version") or "").strip().upper()
          if subtitle_value not in subtitle_set:
            continue
        timestamp = showtime_timestamp(show.get("start_date"), show.get("start_time"))
        if timestamp is not None:
          if earliest_ts is None or timestamp < earliest_ts:
            earliest_ts = timestamp
        showtimes.append(show)

      if not showtimes:
        continue

      distance_val = cinema.get("distance_km")
      if isinstance(distance_val, (int, float)):
        if min_distance is None or distance_val < min_distance:
          min_distance = distance_val

      cinema_copy = {**cinema, "showtimes": showtimes}
      new_cinemas.append(cinema_copy)

    if not new_cinemas:
      continue

    movie_copy = {**movie, "cinemas": new_cinemas, "_meta": {"min_distance": min_distance, "earliest_ts": earliest_ts}}
    processed_movies.append(movie_copy)

  if sort_by == "distance":
    processed_movies.sort(key=lambda m: m["_meta"]["min_distance"] if m["_meta"]["min_distance"] is not None else float("inf"))
  elif sort_by == "earliest_showtime":
    processed_movies.sort(key=lambda m: m["_meta"]["earliest_ts"] if m["_meta"]["earliest_ts"] is not None else float("inf"))
  elif sort_by == "title_asc":
    processed_movies.sort(key=lambda m: (m.get("title") or "").lower())
  elif sort_by == "duration_asc":
    processed_movies.sort(key=lambda m: m.get("duration") if isinstance(m.get("duration"), int) else float("inf"))

  for movie in processed_movies:
    movie.pop("_meta", None)

  response_payload = {
    "success": True,
    "center_lat": center_lat,
    "center_lon": center_lon,
    "radius_km": radius,
    "data": processed_movies,
  }

  return response_payload


@app.post("/api/movie/{movie_id}")
def movie_details(movie_id: int, req: MovieDetailsRequest = Body(...)):
  radius = req.radius_km if req.radius_km and req.radius_km > 0 else 5
  cinema_lat_expr = "COALESCE(c.lat, c.latitude)"
  cinema_lon_expr = "COALESCE(c.lon, c.longitude)"
  dist_expr = distance_sql(cinema_lat_expr, cinema_lon_expr)
  sort_options = {"relevance", "distance", "earliest_showtime", "title_asc", "duration_asc"}
  sort_by = (req.sort_by or "relevance").lower()
  if sort_by not in sort_options:
    sort_by = "relevance"

  filter_date = None
  if req.date:
    try:
      filter_date = date.fromisoformat(req.date)
    except ValueError:
      logging.warning("Invalid date filter received for movie %s: %s", movie_id, req.date)

  subtitles_filter = [str(sub).strip().upper() for sub in (req.subtitles or []) if isinstance(sub, str) and str(sub).strip()]
  duration_max = req.duration_max_minutes if req.duration_max_minutes and req.duration_max_minutes > 0 else None
  languages_filter = [str(lang).strip().lower() for lang in (req.languages or []) if isinstance(lang, str) and str(lang).strip()]
  genres_filter = [str(genre).strip().lower() for genre in (req.genres or []) if isinstance(genre, str) and str(genre).strip()]
  subtitles_set = set(subtitles_filter)
  languages_filter_set = set(languages_filter)
  genres_filter_set = set(genres_filter)

  if filter_date:
    start_date = filter_date
    end_date = filter_date
  else:
    start_date = date.today()
    end_date = start_date + timedelta(days=6)

  try:
    conn = get_connection()
  except Exception as exc:
    logging.error("Database connection error during movie_details: %s", exc)
    raise HTTPException(status_code=500, detail="Database connection error")

  try:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
      cur.execute(
        "SELECT id, title, poster_url, duration, release_date, synopsis, director, genre, languages FROM films WHERE id = %(movie_id)s",
        {"movie_id": movie_id},
      )
      film = cur.fetchone()
      if not film:
        raise HTTPException(status_code=404, detail="Film not found")

      extra_showtime_filters = ""
      if subtitles_filter:
        extra_showtime_filters += " AND UPPER(COALESCE(s.diffusion_version, '')) = ANY(%(subtitles)s)"

      query = f"""
        SELECT
          c.id AS cinema_id,
          c.name,
          c.address,
          {cinema_lat_expr} AS lat,
          {cinema_lon_expr} AS lon,
          {dist_expr} AS distance_km,
          s.start_date,
          s.start_time,
          s.diffusion_version,
          s.format,
          s.reservation_url
        FROM showtimes s
        JOIN cinemas c ON c.id = s.cinema_id
        WHERE s.movie_id = %(movie_id)s
          AND {cinema_lat_expr} IS NOT NULL
          AND {cinema_lon_expr} IS NOT NULL
          AND s.start_date BETWEEN %(start_date)s AND %(end_date)s
          AND {dist_expr} <= %(radius_km)s
          {extra_showtime_filters}
        ORDER BY distance_km ASC, s.start_date ASC, s.start_time ASC;
        """

      params = {
        "movie_id": movie_id,
        "center_lat": req.lat,
        "center_lon": req.lon,
        "radius_km": radius,
        "start_date": start_date,
        "end_date": end_date,
      }
      if subtitles_filter:
        params["subtitles"] = subtitles_filter

      cur.execute(query, params)
      rows = cur.fetchall()
  finally:
    conn.close()

  cinemas = {}
  for row in rows:
    if subtitles_set:
      subtitle_value = (row.get("diffusion_version") or "").strip().upper()
      if subtitle_value not in subtitles_set:
        continue

    if filter_date:
      show_date = row.get("start_date")
      if isinstance(show_date, date):
        if show_date != filter_date:
          continue
      elif show_date != filter_date.isoformat():
        continue

    cinema_id = row["cinema_id"]
    cinema = cinemas.get(cinema_id)
    if not cinema:
      cinema = {
        "id": cinema_id,
        "name": row["name"],
        "address": row.get("address"),
        "lat": float(row["lat"]) if row.get("lat") is not None else None,
        "lon": float(row["lon"]) if row.get("lon") is not None else None,
        "distance_km": float(row["distance_km"]) if row.get("distance_km") is not None else None,
        "showtimes": [],
      }
      cinemas[cinema_id] = cinema

    cinema["showtimes"].append({
      "start_date": row["start_date"].isoformat() if isinstance(row["start_date"], date) else row["start_date"],
      "start_time": row["start_time"].isoformat() if hasattr(row["start_time"], "isoformat") else row["start_time"],
      "diffusion_version": row.get("diffusion_version"),
      "format": row.get("format"),
      "reservation_url": row.get("reservation_url"),
    })

  cinema_list = []
  for cinema in cinemas.values():
    if not cinema["showtimes"]:
      continue
    earliest_ts = None
    for show in cinema["showtimes"]:
      ts = showtime_timestamp(show.get("start_date"), show.get("start_time"))
      if ts is not None and (earliest_ts is None or ts < earliest_ts):
        earliest_ts = ts
    cinema["_meta"] = {"earliest_ts": earliest_ts}
    cinema_list.append(cinema)

  film_genres_list = split_to_list(film.get("genre"))
  film_languages_list = split_to_list(film.get("languages"))
  film_languages_lower = [lang.lower() for lang in film_languages_list]
  film_genres_lower = [genre.lower() for genre in film_genres_list]

  if duration_max is not None and isinstance(film.get("duration"), int) and film["duration"] > duration_max:
    cinema_list = []

  if languages_filter_set and film_languages_lower and not languages_filter_set.intersection(film_languages_lower):
    cinema_list = []

  if genres_filter_set and film_genres_lower and not genres_filter_set.intersection(film_genres_lower):
    cinema_list = []

  if sort_by == "distance":
    cinema_list.sort(key=lambda c: c.get("distance_km") if isinstance(c.get("distance_km"), (int, float)) else float("inf"))
  elif sort_by == "earliest_showtime":
    cinema_list.sort(key=lambda c: c.get("_meta", {}).get("earliest_ts") if c.get("_meta", {}).get("earliest_ts") is not None else float("inf"))

  for cinema in cinema_list:
    cinema.pop("_meta", None)

  return {
    "id": film["id"],
    "title": film["title"],
    "poster_url": film.get("poster_url"),
    "duration": film.get("duration"),
    "release_date": film.get("release_date"),
    "synopsis": film.get("synopsis"),
    "director": film.get("director"),
    "genre": film.get("genre"),
    "genres": film_genres_list,
    "languages": film_languages_list,
    "language": film_languages_list[0] if film_languages_list else None,
    "cinemas": cinema_list,
  }
