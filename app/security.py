from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from pydantic import BaseModel
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone

from . import crud, schemas, database
from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


# --- Funções de Hashing ---

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


# --- Funções de Token JWT ---

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# --- NOVA FUNÇÃO DE TOKEN (Recuperação de Senha) ---

def create_password_reset_token(id_usuario: str) -> str:
    """Cria um token JWT de curta duração para redefinir a senha."""
    expires = timedelta(minutes=15)  # Token válido por 15 minutos
    to_encode = {
        "id_usuario": id_usuario,
        "sub": "password-reset"  # 'Subject' para diferenciar do token de acesso
    }
    return create_access_token(data=to_encode, expires_delta=expires)


# --- NOVA FUNÇÃO DE TOKEN (Decodificar Token de Recuperação) ---

def decode_password_reset_token(token: str) -> str:
    """Valida o token de redefinição de senha e retorna o ID do usuário."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        # Garante que o token é específico para reset de senha
        if payload.get("sub") != "password-reset":
            raise HTTPException(status_code=401, detail="Tipo de token inválido.")

        id_usuario = payload.get("id_usuario")
        if id_usuario is None:
            raise HTTPException(status_code=401, detail="Token inválido, ID de usuário ausente.")

        return id_usuario
    except JWTError:
        # Erro de expiração ou assinatura inválida
        raise HTTPException(status_code=401, detail="Token inválido ou expirado.")


# --- Dependências de Autenticação ---

class TokenData(BaseModel):
    id_usuario: str | None = None


def authenticate_user(db: Session, email: str, password: str) -> schemas.UserInDB | None:
    user = crud.get_user_by_email(db, email=email)
    if not user or not verify_password(password, user.senha_hash):
        return None
    return user


def get_current_active_user(
        db: Session = Depends(database.get_db_sql),
        token: str = Depends(oauth2_scheme)
) -> schemas.UserInDB:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        token_data = TokenData(id_usuario=payload.get("id_usuario"))
        if token_data.id_usuario is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = crud.get_user_by_id_in_db(db, id_usuario=token_data.id_usuario)
    if user is None:
        raise credentials_exception
    return user


def get_current_user_id(user: schemas.UserInDB = Depends(get_current_active_user)) -> str:
    return user.id_usuario


def get_admin_user(user: schemas.UserInDB = Depends(get_current_active_user)):
    if user.id_grupo != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: Requer privilégios de administrador."
        )
    return user