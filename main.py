from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from routers.api_endpoints import router

app = FastAPI(
    title="Motor de Recomendación Musical",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

@app.get("/api")
def read_root():
    return {"message": "API de Recomendación Activa. Visita /api/docs para pruebas de endpoints."}

# Sirve index.html, style.css y worker.js en la ruta principal (debe ir siempre al final)
frontend_dir = Path(__file__).resolve().parent / "frontend"
app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
