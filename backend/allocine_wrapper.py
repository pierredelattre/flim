from allocineAPI.allocineAPI import allocineAPI

def get_movies_with_showtimes(cinemaId, date):
    api = allocineAPI()

    # 1. Films avec infos complètes
    movies = api.get_movies(cinemaId, date)

    # 2. Films avec horaires
    showtimes = api.get_showtime(cinemaId, date)

    # 3. Indexer les horaires par titre
    showtimes_by_title = {s["title"]: s.get("showtimes", []) for s in showtimes}

    # 4. Fusionner infos du film + horaires correspondants
    result = []
    for movie in movies:
        title = movie.get("title")
        movie_with_times = dict(movie)  # toutes les infos du film
        movie_with_times["showtimes"] = showtimes_by_title.get(title, [])
        result.append(movie_with_times)

    return result