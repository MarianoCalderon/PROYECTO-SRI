import json
import time
from pathlib import Path

import faiss
import numpy as np
import pandas as pd

from infrastructure.db_clients import (
    FAISS_DIM,
    neo4j_driver,
    redis_client,
    save_faiss_assets,
)
from infrastructure.key_utils import normalizar_clave

ROOT_DIR = Path(__file__).resolve().parent
CSV_PATH = ROOT_DIR / "spotify_data.csv"
FEATURES = ["danceability", "energy", "acousticness", "valence", "tempo_norm"]


def _preparar_dataframe(n_muestra: int = 15000) -> pd.DataFrame:
    columnas_necesarias = [
        "track_id",
        "track_name",
        "artists",
        "track_genre",
        "popularity",
        "danceability",
        "energy",
        "acousticness",
        "valence",
        "tempo",
    ]

    df = pd.read_csv(CSV_PATH)
    df = df.dropna(subset=columnas_necesarias)
    df = df.drop_duplicates(subset="track_id")

    # Filtrar el género 'iranian' para evitar sesgos en el recomendador
    df = df[df["track_genre"] != "iranian"]

    if len(df) > n_muestra:
        # Misma idea del prototipo original: muestra reproducible de 15,000 canciones.
        df = df.sample(n=n_muestra, random_state=42)

    tempo_min = float(df["tempo"].min())
    tempo_max = float(df["tempo"].max())
    rango_tempo = max(tempo_max - tempo_min, 1e-9)
    df["tempo_norm"] = (df["tempo"] - tempo_min) / rango_tempo

    for col in FEATURES:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=FEATURES)

    return df.reset_index(drop=True)


def _reiniciar_redis() -> None:
    print("Reiniciando Redis...")
    redis_client.flushdb()


def _cargar_redis_y_faiss(df: pd.DataFrame) -> None:
    print("Cargando metadatos, rankings e índice FAISS...")

    vectores = []
    track_ids = []
    pipe = redis_client.pipeline()

    for _, row in df.iterrows():
        track_id = str(row["track_id"])
        titulo = str(row["track_name"])
        artista = str(row["artists"])
        genero = str(row["track_genre"])
        popularidad = float(row["popularity"])
        vector = [float(row[col]) for col in FEATURES]

        track_ids.append(track_id)
        vectores.append(vector)

        pipe.zadd("ranking:popularidad", {track_id: popularidad})
        pipe.zadd(f"ranking:genero:{normalizar_clave(genero)}", {track_id: popularidad})
        pipe.zadd(
            f"ranking:artista:{normalizar_clave(artista)}", {track_id: popularidad}
        )
        pipe.hset(
            f"track:{track_id}",
            mapping={
                "titulo": titulo,
                "artista": artista,
                "genero": genero,
                "popularidad": popularidad,
                "features": json.dumps(vector),
            },
        )

    pipe.execute()

    matriz_vectores = np.array(vectores, dtype="float32")
    if matriz_vectores.shape[1] != FAISS_DIM:
        raise ValueError(
            f"FAISS esperaba {FAISS_DIM} dimensiones y recibió {matriz_vectores.shape[1]}"
        )

    index = faiss.IndexFlatL2(FAISS_DIM)
    index.add(matriz_vectores)
    save_faiss_assets(index, track_ids)

    print(f"FAISS persistido con {index.ntotal} canciones.")


def _preparar_onboarding(df: pd.DataFrame) -> None:
    print("Preparando opciones dinámicas de onboarding...")
    # Se mantiene cercano al prototipo original de Mariano.
    top_genres = df["track_genre"].value_counts().head(30).index.astype(str).tolist()
    top_artists = df["artists"].value_counts().head(20).index.astype(str).tolist()

    redis_client.delete("onboarding:genres", "onboarding:artists")
    if top_genres:
        redis_client.rpush("onboarding:genres", *top_genres)
    if top_artists:
        redis_client.rpush("onboarding:artists", *top_artists)


def _crear_historial_base_estilo_original(df: pd.DataFrame) -> list[dict]:
    """
    Replica la idea del ZIP original: un historial pequeño, no un grafo artificial
    enorme. Esto deja claro el arranque en frío, pero permite que Neo4j no esté
    totalmente vacío al iniciar la demo.
    """
    top = df.sort_values("popularity", ascending=False).head(10).reset_index(drop=True)
    if len(top) < 2:
        raise ValueError(
            "El dataset necesita al menos dos canciones para crear el historial base."
        )

    t1 = top.iloc[0]
    t2 = top.iloc[1]
    now = int(time.time())

    return [
        {
            "user": "Usuario_Frecuente_1",
            "track": str(t1["track_id"]),
            "rating": 5,
            "timestamp": now - 3,
            "titulo": str(t1["track_name"]),
            "artista": str(t1["artists"]),
            "genero": str(t1["track_genre"]),
        },
        {
            "user": "Usuario_Frecuente_2",
            "track": str(t1["track_id"]),
            "rating": 5,
            "timestamp": now - 2,
            "titulo": str(t1["track_name"]),
            "artista": str(t1["artists"]),
            "genero": str(t1["track_genre"]),
        },
        {
            "user": "Usuario_Frecuente_2",
            "track": str(t2["track_id"]),
            "rating": 5,
            "timestamp": now - 1,
            "titulo": str(t2["track_name"]),
            "artista": str(t2["artists"]),
            "genero": str(t2["track_genre"]),
        },
    ]


def _cargar_neo4j(df: pd.DataFrame) -> None:
    print("Construyendo historial base en Neo4j al estilo original...")
    interacciones = _crear_historial_base_estilo_original(df)

    query_limpieza = "MATCH (n) DETACH DELETE n"
    query_constraints = [
        "CREATE CONSTRAINT usuario_id IF NOT EXISTS FOR (u:Usuario) REQUIRE u.id IS UNIQUE",
        "CREATE CONSTRAINT cancion_id IF NOT EXISTS FOR (c:Cancion) REQUIRE c.id IS UNIQUE",
    ]
    query_seed = """
    UNWIND $interacciones AS inter
    MERGE (u:Usuario {id: inter.user})
    SET u.idioma = 'es',
        u.generos_favoritos = coalesce(u.generos_favoritos, []),
        u.artistas_favoritos = coalesce(u.artistas_favoritos, [])
    MERGE (c:Cancion {id: inter.track})
    SET c.titulo = inter.titulo,
        c.artista = inter.artista,
        c.genero = inter.genero
    MERGE (u)-[r:CALIFICO]->(c)
    SET r.valor = inter.rating,
        r.timestamp = inter.timestamp
    """

    with neo4j_driver.session() as session:
        session.run(query_limpieza)
        for query in query_constraints:
            try:
                session.run(query)
            except Exception as exc:
                print(f"No se pudo crear una constraint opcional: {exc}")
        session.run(query_seed, interacciones=interacciones)

    print("Grafo base cargado: 2 usuarios frecuentes, 2 canciones y 3 relaciones.")


def cargar_dataset_real() -> None:
    print("1. Leyendo dataset real de Spotify...")
    if not CSV_PATH.exists():
        print("Error: No se encontró 'spotify_data.csv' en la raíz del proyecto.")
        return

    df = _preparar_dataframe()
    print(f"Dataset preparado: {len(df)} canciones únicas.")

    _reiniciar_redis()
    _cargar_redis_y_faiss(df)
    _preparar_onboarding(df)
    _cargar_neo4j(df)

    print("¡Éxito! Pipeline finalizado. El recomendador ya puede ejecutarse.")


if __name__ == "__main__":
    cargar_dataset_real()
