import json
import time

import faiss
import numpy as np

from infrastructure.db_clients import FAISS_DIM, redis_client, neo4j_driver, save_faiss_assets
from infrastructure.key_utils import normalizar_clave

# Micro-catálogo de prueba para demos rápidas sin spotify_data.csv.
catalogo_canciones = [
    {"id": "t1", "titulo": "Do I Wanna Know?", "artista": "Arctic Monkeys", "genero": "rock", "pop": 85, "features": [0.71, 0.53, 0.18, 0.39, 0.85]},
    {"id": "t2", "titulo": "Cruel Summer", "artista": "Taylor Swift", "genero": "pop", "pop": 95, "features": [0.55, 0.70, 0.11, 0.56, 0.65]},
    {"id": "t3", "titulo": "R U Mine?", "artista": "Arctic Monkeys", "genero": "rock", "pop": 80, "features": [0.65, 0.85, 0.05, 0.45, 0.72]},
    {"id": "t4", "titulo": "Anti-Hero", "artista": "Taylor Swift", "genero": "pop", "pop": 90, "features": [0.63, 0.64, 0.13, 0.53, 0.68]},
    {"id": "t5", "titulo": "Take Five", "artista": "The Dave Brubeck Quartet", "genero": "jazz", "pop": 60, "features": [0.45, 0.25, 0.85, 0.60, 0.40]},
    {"id": "t6", "titulo": "505", "artista": "Arctic Monkeys", "genero": "rock", "pop": 86, "features": [0.52, 0.82, 0.04, 0.31, 0.70]},
]

interacciones = [
    {"user": "Carlos", "track": "t1", "rating": 5},
    {"user": "Carlos", "track": "t3", "rating": 5},
    {"user": "Mariana", "track": "t2", "rating": 5},
    {"user": "Mariana", "track": "t4", "rating": 4},
    {"user": "Julio", "track": "t1", "rating": 4},
    {"user": "Julio", "track": "t5", "rating": 5},
    {"user": "Ana", "track": "t1", "rating": 5},
    {"user": "Ana", "track": "t6", "rating": 5},
]


def cargar_datos() -> None:
    print("Iniciando pipeline ETL de prueba...")
    redis_client.flushdb()

    print("Cargando metadatos, rankings y FAISS...")
    track_ids = []
    vectores = []
    for cancion in catalogo_canciones:
        track_ids.append(cancion["id"])
        vectores.append(cancion["features"])
        redis_client.zadd("ranking:popularidad", {cancion["id"]: cancion["pop"]})
        redis_client.zadd(f"ranking:genero:{normalizar_clave(cancion['genero'])}", {cancion["id"]: cancion["pop"]})
        redis_client.zadd(f"ranking:artista:{normalizar_clave(cancion['artista'])}", {cancion["id"]: cancion["pop"]})
        redis_client.hset(
            f"track:{cancion['id']}",
            mapping={
                "titulo": cancion["titulo"],
                "artista": cancion["artista"],
                "genero": cancion["genero"],
                "popularidad": cancion["pop"],
                "features": json.dumps(cancion["features"]),
            },
        )

    redis_client.rpush("onboarding:genres", "rock", "pop", "jazz")
    redis_client.rpush("onboarding:artists", "Arctic Monkeys", "Taylor Swift", "The Dave Brubeck Quartet")

    matriz_vectores = np.array(vectores, dtype="float32")
    if matriz_vectores.shape[1] != FAISS_DIM:
        raise ValueError("Las dimensiones del micro-catálogo no coinciden con FAISS_DIM")
    index = faiss.IndexFlatL2(FAISS_DIM)
    index.add(matriz_vectores)
    save_faiss_assets(index, track_ids)

    print("Construyendo grafo en Neo4j...")
    canciones_por_id = {c["id"]: c for c in catalogo_canciones}
    interacciones_cypher = []
    now = int(time.time())
    for pos, inter in enumerate(interacciones):
        cancion = canciones_por_id[inter["track"]]
        interacciones_cypher.append(
            {
                **inter,
                "timestamp": now - pos,
                "titulo": cancion["titulo"],
                "artista": cancion["artista"],
                "genero": cancion["genero"],
            }
        )

    query_limpieza = "MATCH (n) DETACH DELETE n"
    query_nodos = """
    UNWIND $interacciones AS inter
    MERGE (u:Usuario {id: inter.user})
    SET u.idioma = 'es'
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
        session.run(query_nodos, interacciones=interacciones_cypher)

    print("¡Datos de prueba cargados exitosamente!")
    print(f"Total en FAISS: {index.ntotal} vectores.")


if __name__ == "__main__":
    cargar_datos()
