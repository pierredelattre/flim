# Charger variables BDD
import psycopg2
import os
from dotenv import load_dotenv
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from math import radians, cos, sin, asin, sqrt
from fastapi import Body

load_dotenv()  # charge .env
print("DB URL:", os.getenv("DATABASE_URL"))

from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
from allocineAPI.allocineAPI import allocineAPI
from allocine_wrapper import get_movies_with_showtimes

app = FastAPI()

# Autoriser le frontend Vue (en dev sur :5173)
app.add_middleware(
  CORSMiddleware,
  allow_origins=["http://localhost:5173"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
) 

@app.post("/scrape")
def scrape(departement_id: str = Form(...)):
  api = allocineAPI() 
  try:
    data = get_movies_with_showtimes(departement_id, datetime.today().strftime('%Y-%m-%d'))
    # print("Résultats trouvés:", data)
    return {"success": True, "data": data}
  except Exception as e:
    return {"success": False, "error": str(e)}

# Classe pour récupérer lat/lon du client + rayon
class LocationRequest(BaseModel):
  lat: float
  lon: float
  radius_km: float = 5

def haversine(lat1, lon1, lat2, lon2):
  # Retourne la distance en km entre 2 points
  R = 6371  # rayon Terre en km
  dlat = radians(lat2 - lat1)
  dlon = radians(lon2 - lon1)
  a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
  c = 2*asin(sqrt(a))
  return R * c

@app.post("/cinemas_nearby")
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


@app.post("/movies_nearby")
def movies_nearby(req: LocationRequest = Body(...)):
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id_allocine, name, address, latitude, longitude FROM cinemas WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
    )
    cinemas = cursor.fetchall()
    cursor.close()
    conn.close()

    today = datetime.today().strftime('%Y-%m-%d')
    movies_dict = {}

    for c in cinemas:
        dist = haversine(req.lat, req.lon, c[3], c[4])
        if dist <= req.radius_km:
            try:
                movies = get_movies_with_showtimes(c[0], today)
            except Exception as e:
                print(f"❌ Erreur films pour {c[1]} ({c[0]}): {e}")
                movies = []

            for m in movies:
                title = m["title"]
                if title not in movies_dict:
                    movies_dict[title] = {
                        "title": title,
                        "poster": m.get("urlPoster"),
                        "cinemas": []
                    }
                movies_dict[title]["cinemas"].append({
                    "id": c[0],
                    "name": c[1],
                    "address": c[2],
                    "distance_km": dist,
                    "showtimes": m["showtimes"]
                })

    return {"success": True, "data": list(movies_dict.values())}