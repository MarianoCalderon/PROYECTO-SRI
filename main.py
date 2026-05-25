from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.api_endpoints import router

app = FastAPI(title="Motor de Recomendación Musical")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/")
def read_root():
    return {"message": "API de Recomendación Activa. Visita /docs para pruebas de endpoints."}