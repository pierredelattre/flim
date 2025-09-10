# import sys
# import os

# sys.path.append(os.path.dirname(__file__))  # ajoute le dossier actuel au path
# from allocine_wrapper import get_movies_with_showtimes

# from allocineAPI.allocineAPI import allocineAPI
# api = allocineAPI()
# data = get_movies_with_showtimes("P0571", "2025-09-10")

# print(data)

from allocineAPI.allocineAPI import allocineAPI
api = allocineAPI()
data = api.get_showtime("P0086", "2025-09-10")
print(data)