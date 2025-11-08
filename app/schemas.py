from pydantic import BaseModel, Field, EmailStr
from typing import Any, Dict, List
from datetime import datetime


# --- Modelos de Evento ---

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


# --- Modelos de Autenticação ---

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    id_usuario: str | None = None


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)
    nome_completo: str


class UserInDB(BaseModel):
    id_usuario: str
    id_grupo: int
    email: EmailStr
    senha_hash: str
    nome_completo: str

    class Config:
        from_attributes = True


# --- Modelos de Gerenciamento de Perfil ---

class UserResponse(BaseModel):
    id_usuario: str
    email: EmailStr
    nome_completo: str
    id_grupo: int

    class Config:
        from_attributes = True


class UserUpdateProfile(BaseModel):
    nome_completo: str = Field(..., min_length=3)


class UserUpdatePassword(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8, max_length=72)

# --- NOVOS SCHEMAS (Recuperação de Senha e Busca de Admin) ---

class ForgotPasswordRequest(BaseModel):
    """Schema para a solicitação de recuperação de senha."""
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    """Schema para a efetivação da nova senha."""
    token: str
    new_password: str = Field(..., min_length=8, max_length=72)

class UserSearchResponse(BaseModel):
    """Schema para a resposta da busca de usuários pelo admin."""
    id_usuario: str
    email: EmailStr
    nome_completo: str

    class Config:
        from_attributes = True