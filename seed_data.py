import numpy as np
from infrastructure.db_clients import redis_client, neo4j_driver, faiss_index

# 1. Micro-Catálogo de prueba (Simulando un DataFrame de Pandas/CSV)
# Características de audio para FAISS: [tempo, bailabilidad, energia, acusticidad, valencia]
catalogo_canciones = [
    {"id": "t1", "titulo": "Do I Wanna Know?", "artista": "Arctic Monkeys", "pop": 85, "features": [0.85, 0.71, 0.53, 0.18, 0.39]},
    {"id": "t2", "titulo": "Cruel Summer", "artista": "Taylor Swift", "pop": 95, "features": [1.15, 0.55, 0.70, 0.11, 0.56]},
    {"id": "t3", "titulo": "R U Mine?", "artista": "Arctic Monkeys", "pop": 80, "features": [0.96, 0.65, 0.85, 0.05, 0.45]},
    {"id": "t4", "titulo": "Anti-Hero", "artista": "Taylor Swift", "pop": 90, "features": [0.97, 0.63, 0.64, 0.13, 0.53]},
    {"id": "t5", "titulo": "Take Five", "artista": "The Dave Brubeck Quartet", "pop": 60, "features": [0.80, 0.45, 0.25, 0.85, 0.60]}
]

# 2. Interacciones de prueba (Simulando historial de usuarios)
interacciones = [
    {"user": "Carlos", "track": "t1", "rating": 5},
    {"user": "Carlos", "track": "t3", "rating": 5},
    {"user": "Mariana", "track": "t2", "rating": 5},
    {"user": "Mariana", "track": "t4", "rating": 4},
    {"user": "Julio", "track": "t1", "rating": 4}, # Julio conecta los gustos de Carlos...
    {"user": "Julio", "track": "t5", "rating": 5}  # ...con el Jazz
]

def cargar_datos():
    print("Iniciando Pipeline ETL...")

    # --- A. Cargar en Redis (Ranking) ---
    print("Cargando popularidad en Redis...")
    for cancion in catalogo_canciones:
        redis_client.zadd("ranking:popularidad", {cancion["id"]: cancion["pop"]})

    # --- B. Cargar en FAISS (Contenido / Audio Features) ---
    print("Vectorizando audio en FAISS...")
    # Convertimos la lista de features a una matriz de Numpy (float32 es requerido por FAISS)
    matriz_vectores = np.array([c["features"] for c in catalogo_canciones]).astype('float32')
    faiss_index.add(matriz_vectores)

    # --- C. Cargar en Neo4j (Colaborativo / Grafo) ---
    print("Construyendo el Grafo en Neo4j...")
    query_limpieza = "MATCH (n) DETACH DELETE n" # Limpia la BD antes de insertar
    
    query_nodos = """
    UNWIND $interacciones AS inter
    MERGE (u:Usuario {id: inter.user})
    MERGE (c:Cancion {id: inter.track})
    MERGE (u)-[:CALIFICO {valor: inter.rating}]->(c)
    """
    
    with neo4j_driver.session() as session:
        session.run(query_limpieza)
        session.run(query_nodos, interacciones=interacciones)

    print("¡Datos cargados exitosamente!")
    print(f"Total en FAISS: {faiss_index.ntotal} vectores.")

if __name__ == "__main__":
    cargar_datos()