from pydantic import BaseModel, Field, EmailStr
from typing import Any, Dict
from datetime import datetime


# --- Modelos de Evento ---

class DetalhesFlexiveis(BaseModel):
    detalhes: Dict[str, Any] = Field(default_factory=dict)


class EventoBase(BaseModel):
    id_categoria: int
    titulo: str
    data_hora_inicio: datetime
    local_evento: str


class EventoCriacao(EventoBase):
    dados_mongo: Dict[str, Any]


class EventoResposta(EventoBase):
    id_evento: str
    nome_categoria: str
    detalhes_mongo: Dict[str, Any] | None = None

    class Config:
        from_attributes = True


# --- NOVOS Modelos de Autenticação ---

class Token(BaseModel):
    """Schema para a resposta do token de login."""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Schema para os dados dentro do token JWT."""
    id_usuario: str | None = None


class UserCreate(BaseModel):
    """Schema para a criação de um novo usuário."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)
    nome_completo: str


class UserInDB(BaseModel):
    """Schema para ler o usuário do banco (inclui hash)."""
    id_usuario: str
    id_grupo: int
    email: EmailStr
    senha_hash: str
    nome_completo: str

    class Config:
        from_attributes = True

