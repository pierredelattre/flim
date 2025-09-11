# Charger variables BDD
from dotenv import load_dotenv
from datetime import datetime
import os
load_dotenv()  # charge .env
print("DB URL:", os.getenv("DATABASE_URL"))
print("Allociné Key:", os.getenv("API_KEY_ALLOCINE"))

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
        print("Résultats trouvés:", data)
        return {"success": True, "data": data}
    except Exception as e:
        return {"success": False, "error": str(e)}
