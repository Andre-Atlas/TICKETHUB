from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from pydantic import BaseModel
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone

from . import crud, schemas, database
from .config import settings  # Importa as configurações

# --- Configuração de Hashing de Senha (Passlib) ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Configuração do OAuth2 (FastAPI) ---
# Diz ao FastAPI para procurar o token na URL "/login"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


# --- Funções de Hashing ---

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha em texto plano corresponde ao hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Gera um hash para a senha em texto plano."""
    return pwd_context.hash(password)


# --- Funções de Token JWT ---

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """Cria um novo token JWT."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Usa o tempo de expiração das configurações
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt


# --- Dependência de Autenticação ---

class TokenData(BaseModel):
    """Modelo Pydantic para os dados dentro do token."""
    id_usuario: str | None = None


def authenticate_user(db: Session, email: str, password: str) -> schemas.UserInDB | None:
    """Verifica se um usuário existe e se a senha está correta."""
    user = crud.get_user_by_email(db, email=email)
    if not user:
        return None
    if not verify_password(password, user.senha_hash):
        return None
    return user


def get_current_user_id(
        db: Session = Depends(database.get_db_sql),
        token: str = Depends(oauth2_scheme)
) -> str:
    """
    Dependência principal: decodifica o token, valida o usuário
    e retorna o ID do usuário.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        # Pega o 'id_usuario' de dentro do token
        token_data = TokenData(id_usuario=payload.get("id_usuario"))
        if token_data.id_usuario is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    # --- LINHA CORRIGIDA ---
    # Chamando a função com o nome correto: 'get_user_by_id_in_db'
    user = crud.get_user_by_id_in_db(db, id_usuario=token_data.id_usuario)

    if user is None:
        raise credentials_exception

    # Retorna o ID do usuário para os endpoints usarem
    return user.id_usuario