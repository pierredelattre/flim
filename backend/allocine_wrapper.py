from AllocineAPI.src.allocineAPI.allocineAPI import allocineAPI, URLs
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def get_movies_with_showtimes(cinemaId, date):
    api = allocineAPI()

    # 1. Films avec infos complètes
    movies = api.get_movies(cinemaId, date)

    # 2. Films avec horaires
    showtimes = api.get_showtime(cinemaId, date)

    # 3. Indexer les horaires par titre
    showtimes_by_title = {s["title"]: {"id_allocine": s.get("id_allocine") or s.get("internalId"), "showtimes": s.get("showtimes", [])} for s in showtimes}
    logger.debug(f"Showtimes by title and their id_allocine: { {k: v['id_allocine'] for k,v in showtimes_by_title.items()} }")

    # 4. Fusionner infos du film + horaires correspondants
    result = []
    for movie in movies:
        title = movie.get("title")
        movie_with_times = dict(movie)  # toutes les infos du film
        entry = showtimes_by_title.get(title, {})
        movie_with_times["showtimes"] = entry.get("showtimes", [])
        if not movie_with_times.get("id_allocine"):
          movie_with_times["id_allocine"] = entry.get("id_allocine") or movie_with_times.get("id_allocine")
        if not movie_with_times.get("isPremiere"):
          movie_with_times["isPremiere"] = entry.get("isPremiere", False)
        logger.debug(f"Movie '{title}': assigned id_allocine = {movie_with_times.get('id_allocine')}")
        result.append(movie_with_times)
    return result
