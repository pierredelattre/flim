from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware

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
def scrape(url: str = Form(...)):
    # Ici tu appelles ton vrai scraper (allocine, bs4, etc.)
    return {"results": [f"Scrapé : {url}"]}
