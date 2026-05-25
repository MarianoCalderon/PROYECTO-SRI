from fastapi import APIRouter
from domain.models import UserProfile, Interaction, UserRegistration
from use_cases.recommender_logic import get_hybrid_recommendations
from infrastructure.db_clients import redis_client, neo4j_driver

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
        u.artistas_favoritos = $artistas
    """
    with neo4j_driver.session() as session:
        session.run(query, 
                    uid=user_data.user_id, 
                    idioma=user_data.idioma_preferido, 
                    generos=user_data.generos_favoritos,
                    artistas=user_data.artistas_favoritos)
    return {"status": "Usuario registrado exitosamente", "user_id": user_data.user_id}

@router.post("/recommendations/")
async def generate_recommendation(user: UserProfile):
    ultima_cancion = None if user.is_new else "5vjLSffimiOvm1VyEPNcXg"
    recs = get_hybrid_recommendations(
        user_id=user.user_id, 
        initial_genres=user.initial_genres, 
        initial_artists=user.initial_artists, # Se incluyen los artistas elegidos
        ultima_cancion_gustada_id=ultima_cancion
    )
    return {"type": "dynamic", "recommendations": recs}

@router.post("/interact/")
async def register_interaction(interaction: Interaction):
    redis_client.zincrby("ranking:popularidad", 1, interaction.track_id)
    datos_cancion = redis_client.hgetall(f"track:{interaction.track_id}")
    titulo = datos_cancion.get("titulo", "Canción Desconocida")
    artista = datos_cancion.get("artista", "Artista Anónimo")
    
    query = """
    MERGE (u:Usuario {id: $uid})
    MERGE (c:Cancion {id: $tid})
    SET c.titulo = $titulo, c.artista = $artista
    MERGE (u)-[:CALIFICO {valor: $rating}]->(c)
    """
    with neo4j_driver.session() as session:
        session.run(query, uid=interaction.user_id, tid=interaction.track_id, rating=interaction.rating, titulo=titulo, artista=artista)
    return {"status": "Interación registrada"}