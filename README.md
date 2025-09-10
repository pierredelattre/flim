# flim
## Lancer front & back en même temps
make dev

## Lancer le back-end
uvicorn main:app --reload

## Lancer le front-end
npm run dev

### Listes des villes
ret = api.get_top_villes()

### Liste des films d'un cinéma
data = api.get_movies("P0571", "2025-09-10")

### Liste des départements
ret = api.get_departements()

### Liste des circuits
ret = api.get_circuit()

### liste des cinemas
cinemas = api.get_cinema("departement-83191")

### liste des seances
data = api.get_showtime("W2920", "2024-01-01")
