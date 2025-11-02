from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from . import schemas, crud
from .database import get_db_sql
from .config import SECRET_KEY, ALGORITHM

# Importa o Passlib para hashing de senha
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Isso diz ao FastAPI que a URL "/login" é a que gera o token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def verify_password(plain_password, hashed_password):
    """Verifica se a senha em texto plano bate com o hash salvo."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    """Gera um hash para a senha em texto plano."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """Cria um novo token de acesso JWT."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Usa o tempo padrão de 15 minutos se não for passado
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# --- A NOVA DEPENDÊNCIA DE AUTENTICAÇÃO ---
# Ela será usada em todos os endpoints protegidos
def get_current_user_id(
        token: str = Depends(oauth2_scheme),
        db: Session = Depends(get_db_sql)
) -> str:
    """
    Decodifica o token JWT para obter o ID do usuário.
    Levanta exceção 401 se o token for inválido.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Decodifica o token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Pega o ID do usuário de dentro do token
        id_usuario: str = payload.get("id_usuario")

        if id_usuario is None:
            raise credentials_exception

        token_data = schemas.TokenData(id_usuario=id_usuario)
    except JWTError:
        raise credentials_exception

    # (Opcional, mas recomendado) Verifica se o usuário ainda existe no banco
    user = crud.get_user_by_id(db, id_usuario=token_data.id_usuario)
    if user is None:
        raise credentials_exception

    return user.id_usuario
