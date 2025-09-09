from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
from allocineAPI.allocineAPI import allocineAPI

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
        data = api.get_movies(departement_id, "2025-09-10")
        return {"success": True, "data": data}
    except Exception as e:
        return {"success": False, "error": str(e)}
