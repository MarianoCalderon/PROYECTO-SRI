import pandas as pd
import numpy as np
from infrastructure.db_clients import redis_client, neo4j_driver, faiss_index

def cargar_dataset_real():
    print("1. Leyendo Dataset (Muestra aleatoria de 15,000 canciones)...")
    try:
        # Extracción aleatoria para abarcar más variedad
        df = pd.read_csv('spotify_data.csv').dropna().sample(n=15000, random_state=42)
    except FileNotFoundError:
        print("Error: No se encontró 'spotify_data.csv'.")
        return

    features = ['danceability', 'energy', 'acousticness', 'valence', 'tempo']
    df['tempo'] = df['tempo'] / df['tempo'].max()
    
    print("2. Cargando canciones en FAISS y metadatos en Redis...")
    vectores = []
    
    for index, row in df.iterrows():
        track_id = str(row['track_id'])
        redis_client.zadd("ranking:popularidad", {track_id: int(row['popularity'])})
        redis_client.hset(f"track:{track_id}", mapping={
            "titulo": str(row['track_name']),
            "artista": str(row['artists']),
            "genero": str(row['track_genre'])
        })
        vectores.append([row[f] for f in features])
        
    matriz_vectores = np.array(vectores).astype('float32')
    faiss_index.add(matriz_vectores)
    
    print("3. Preparando opciones dinámicas para la UI...")
    top_genres = df['track_genre'].value_counts().head(15).index.tolist()
    top_artists = df['artists'].value_counts().head(20).index.tolist()
    
    redis_client.delete("onboarding:genres")
    redis_client.delete("onboarding:artists")
    if top_genres: redis_client.rpush("onboarding:genres", *top_genres)
    if top_artists: redis_client.rpush("onboarding:artists", *top_artists)

    print("4. Generando historial base en Neo4j...")
    query_limpieza = "MATCH (n) DETACH DELETE n"
    query_seed_grafo = """
    MERGE (u1:Usuario {id: 'Usuario_Frecuente_1'})
    MERGE (u2:Usuario {id: 'Usuario_Frecuente_2'})
    MERGE (c1:Cancion {id: $track_1}) SET c1.titulo = $titulo_1, c1.artista = $artista_1
    MERGE (c2:Cancion {id: $track_2}) SET c2.titulo = $titulo_2, c2.artista = $artista_2
    MERGE (u1)-[:CALIFICO {valor: 5}]->(c1)
    MERGE (u2)-[:CALIFICO {valor: 5}]->(c1)
    MERGE (u2)-[:CALIFICO {valor: 5}]->(c2)
    """
    
    with neo4j_driver.session() as session:
        session.run(query_limpieza)
        t1, nom1, art1 = str(df.iloc[0]['track_id']), str(df.iloc[0]['track_name']), str(df.iloc[0]['artists'])
        t2, nom2, art2 = str(df.iloc[1]['track_id']), str(df.iloc[1]['track_name']), str(df.iloc[1]['artists'])
        session.run(query_seed_grafo, track_1=t1, titulo_1=nom1, artista_1=art1, track_2=t2, titulo_2=nom2, artista_2=art2)

    print(f"¡Éxito! Pipeline finalizado. {faiss_index.ntotal} canciones cargadas.")

if __name__ == "__main__":
    cargar_dataset_real()