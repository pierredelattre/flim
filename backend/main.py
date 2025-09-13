# Charger variables BDD
import psycopg2
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from math import radians, cos, sin, asin, sqrt
from fastapi import Body

load_dotenv()  # charge .env
print("DB URL:", os.getenv("DATABASE_URL"))

from fastapi import FastAPI

app = FastAPI()

# Autoriser le frontend Vue (en dev sur :5173)
app.add_middleware(
  CORSMiddleware,
  allow_origins=["http://localhost:5173"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
) 

# Classe pour récupérer lat/lon du client + rayon
class LocationRequest(BaseModel):
  lat: float
  lon: float
  radius_km: float = 20

def haversine(lat1, lon1, lat2, lon2):
  # Retourne la distance en km entre 2 points
  R = 6371  # rayon Terre en km
  dlat = radians(lat2 - lat1)
  dlon = radians(lon2 - lon1)
  a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
  c = 2*asin(sqrt(a))
  return R * c

@app.post("/api/cinemas_nearby")
def cinemas_nearby(req: LocationRequest):
  conn = psycopg2.connect(os.getenv("DATABASE_URL"))
  cursor = conn.cursor()
  cursor.execute("SELECT id_allocine, name, address, latitude, longitude FROM cinemas WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
  cinemas = cursor.fetchall()
  cursor.close()
  conn.close()

  # Filtrer par distance
  nearby = []
  for c in cinemas:
    dist = haversine(req.lat, req.lon, c[3], c[4])
    if dist <= req.radius_km:
      nearby.append({"id": c[0], "name": c[1], "address": c[2], "lat": c[3], "lon": c[4], "distance_km": dist})
  return {"success": True, "data": nearby}



# Nouvelle version movies_nearby: utilise seulement la BDD
@app.post("/api/movies_nearby")
def movies_nearby(req: LocationRequest = Body(...)):
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cursor = conn.cursor()
        # Récupérer les cinémas avec coordonnées, inclure id interne
    cursor.execute(
        "SELECT id, id_allocine, name, address, latitude, longitude FROM cinemas WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
    )
    cinemas = cursor.fetchall()
    # Calculer les cinémas proches
    nearby_cinemas = []

    today = datetime.today().date()
    movies_dict = {}

    for c in cinemas:
        dist = haversine(req.lat, req.lon, c[4], c[5])
        print("DEBUG position:", req.lat, req.lon, "rayon:", req.radius_km)
        if dist <= req.radius_km:
            nearby_cinemas.append({
                "id": c[0],
                "id_allocine": c[1],
                "name": c[2],
                "address": c[3],
                "lat": c[4],
                "lon": c[5],
                "distance_km": dist
            })
    if not nearby_cinemas:
        cursor.close()
        conn.close()
        return {"success": True, "data": []}

    # Obtenir la liste des id_allocine des cinémas proches
    cinema_ids = [c["id"] for c in nearby_cinemas]

    # Récupérer tous les showtimes pour ces cinémas (pour aujourd'hui)
    format_strings = ','.join(['%s'] * len(cinema_ids))
    query = f"""
        SELECT s.cinema_id, s.movie_id, f.id, s.start_date, s.start_time, s.diffusion_version, s.reservation_url, f.title, f.poster_url, f.duration, f.release_date, f.synopsis
        FROM showtimes s
        JOIN films f ON s.movie_id = f.id
        WHERE s.cinema_id IN ({format_strings})
        AND s.start_date = %s
    """
    params = cinema_ids + [today]
    cursor.execute(query, params)
    results = cursor.fetchall()
    print(results)
    # print("DEBUG results count:", len(results))

    # Construire un dict des cinémas par id pour accès rapide à leur info/distance
    cinema_dict = {c["id"]: c for c in nearby_cinemas}

    # Grouper les films
    for row in results:
        cinema_id, movie_id, film_id, start_date, start_time, diffusion_version, reservation_url, title, poster_url, duration, release_date, synopsis = row
        if title not in movies_dict:
            movies_dict[title] = {
                "id": film_id,
                "title": title,
                "poster": poster_url,
                "duration": duration,
                "release_date": release_date,
                "synopsis": synopsis,
                "cinemas": []
            }
        # Check if cinema already exists in the cinemas list for this movie
        cinema_info = next((c for c in movies_dict[title]["cinemas"] if c["id"] == cinema_id), None)
        if not cinema_info:
            cinema_info = {
                "id": cinema_id,
                "name": cinema_dict[cinema_id]["name"],
                "address": cinema_dict[cinema_id]["address"],
                "distance_km": cinema_dict[cinema_id]["distance_km"],
                "showtimes": []
            }
            movies_dict[title]["cinemas"].append(cinema_info)
        # Append the current showtime to the cinema's showtimes list
        cinema_info["showtimes"].append({
            "start_date": start_date,
            "start_time": start_time,
            "diffusion_version": diffusion_version,
            "reservation_url": reservation_url
        })
    cursor.close()
    conn.close()

    return {"success": True, "data": list(movies_dict.values())}

@app.post("/api/movie/{movie_id}")
def movie_details(movie_id: int, req: LocationRequest = Body(...)):
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cursor = conn.cursor()
    # Récupérer les détails du film
    cursor.execute(
        "SELECT title, poster_url, duration, release_date, synopsis, director FROM films WHERE id = %s",
        (movie_id,)
    )
    film = cursor.fetchone()
    if not film:
        cursor.close()
        conn.close()
        return {"success": False, "error": "Film not found"}

    title, poster_url, duration, release_date, synopsis, director = film

    today = datetime.today().date()
    end_date = today + timedelta(days=6)

    # Récupérer tous les showtimes du film avec infos cinéma
    cursor.execute(
        """
        SELECT c.id, c.name, c.address, c.latitude, c.longitude,
               s.start_date, s.start_time, s.diffusion_version, s.reservation_url
        FROM showtimes s
        JOIN cinemas c ON s.cinema_id = c.id
        WHERE s.movie_id = %s
        AND s.start_date BETWEEN %s AND %s
        ORDER BY c.name, s.start_date, s.start_time
        """,
        (movie_id, today, end_date)
    )
    rows = cursor.fetchall()

    cinemas_dict = {}
    for row in rows:
        cinema_id, name, address, latitude, longitude, start_date, start_time, diffusion_version, reservation_url = row
        dist = haversine(req.lat, req.lon, latitude, longitude)
        if dist <= req.radius_km:
            if cinema_id not in cinemas_dict:
                cinemas_dict[cinema_id] = {
                    "name": name,
                    "address": address,
                    "distance_km": dist,
                    "showtimes": []
                }
            cinemas_dict[cinema_id]["showtimes"].append({
                "start_date": start_date,
                "start_time": start_time,
                "diffusion_version": diffusion_version,
                "reservation_url": reservation_url
            })

    cursor.close()
    conn.close()

    # Return the film object directly, including the id
    return {
        "id": movie_id,
        "title": title,
        "poster_url": poster_url,
        "duration": duration,
        "release_date": release_date,
        "synopsis": synopsis,
        "director": director,
        "cinemas": list(cinemas_dict.values())
    }