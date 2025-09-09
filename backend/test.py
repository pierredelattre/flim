from allocineAPI.allocineAPI import allocineAPI
api = allocineAPI()
data = api.get_movies("P0571", "2025-09-10")
print(data)