from infrastructure.db_clients import redis_client, neo4j_driver, faiss_index
import numpy as np

def obtener_metadatos(track_ids):
    resultados = []
    for tid in track_ids:
        datos = redis_client.hgetall(f"track:{tid}")
        if datos:
            resultados.append({
                "track_id": tid, 
                "titulo": datos.get("titulo", "Canción Desconocida"), 
                "artista": datos.get("artista", "Artista Anónimo"),
                "genero": datos.get("genero", "General")
            })
    return resultados

def get_hybrid_recommendations(user_id: str, initial_genres: list = [], initial_artists: list = [], ultima_cancion_gustada_id: str = None):
    # 1. Filtro de exclusión de canciones ya interactuadas
    canciones_excluidas = set()
    query_historial = """
    MATCH (u:Usuario {id: $uid})-[:CALIFICO]->(c:Cancion)
    RETURN c.id AS track_id
    """
    with neo4j_driver.session() as session:
        result_historial = session.run(query_historial, uid=user_id)
        canciones_excluidas = {record["track_id"] for record in result_historial}
    
    top_global = redis_client.zrevrange("ranking:popularidad", 0, 100, withscores=True)
    recomendaciones_finales = []

    # 2. Inicio en Frío (Género + Artista excluyendo las ya escuchadas)
    if not ultima_cancion_gustada_id and (initial_genres or initial_artists):
        ids_candidatos = [t[0] for t in top_global]
        tracks_candidatos = obtener_metadatos(ids_candidatos)
        
        for t in tracks_candidatos:
            if t["track_id"] not in canciones_excluidas:
                match_artista = t["artista"].lower() in [a.lower() for a in initial_artists]
                match_genero = t["genero"].lower() in [g.lower() for g in initial_genres]
                
                if match_artista or match_genero:
                    if match_artista:
                        t["reason"] = f"🌟 Favorito: Canción de tu artista predilecto ({t['artista']})."
                    else:
                        t["reason"] = f"❄️ Inicio en Frío: Basado en tu gusto por el género {t['genero']}."
                    recomendaciones_finales.append(t)
                    
            if len(recomendaciones_finales) >= 5:
                break
        if recomendaciones_finales:
            return recomendaciones_finales

    # 3. Relleno puro si no especificó datos
    if not ultima_cancion_gustada_id:
        ids_candidatos = [t[0] for t in top_global]
        tracks_candidatos = obtener_metadatos(ids_candidatos)
        for t in tracks_candidatos:
            if t["track_id"] not in canciones_excluidas:
                t["reason"] = "🔥 Tendencia: Canción con alta popularidad global."
                recomendaciones_finales.append(t)
            if len(recomendaciones_finales) >= 5:
                break
        return recomendaciones_finales[:5]

    # 4. Modelo Híbrido (Exclusión nativa en Cypher)
    query_collab = """
    MATCH (u:Usuario {id: $uid})-[:CALIFICO]->(c:Cancion)<-[:CALIFICO]-(otro:Usuario)-[:CALIFICO]->(rec:Cancion)
    WHERE NOT (u)-[:CALIFICO]->(rec)
    RETURN rec.id AS track_id, COUNT(otro) AS score
    ORDER BY score DESC LIMIT 5
    """
    collab_recs = []
    with neo4j_driver.session() as session:
        result_collab = session.run(query_collab, uid=user_id)
        collab_recs = [record["track_id"] for record in result_collab]

    vector_busqueda = np.random.random((1, 5)).astype('float32') 
    distancias, indices = faiss_index.search(vector_busqueda, 10)

    for tid in collab_recs:
        if tid not in canciones_excluidas:
            meta = obtener_metadatos([tid])
            if meta:
                track_meta = meta[0]
                track_meta["reason"] = "👥 Caja Blanca: Recomendado porque a usuarios con tus mismos gustos también les gustó."
                recomendaciones_finales.append(track_meta)

    if len(recomendaciones_finales) < 5:
        ids_relleno = [t[0] for t in top_global]
        tracks_relleno = obtener_metadatos(ids_relleno)
        for t in tracks_relleno:
            if t["track_id"] not in canciones_excluidas and t["track_id"] not in [r["track_id"] for r in recomendaciones_finales]:
                t["reason"] = "📈 Boosting: Canción sugerida por su alto rendimiento en la plataforma."
                recomendaciones_finales.append(t)
            if len(recomendaciones_finales) >= 5:
                break

    return recomendaciones_finales[:5]