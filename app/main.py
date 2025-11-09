from fastapi import FastAPI, Depends, HTTPException, Response, status, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pymongo.collection import Collection
from redis import Redis
import json
from . import crud, schemas, security
from .database import get_db_sql, get_db_mongo_collection, get_db_redis
from typing import List

app = FastAPI(
    title="TicketHub API",
    description="API para gerenciar ingressos e eventos de usuários.",
    version="1.0.0"
)


# --- Endpoints de Autenticação e Registro ---

@app.post("/register", status_code=status.HTTP_201_CREATED, summary="Registra um novo usuário")
def api_register_user(user: schemas.UserCreate, db_sql: Session = Depends(get_db_sql)):
    db_user = crud.get_user_by_email(db_sql, user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email já registrado.")
    try:
        crud.create_user(db_sql, user)
        return {"message": f"Usuário {user.email} registrado com sucesso."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ocorreu um erro ao registrar: {e}")


@app.post("/login", response_model=schemas.Token, summary="Faz o login para obter um token")
def api_login_for_access_token(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db_sql: Session = Depends(get_db_sql)
):
    user = security.authenticate_user(db_sql, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Email ou senha incorretos.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = security.create_access_token(data={"id_usuario": user.id_usuario})
    return {"access_token": access_token, "token_type": "bearer"}


# --- NOVOS ENDPOINTS (Recuperação de Senha) ---

@app.post("/forgot-password", summary="Inicia a recuperação de senha")
def api_forgot_password(
        request: schemas.ForgotPasswordRequest,
        db_sql: Session = Depends(get_db_sql)
):
    """
    Usuário informa o e-mail para receber o token de recuperação.
    """
    user = crud.get_user_by_email(db_sql, email=request.email)

    # IMPORTANTE: Por segurança, a resposta é a mesma,
    # encontre o e-mail ou não, para evitar que um atacante
    # descubra quais e-mails estão cadastrados.
    if user:
        reset_token = security.create_password_reset_token(user.id_usuario)
        # --- AVISO DE SEGURANÇA ---
        # Em uma aplicação real, você NUNCA retornaria o token aqui.
        # Você enviaria este token por e-mail para o usuário.
        # Estamos retornando para fins de teste no Postman.
        print(f"TOKEN DE RESET PARA {user.email}: {reset_token}")
        return {
            "message": "Se um usuário com este e-mail existir, um token de recuperação foi gerado.",
            "reset_token_for_testing": reset_token
        }

    return {"message": "Se um usuário com este e-mail existir, um token de recuperação foi gerado."}


@app.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT, summary="Define uma nova senha")
def api_reset_password(
        request: schemas.ResetPasswordRequest,
        db_sql: Session = Depends(get_db_sql)
):
    """
    Usuário envia o token recebido e a nova senha.
    """
    id_usuario = security.decode_password_reset_token(request.token)
    success = crud.update_password_by_id(db_sql, id_usuario, request.new_password)

    if not success:
        # Isso não deve acontecer se o token for válido, mas é uma garantia.
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Endpoints de Gerenciamento de Usuário ---

@app.get("/users/me", response_model=schemas.UserResponse, summary="Vê o perfil do usuário logado")
def api_get_my_profile(user: schemas.UserInDB = Depends(security.get_current_active_user)):
    return user


@app.put("/users/me/profile", response_model=schemas.UserResponse, summary="Atualiza o nome do usuário logado")
def api_update_my_profile(
        data: schemas.UserUpdateProfile,
        db_sql: Session = Depends(get_db_sql),
        id_usuario: str = Depends(security.get_current_user_id)
):
    updated_user = crud.update_user_profile(db_sql, id_usuario, data)
    if not updated_user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    return updated_user


@app.put("/users/me/password", status_code=status.HTTP_204_NO_CONTENT, summary="Altera a senha do usuário logado")
def api_update_my_password(
        data: schemas.UserUpdatePassword,
        db_sql: Session = Depends(get_db_sql),
        id_usuario: str = Depends(security.get_current_user_id)
):
    if data.old_password == data.new_password:
        raise HTTPException(status_code=400, detail="A nova senha não pode ser igual à antiga.")
    success = crud.update_user_password(db_sql, id_usuario, data)
    if not success:
        raise HTTPException(status_code=400, detail="Senha antiga incorreta.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Endpoints de Administração ---

@app.delete("/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="[ADMIN] Deleta um usuário")
def api_admin_delete_user(
        user_id: str,
        db_sql: Session = Depends(get_db_sql),
        admin_user: schemas.UserInDB = Depends(security.get_admin_user)
):
    if admin_user.id_usuario == user_id:
        raise HTTPException(status_code=400, detail="Administrador não pode deletar a si mesmo.")
    success = crud.delete_user_by_id(db_sql, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Usuário não encontrado para deleção.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- NOVO ENDPOINT DE ADMINISTRAÇÃO ---

@app.get("/admin/users/search", response_model=List[schemas.UserSearchResponse], summary="[ADMIN] Procura por usuários")
def api_admin_search_users(
        q: str = Query(..., min_length=1, description="Termo de busca para e-mail ou nome completo"),
        db_sql: Session = Depends(get_db_sql),
        admin_user: schemas.UserInDB = Depends(security.get_admin_user)
):
    """
    [Rota de Administrador]
    Busca usuários cujo e-mail ou nome completo contenham o termo de busca.
    """
    users = crud.search_users(db_sql, search_term=q)
    return users


# --- Endpoints de Eventos (CRUD) ---
# ... (o restante do seu arquivo main.py continua igual)
@app.post("/eventos/", response_model=schemas.EventoResposta, status_code=status.HTTP_201_CREATED,
          summary="Cria um novo evento")
def api_criar_evento(
        evento: schemas.EventoCriacao,
        db_sql: Session = Depends(get_db_sql),
        db_mongo: Collection = Depends(get_db_mongo_collection),
        db_redis: Redis = Depends(get_db_redis),
        id_usuario: str = Depends(security.get_current_user_id)
):
    try:
        novo_evento_id_sql = crud.criar_evento_completo(db_sql, db_mongo, evento, id_usuario)

        cache_key_lista = f"agenda:{id_usuario}"
        db_redis.delete(cache_key_lista)

        evento_criado = crud.get_single_event_by_id(
            db_sql, db_mongo, novo_evento_id_sql, id_usuario
        )

        if not evento_criado:
            raise HTTPException(status_code=500, detail="Erro ao buscar evento recém-criado.")

        return evento_criado

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ocorreu um erro ao criar evento: {e}")


@app.get("/agenda/", response_model=List[schemas.EventoResposta], summary="Obtém a agenda do usuário (com cache)")
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
            print("LOG: ACERTO NO CACHE DA AGENDA!")
            return json.loads(cached_agenda)
    except Exception as e:
        print(f"AVISO: Falha ao ler cache do Redis. {e}")

    print("LOG: FALHA NO CACHE DA AGENDA!")
    agenda = crud.obter_agenda_do_banco(db_sql, db_mongo, id_usuario)

    try:
        db_redis.set(cache_key, json.dumps(agenda, default=str), ex=3600)
    except Exception as e:
        print(f"AVISO: Falha ao salvar cache da agenda no Redis. {e}")

    return agenda


@app.get("/eventos/{id_evento}", response_model=schemas.EventoResposta, summary="Obtém um único evento pelo ID")
def api_get_single_event(
        id_evento: str,
        db_sql: Session = Depends(get_db_sql),
        db_mongo: Collection = Depends(get_db_mongo_collection),
        db_redis: Redis = Depends(get_db_redis),
        id_usuario: str = Depends(security.get_current_user_id)
):
    cache_key = f"evento:{id_evento}"

    try:
        cached_event = db_redis.get(cache_key)
        if cached_event:
            print("LOG: ACERTO NO CACHE DE EVENTO ÚNICO!")
            return json.loads(cached_event)
    except Exception as e:
        print(f"AVISO: Falha ao ler cache do Redis. {e}")

    print("LOG: FALHA NO CACHE DE EVENTO ÚNICO!")
    evento = crud.get_single_event_by_id(db_sql, db_mongo, id_evento, id_usuario)

    if not evento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento não encontrado ou não pertence ao usuário."
        )

    try:
        db_redis.set(cache_key, json.dumps(evento, default=str), ex=3600)
    except Exception as e:
        print(f"AVISO: Falha ao salvar cache individual no Redis. {e}")

    return evento


@app.put("/eventos/{id_evento}", response_model=schemas.EventoResposta, summary="Atualiza um evento existente")
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
        cache_key_lista = f"agenda:{id_usuario}"
        cache_key_item = f"evento:{id_evento}"
        db_redis.delete(cache_key_lista)
        db_redis.delete(cache_key_item)
    except Exception as e:
        print(f"AVISO: Evento atualizado com sucesso, mas falha ao limpar o cache: {e}")

    evento_atualizado_real = crud.get_single_event_by_id(
        db_sql, db_mongo, id_evento, id_usuario
    )

    if not evento_atualizado_real:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento não encontrado após a atualização."
        )

    return evento_atualizado_real


@app.delete("/eventos/{id_evento}", status_code=status.HTTP_204_NO_CONTENT, summary="Deleta um evento")
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
        cache_key_lista = f"agenda:{id_usuario}"
        cache_key_item = f"evento:{id_evento}"
        db_redis.delete(cache_key_lista)
        db_redis.delete(cache_key_item)
    except Exception as e:
        print(f"AVISO: Evento deletado com sucesso, mas falha ao limpar o cache: {e}")

    return Response(status_code=status.HTTP_204_NO_CONTENT)