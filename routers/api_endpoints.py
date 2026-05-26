import time

from fastapi import APIRouter

from domain.models import Interaction, UserProfile, UserRegistration
from infrastructure import db_clients
from infrastructure.db_clients import neo4j_driver, redis_client
from use_cases.recommender_logic import get_hybrid_recommendations

router = APIRouter()


@router.get("/onboarding-options/")
async def get_onboarding_data():
    genres = redis_client.lrange("onboarding:genres", 0, -1)
    artists = redis_client.lrange("onboarding:artists", 0, -1)
    return {"genres": genres, "artists": artists}


@router.post("/register/")
async def register_new_user(user_data: UserRegistration):
    query = """
    MERGE (u:Usuario {id: $uid})
    SET u.idioma = $idioma,
        u.generos_favoritos = $generos,
        u.artistas_favoritos = $artistas,
        u.created_at = coalesce(u.created_at, $timestamp)
    """
    with neo4j_driver.session() as session:
        session.run(
            query,
            uid=user_data.user_id,
            idioma=user_data.idioma_preferido,
            generos=user_data.generos_favoritos,
            artistas=user_data.artistas_favoritos,
            timestamp=int(time.time()),
        )
    return {"status": "Usuario registrado exitosamente", "user_id": user_data.user_id}


@router.post("/recommendations/")
async def generate_recommendation(user: UserProfile):
    # La versión anterior usaba una canción hardcodeada. Ahora la lógica revisa
    # el historial real del usuario en Neo4j y construye su perfil híbrido.
    recs = get_hybrid_recommendations(
        user_id=user.user_id,
        initial_genres=user.initial_genres,
        initial_artists=user.initial_artists,
    )
    return {"type": "dynamic", "recommendations": recs}


@router.post("/interact/")
async def register_interaction(interaction: Interaction):
    datos_cancion = redis_client.hgetall(f"track:{interaction.track_id}")
    titulo = datos_cancion.get("titulo", "Canción Desconocida")
    artista = datos_cancion.get("artista", "Artista Anónimo")
    genero = datos_cancion.get("genero", "General")

    # Likes suben ranking; dislikes/skip evitan repetir sin inflar popularidad.
    if interaction.rating >= 4:
        redis_client.zincrby("ranking:popularidad", 1, interaction.track_id)
        redis_client.set(f"user:{interaction.user_id}:last_like", interaction.track_id)
    elif interaction.rating <= 2:
        redis_client.zincrby("ranking:popularidad", -0.25, interaction.track_id)

    query = """
    MERGE (u:Usuario {id: $uid})
    MERGE (c:Cancion {id: $tid})
    SET c.titulo = $titulo,
        c.artista = $artista,
        c.genero = $genero
    MERGE (u)-[r:CALIFICO]->(c)
    SET r.valor = $rating,
        r.timestamp = $timestamp
    """
    with neo4j_driver.session() as session:
        session.run(
            query,
            uid=interaction.user_id,
            tid=interaction.track_id,
            rating=interaction.rating,
            titulo=titulo,
            artista=artista,
            genero=genero,
            timestamp=int(time.time()),
        )
    return {"status": "Interacción registrada", "rating": interaction.rating}


@router.get("/status/")
async def get_system_status():
    """Endpoint útil para la presentación: demuestra que los 3 motores están vivos."""
    with neo4j_driver.session() as session:
        conteos = session.run(
            """
            MATCH (u:Usuario)
            WITH count(u) AS usuarios
            OPTIONAL MATCH (c:Cancion)
            WITH usuarios, count(c) AS canciones_grafo
            OPTIONAL MATCH ()-[r:CALIFICO]->()
            RETURN usuarios, canciones_grafo, count(r) AS interacciones
            """
        ).single()

    return {
        "redis_tracks_ranked": redis_client.zcard("ranking:popularidad"),
        "faiss_vectors": db_clients.faiss_index.ntotal,
        "faiss_track_ids": len(db_clients.faiss_track_ids),
        "neo4j_users": conteos["usuarios"] if conteos else 0,
        "neo4j_songs": conteos["canciones_grafo"] if conteos else 0,
        "neo4j_interactions": conteos["interacciones"] if conteos else 0,
        "hybrid_components": ["cold_start", "content_faiss", "collaborative_neo4j", "ranking_boosting_redis", "white_box"],
    }
