# Géocodage des adresses  
import re
import psycopg2
import os
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from time import sleep
from allocineAPI.allocineAPI import allocineAPI

geolocator = Nominatim(user_agent="cinema_app")

def clean_address(cinema_name, raw_address):
    # Récupère le code postal (5 chiffres)
    match = re.search(r"\b\d{5}\b", raw_address)
    if not match:
        return f"{cinema_name}, France"
    
    zipcode = match.group()
    # Tout ce qui vient après le code postal (ville)
    city_part = raw_address.split(zipcode)[-1].strip()
    # Reconstruit une adresse simplifiée : "Nom cinéma + code postal + ville"
    return f"{cinema_name} {zipcode} {city_part}, France"


def geocode_address(cinema_name, raw_address):
  # --- tentative 1 : adresse brute
  try:
    print("---")
    print(f"👉 Tentative brute : {raw_address}, France")
    location = geolocator.geocode(f"{raw_address}, France", timeout=10)
    if location:
      return location.latitude, location.longitude, "raw"
  except Exception as e:
    print(f"❌ Erreur brute : {e}")

  # --- tentative 2 : adresse simplifiée
  try:
    clean_addr = clean_address(cinema_name, raw_address)
    print(f"👉 Tentative simplifiée : {clean_addr}")
    location = geolocator.geocode(clean_addr, timeout=10)
    if location:
      return location.latitude, location.longitude, "clean"
  except Exception as e:
    print(f"❌ Erreur simplifiée : {e}")

  # --- tentative 3 : code postal + ville seulement
  try:
    match = re.search(r"\b\d{5}\b", raw_address)
    if match:
      zipcode = match.group()
      city_part = raw_address.split(zipcode)[-1].strip()
      simple_addr = f"{zipcode} {city_part}, France"
      print(f"👉 Tentative fallback : {simple_addr}")
      location = geolocator.geocode(simple_addr, timeout=10)
      if location:
          return location.latitude, location.longitude, "city_only"
  except Exception as e:
    print(f"❌ Erreur fallback : {e}")

  # --- tentative 4 : ville seule
  try:
    # Extraire la ville (tout ce qui suit le dernier code postal ou dernier chiffre 5)
    city = None
    match = re.search(r"\b\d{5}\b", raw_address)
    if match:
      city = raw_address.split(match.group())[-1].strip()
    else:
      # fallback si pas de CP : tout sauf les chiffres
      city = re.sub(r'\d', '', raw_address).strip()

    if city:
      city_only_addr = f"{city}, France"
      print(f"👉 Tentative fallback ville seule : {city_only_addr}")
      location = geolocator.geocode(city_only_addr, timeout=10)
      if location:
        return location.latitude, location.longitude, "city_only_name"
  except Exception as e:
    print(f"❌ Erreur fallback ville seule : {e}")

  return None, None, "failed"

api = allocineAPI()
load_dotenv()
conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cursor = conn.cursor()

def insert_cinema(cinema_id, name, address, latitude, longitude, precision):
  query = """
  INSERT INTO cinemas (id_allocine, name, address, latitude, longitude, geocode_precision)
  VALUES (%s, %s, %s, %s, %s, %s)
  ON CONFLICT (id_allocine) DO UPDATE
  SET name = EXCLUDED.name,
      address = EXCLUDED.address,
      latitude = EXCLUDED.latitude,
      longitude = EXCLUDED.longitude,
      geocode_precision = EXCLUDED.geocode_precision;
  """
  cursor.execute(query, (cinema_id, name, address, latitude, longitude, precision))
  conn.commit()


# Récupérer la liste des départements et leurs cinémas
departements = api.get_departements()

for dept in departements:
    cinemas_list = api.get_cinema(dept["id"])
    for idx, c in enumerate(cinemas_list, start=1):
        lat, lon, precision = geocode_address(c["name"], c["address"])
        if lat and lon:
            print(f"✅ {c['name']} -> {lat}, {lon} ({precision})")
            insert_cinema(c["id"], c["name"], c["address"], lat, lon, precision)
            print(f"➡️ {c['name']} inséré en BDD avec : {precision}")
        else:
            print(f"⚠️ Échec géocodage pour {c['name']}")
        sleep(1)  # limite Nominatim