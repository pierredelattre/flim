# import sys
# import os

# sys.path.append(os.path.dirname(__file__))  # ajoute le dossier actuel au path
# # from allocine_wrapper import get_movies_with_showtimes

# # from allocineAPI.allocineAPI import allocineAPI
# # api = allocineAPI()
# # data = get_movies_with_showtimes("P0571", "2025-09-10")

# # print(data)

# from allocineAPI.allocineAPI import allocineAPI
# api = allocineAPI()
# # data = api.get_showtime("P0086", "2025-09-10")
# data = api.get_cinema("departement-83158")
# print(data)
# print(api.get_departements())  # liste des départements

import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
print(os.getenv("DATABASE_URL"))  # vérifier que c'est bien chargé

try:
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    print("Connexion OK !")
except Exception as e:
    print("Erreur connexion:", e)