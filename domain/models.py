from typing import List, Optional

from pydantic import BaseModel, Field


class UserRegistration(BaseModel):
    user_id: str = Field(..., min_length=1)
    generos_favoritos: List[str] = Field(default_factory=list)
    artistas_favoritos: List[str] = Field(default_factory=list)
    idioma_preferido: str = "es"


class UserProfile(BaseModel):
    user_id: str = Field(..., min_length=1)
    is_new: bool = False
    initial_genres: Optional[List[str]] = Field(default_factory=list)
    initial_artists: Optional[List[str]] = Field(default_factory=list)


class Interaction(BaseModel):
    user_id: str = Field(..., min_length=1)
    track_id: str = Field(..., min_length=1)
    rating: int = Field(..., ge=1, le=5)
