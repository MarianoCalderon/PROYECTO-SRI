from pydantic import BaseModel
from typing import List, Optional

class UserRegistration(BaseModel):
    user_id: str
    generos_favoritos: List[str]
    artistas_favoritos: List[str]
    idioma_preferido: str

class UserProfile(BaseModel):
    user_id: str
    is_new: bool
    initial_genres: Optional[List[str]] = []
    initial_artists: Optional[List[str]] = [] # Nuevo campo para artistas

class Interaction(BaseModel):
    user_id: str
    track_id: str
    rating: int