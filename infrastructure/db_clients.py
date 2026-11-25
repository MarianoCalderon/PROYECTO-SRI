import json
import os
from pathlib import Path
from typing import List, Tuple

import faiss
import redis
from neo4j import GraphDatabase

# -----------------------------------------------------------------------------
# Configuración centralizada de infraestructura
# -----------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"

FAISS_DIM = int(os.getenv("FAISS_DIM", "5"))
FAISS_INDEX_PATH = DATA_DIR / "spotify_audio.index"
FAISS_TRACK_IDS_PATH = DATA_DIR / "spotify_track_ids.json"

REDIS_URL = os.getenv("REDIS_URL")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")

# Cliente Redis: usa REDIS_URL en la nube (Upstash/Redis Cloud) o host/port en local
if REDIS_URL:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
else:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        db=0,
        decode_responses=True,
    )

# Driver Neo4j para relaciones usuario-ítem y filtrado colaborativo
neo4j_driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASSWORD),
)


def _crear_indice_vacio() -> faiss.IndexFlatL2:
    return faiss.IndexFlatL2(FAISS_DIM)


def load_faiss_assets() -> Tuple[faiss.IndexFlatL2, List[str]]:
    if FAISS_INDEX_PATH.exists() and FAISS_TRACK_IDS_PATH.exists():
        index = faiss.read_index(str(FAISS_INDEX_PATH))
        with FAISS_TRACK_IDS_PATH.open("r", encoding="utf-8") as archivo:
            track_ids = json.load(archivo)

        if index.ntotal != len(track_ids):
            print(
                "Advertencia: FAISS y track_ids no tienen el mismo tamaño. "
                f"FAISS={index.ntotal}, track_ids={len(track_ids)}"
            )
        return index, track_ids

    print(
        "FAISS: no se encontró un índice persistido. Ejecuta "
        "`python seed_real_data.py` antes de iniciar la API para activar "
        "el filtrado por contenido."
    )
    return _crear_indice_vacio(), []


def save_faiss_assets(index: faiss.IndexFlatL2, track_ids: List[str]) -> None:
    if not DATA_DIR.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(FAISS_INDEX_PATH))
    with FAISS_TRACK_IDS_PATH.open("w", encoding="utf-8") as archivo:
        json.dump(track_ids, archivo, ensure_ascii=False)

    global faiss_index, faiss_track_ids
    faiss_index = index
    faiss_track_ids = list(track_ids)


def reload_faiss_assets() -> Tuple[faiss.IndexFlatL2, List[str]]:
    global faiss_index, faiss_track_ids
    faiss_index, faiss_track_ids = load_faiss_assets()
    return faiss_index, faiss_track_ids


faiss_index, faiss_track_ids = load_faiss_assets()
