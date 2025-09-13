from allocineAPI.allocineAPI import allocineAPI

def get_movies_with_showtimes(cinemaId, date):
    api = allocineAPI()

    # 1. Films avec infos complètes
    movies = api.get_movies(cinemaId, date)

    # 2. Films avec horaires
    showtimes = api.get_showtime(cinemaId, date)

    # 3. Indexer les horaires par titre
    showtimes_by_title = {}
    for s in showtimes:
        showtimes_by_title[s["title"]] = {
            "id_allocine": (
                s.get("id_allocine")
                or s.get("internalId")
                or s.get("id")
                or s.get("code")
            ),
            "showtimes": s.get("showtimes", [])
        }

    # 4. Fusionner infos du film + horaires correspondants
    result = []
    for movie in movies:
        title = movie.get("title")
        movie_with_times = dict(movie)  # toutes les infos du film
        entry = showtimes_by_title.get(title, {})

        movie_with_times["showtimes"] = entry.get("showtimes", [])
        movie_with_times["id_allocine"] = (
            movie.get("id_allocine")
            or entry.get("id_allocine")
            or movie.get("internalId")
            or movie.get("code")
        )
        movie_with_times["isPremiere"] = (
            movie.get("isPremiere") or entry.get("isPremiere", False)
        )
        result.append(movie_with_times)

    return result