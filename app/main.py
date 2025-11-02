from fastapi import FastAPI, Depends, HTTPException, Header, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pymongo.collection import Collection
from redis import Redis
import json
from datetime import timedelta

from . import crud, schemas, security
from .database import get_db_sql, get_db_mongo_collection, get_db_redis
from .config import ACCESS_TOKEN_EXPIRE_MINUTES
from typing import List, Annotated

app = FastAPI(title="TicketHub API")


# --- ENDPOINTS DE AUTENTICAÇÃO ---

@app.post("/register", summary="Registra um novo usuário")
def api_register_user(
        user: schemas.UserCreate,
        db_sql: Session = Depends(get_db_sql)
):
    """
    Cria uma nova conta de usuário.
    """
    db_user = crud.get_user_by_email(db_sql, email=user.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já registrado."
        )

    crud.create_user(db_sql, user)
    return {"message": f"Usuário {user.email} registrado com sucesso."}


@app.post("/login", response_model=schemas.Token, summary="Faz o login para obter um token de acesso")
def api_login_for_access_token(
        form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
        db_sql: Session = Depends(get_db_sql)
):
    """
    Endpoint de login. Recebe 'username' (email) e 'password' de um formulário.
    """
    user = crud.get_user_by_email(db_sql, email=form_data.username)

    # Verifica se o usuário existe e se a senha está correta
    if not user or not security.verify_password(form_data.password, user.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Cria o token JWT
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"id_usuario": user.id_usuario},
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


# --- ENDPOINTS DE EVENTOS (PROTEGIDOS) ---

@app.post("/eventos/", status_code=201, summary="Cria um novo evento (protegido)")
def api_criar_evento(
        evento: schemas.EventoCriacao,
        db_sql: Session = Depends(get_db_sql),
        db_mongo: Collection = Depends(get_db_mongo_collection),
        db_redis: Redis = Depends(get_db_redis),
        id_usuario: str = Depends(security.get_current_user_id)
):
    try:
        crud.criar_evento_completo(db_sql, db_mongo, evento, id_usuario)
        cache_key = f"agenda:{id_usuario}"
        db_redis.delete(cache_key)
        return {"message": "Evento criado com sucesso e cache invalidado."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ocorreu um erro ao criar: {e}")


@app.get("/agenda/", response_model=List[schemas.EventoResposta], summary="Obtém a agenda do usuário (protegido)")
def api_obter_agenda(
        db_sql: Session = Depends(get_db_sql),
        db_mongo: Collection = Depends(get_db_mongo_collection),
        db_redis: Redis = Depends(get_db_redis),
        id_usuario: str = Depends(security.get_current_user_id)
):
    cache_key = f"agenda:{id_usuario}"
    try:
        cached_agenda = db_redis.get(cache_key)
        if cached_agenda:
            print("LOG: CACHE HIT!")
            return json.loads(cached_agenda)
    except Exception as e:
        print(f"AVISO: Falha ao ler cache do Redis. {e}")

    print("LOG: CACHE MISS!")
    agenda = crud.obter_agenda_do_banco(db_sql, db_mongo, id_usuario)

    try:
        agenda_json = json.dumps(agenda, default=str)
        db_redis.set(cache_key, agenda_json, ex=3600)
    except Exception as e:
        print(f"AVISO: Falha ao salvar cache no Redis. {e}")

    return agenda


@app.delete("/eventos/{id_evento}", status_code=status.HTTP_204_NO_CONTENT, summary="Deleta um evento (protegido)")
def api_deletar_evento(
        id_evento: str,
        db_sql: Session = Depends(get_db_sql),
        db_mongo: Collection = Depends(get_db_mongo_collection),
        db_redis: Redis = Depends(get_db_redis),
        id_usuario: str = Depends(security.get_current_user_id)
):
    try:
        sucesso = crud.deletar_evento_completo(db_sql, db_mongo, id_evento, id_usuario)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ocorreu um erro ao deletar: {e}"
        )

    if not sucesso:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento não encontrado ou não pertence ao usuário."
        )

    try:
        cache_key = f"agenda:{id_usuario}"
        db_redis.delete(cache_key)
    except Exception as e:
        print(f"AVISO: Evento deletado com sucesso, mas falha ao limpar o cache: {e}")

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.put("/eventos/{id_evento}", summary="Atualiza um evento existente (protegido)")
def api_atualizar_evento(
        id_evento: str,
        evento_data: schemas.EventoCriacao,
        db_sql: Session = Depends(get_db_sql),
        db_mongo: Collection = Depends(get_db_mongo_collection),
        db_redis: Redis = Depends(get_db_redis),
        id_usuario: str = Depends(security.get_current_user_id)
):
    try:
        sucesso = crud.atualizar_evento_completo(
            db_sql, db_mongo, id_evento, id_usuario, evento_data
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ocorreu um erro ao atualizar: {e}"
        )

    if not sucesso:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento não encontrado ou não pertence ao usuário."
        )

    try:
        cache_key = f"agenda:{id_usuario}"
        db_redis.delete(cache_key)
    except Exception as e:
        print(f"AVISO: Evento atualizado com sucesso, mas falha ao limpar o cache: {e}")

    return {"message": "Evento atualizado com sucesso e cache invalidado."}