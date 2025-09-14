# Géocodage des adresses  
import re
import psycopg2
import os
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from time import sleep
from allocineAPI.allocineAPI import allocineAPI
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

geolocator = Nominatim(user_agent="cinema_app")

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

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
    logger.info(f"👉 Tentative brute : {raw_address}, France")
    location = geolocator.geocode(f"{raw_address}, France", timeout=10)
    if location:
      return location.latitude, location.longitude, "raw"
  except Exception as e:
    logger.error(f"❌ Erreur brute : {e}")

  # --- tentative 2 : adresse simplifiée
  try:
    clean_addr = clean_address(cinema_name, raw_address)
    logger.info(f"👉 Tentative simplifiée : {clean_addr}")
    location = geolocator.geocode(clean_addr, timeout=10)
    if location:
      return location.latitude, location.longitude, "clean"
  except Exception as e:
    logger.error(f"❌ Erreur simplifiée : {e}")

  # --- tentative 3 : code postal + ville seulement
  try:
    match = re.search(r"\b\d{5}\b", raw_address)
    if match:
      zipcode = match.group()
      city_part = raw_address.split(zipcode)[-1].strip()
      simple_addr = f"{zipcode} {city_part}, France"
      logger.info(f"👉 Tentative fallback : {simple_addr}")
      location = geolocator.geocode(simple_addr, timeout=10)
      if location:
          return location.latitude, location.longitude, "city_only"
  except Exception as e:
    logger.error(f"❌ Erreur fallback : {e}")

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
      logger.info(f"👉 Tentative fallback ville seule : {city_only_addr}")
      location = geolocator.geocode(city_only_addr, timeout=10)
      if location:
        return location.latitude, location.longitude, "city_only_name"
  except Exception as e:
    logger.error(f"❌ Erreur fallback ville seule : {e}")

  return None, None, "failed"

def insert_cinema(cursor, conn, cinema_id, name, address, latitude, longitude, precision):
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

def process_cinema(cinema, conn_lock, conn_params):
    # Each thread creates its own connection and cursor
    conn = psycopg2.connect(**conn_params)
    cursor = conn.cursor()
    lat, lon, precision = geocode_address(cinema["name"], cinema["address"])
    if lat and lon:
        logger.info(f"✅ {cinema['name']} -> {lat}, {lon} ({precision})")
        with conn_lock:
            insert_cinema(cursor, conn, cinema["id"], cinema["name"], cinema["address"], lat, lon, precision)
            logger.info(f"➡️ {cinema['name']} inséré en BDD avec : {precision}")
    else:
        logger.error(f"⚠️ Échec géocodage pour {cinema['name']}")
    cursor.close()
    conn.close()
    sleep(1)  # limite Nominatim

def main():
    api = allocineAPI()
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    conn_params = {"dsn": database_url} if database_url else {}
    departements = api.get_departements()
    conn_lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for dept in departements:
            cinemas_list = api.get_cinema(dept["id"])
            for c in cinemas_list:
                futures.append(executor.submit(process_cinema, c, conn_lock, conn_params))
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Erreur dans le thread: {e}")

if __name__ == "__main__":
    main()