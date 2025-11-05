from fastapi import FastAPI, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pymongo.collection import Collection
from redis import Redis
import json
from . import crud, schemas, security
from .database import get_db_sql, get_db_mongo_collection, get_db_redis
from typing import List

# Inicialização da Aplicação
app = FastAPI(
    title="TicketHub API",
    description="API para gerenciar ingressos e eventos de usuários.",
    version="1.0.0"
)


# --- Endpoints de Autenticação e Registro ---

@app.post("/register", status_code=status.HTTP_201_CREATED, summary="Registra um novo usuário")
def api_register_user(
        user: schemas.UserCreate,
        db_sql: Session = Depends(get_db_sql)
):
    """Cria uma nova conta de usuário."""
    # Verifica se o usuário já existe
    db_user = crud.get_user_by_email(db_sql, user.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já registrado."
        )

    try:
        crud.create_user(db_sql, user)
        return {"message": f"Usuário {user.email} registrado com sucesso."}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ocorreu um erro ao registrar: {e}"
        )


@app.post("/login", response_model=schemas.Token, summary="Faz o login para obter um token")
def api_login_for_access_token(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db_sql: Session = Depends(get_db_sql)
):
    """Autentica o usuário e retorna um token JWT."""
    user = security.authenticate_user(db_sql, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Cria o token de acesso
    access_token = security.create_access_token(
        data={"id_usuario": user.id_usuario}
    )
    return {"access_token": access_token, "token_type": "bearer"}


# --- Endpoints de Eventos (CRUD) ---

@app.post("/eventos/", response_model=schemas.EventoResposta, status_code=status.HTTP_201_CREATED,
          summary="Cria um novo evento")
def api_criar_evento(
        evento: schemas.EventoCriacao,
        db_sql: Session = Depends(get_db_sql),
        db_mongo: Collection = Depends(get_db_mongo_collection),
        db_redis: Redis = Depends(get_db_redis),
        id_usuario: str = Depends(security.get_current_user_id)
):
    """Cria um novo evento (MySQL + MongoDB) e invalida o cache da agenda."""
    try:
        # --- CORREÇÃO ---
        # A função CRUD agora retorna o ID do novo evento criado no SQL
        novo_evento_id_sql = crud.criar_evento_completo(
            db_sql, db_mongo, evento, id_usuario
        )

        # Limpa o cache da lista de agenda (cache de /agenda/)
        cache_key_lista = f"agenda:{id_usuario}"
        db_redis.delete(cache_key_lista)

        # --- CORREÇÃO ---
        # Em vez de simular a resposta, buscamos o evento real que acabamos de criar
        # A função get_single_event_by_id já faz o join com SQL (View) e Mongo
        evento_criado = crud.get_single_event_by_id(
            db_sql, db_mongo, novo_evento_id_sql, id_usuario
        )

        if not evento_criado:
            # Se não encontrou o evento que acabou de criar, algo muito errado aconteceu
            raise HTTPException(status_code=500, detail="Erro ao buscar evento recém-criado.")

        # Retorna o evento completo e real
        return evento_criado

    except Exception as e:
        # [cite_start]Se o erro veio do CRUD (ex: data no passado [cite: 11]), ele será capturado aqui
        raise HTTPException(status_code=500, detail=f"Ocorreu um erro ao criar evento: {e}")


@app.get("/agenda/", response_model=List[schemas.EventoResposta], summary="Obtém a agenda do usuário (com cache)")
def api_obter_agenda(
        db_sql: Session = Depends(get_db_sql),
        db_mongo: Collection = Depends(get_db_mongo_collection),
        db_redis: Redis = Depends(get_db_redis),
        id_usuario: str = Depends(security.get_current_user_id)
):
    """Obtém a lista de todos os eventos futuros do usuário."""
    cache_key = f"agenda:{id_usuario}"

    try:
        cached_agenda = db_redis.get(cache_key)
        if cached_agenda:
            print("LOG: ACERTO NO CACHE DA AGENDA!")
            return json.loads(cached_agenda)
    except Exception as e:
        print(f"AVISO: Falha ao ler cache do Redis. {e}")

    print("LOG: FALHA NO CACHE DA AGENDA!")
    # Busca dos bancos (SQL + Mongo)
    agenda = crud.obter_agenda_do_banco(db_sql, db_mongo, id_usuario)

    try:
        # Salva no cache por 1 hora (3600 seg)
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
    """Obtém os detalhes de um evento específico, com cache individual."""
    cache_key = f"evento:{id_evento}"

    try:
        cached_event = db_redis.get(cache_key)
        if cached_event:
            print("LOG: ACERTO NO CACHE DE EVENTO ÚNICO!")
            return json.loads(cached_event)
    except Exception as e:
        print(f"AVISO: Falha ao ler cache do Redis. {e}")

    print("LOG: FALHA NO CACHE DE EVENTO ÚNICO!")
    # Busca dos bancos (SQL + Mongo)
    evento = crud.get_single_event_by_id(db_sql, db_mongo, id_evento, id_usuario)

    if not evento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento não encontrado ou não pertence ao usuário."
        )

    try:
        # Salva no cache por 1 hora
        db_redis.set(cache_key, json.dumps(evento, default=str), ex=3600)
    except Exception as e:
        print(f"AVISO: Falha ao salvar cache individual no Redis. {e}")

    return evento


@app.put("/eventos/{id_evento}", response_model=schemas.EventoResposta, summary="Atualiza um evento existente")
def api_atualizar_evento(
        id_evento: str,
        evento_data: schemas.EventoCriacao,  # O corpo da requisição com os novos dados
        db_sql: Session = Depends(get_db_sql),
        db_mongo: Collection = Depends(get_db_mongo_collection),
        db_redis: Redis = Depends(get_db_redis),
        id_usuario: str = Depends(security.get_current_user_id)
):
    """Atualiza um evento (MySQL + MongoDB) e invalida os caches."""
    try:
        sucesso = crud.atualizar_evento_completo(
            db_sql, db_mongo, id_evento, id_usuario, evento_data
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ocorreu um erro ao atualizar: {e}"
        )

    # Se a função crud retornar None (ou False), o evento não foi encontrado
    if not sucesso:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento não encontrado ou não pertence ao usuário."
        )

    try:
        # Invalida ambos os caches (o da lista /agenda/ e o do item /eventos/{id}/)
        cache_key_lista = f"agenda:{id_usuario}"
        cache_key_item = f"evento:{id_evento}"
        db_redis.delete(cache_key_lista)
        db_redis.delete(cache_key_item)
    except Exception as e:
        print(f"AVISO: Evento atualizado com sucesso, mas falha ao limpar o cache: {e}")

    # --- CORREÇÃO ---
    # Retorna o objeto atualizado, buscando-o diretamente do banco
    # para garantir que todos os dados (incluindo joins como nome_categoria)
    # estejam corretos.
    evento_atualizado_real = crud.get_single_event_by_id(
        db_sql, db_mongo, id_evento, id_usuario
    )

    if not evento_atualizado_real:
        # Isso não deveria acontecer se o 'sucesso' foi True, mas é uma garantia
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento não encontrado após a atualização."
        )

    # Retorna o evento completo e real
    return evento_atualizado_real


@app.delete("/eventos/{id_evento}", status_code=status.HTTP_204_NO_CONTENT, summary="Deleta um evento")
def api_deletar_evento(
        id_evento: str,
        db_sql: Session = Depends(get_db_sql),
        db_mongo: Collection = Depends(get_db_mongo_collection),
        db_redis: Redis = Depends(get_db_redis),
        id_usuario: str = Depends(security.get_current_user_id)
):
    """Deleta um evento (MySQL + MongoDB) e invalida os caches."""
    try:
        sucesso = crud.deletar_evento_completo(db_sql, db_mongo, id_evento, id_usuario)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ocorreu um erro ao deletar: {e}"
        )

    # Se a função crud retornar None (ou False), o evento não foi encontrado
    if not sucesso:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento não encontrado ou não pertence ao usuário."
        )

    try:
        # Invalida ambos os caches
        cache_key_lista = f"agenda:{id_usuario}"
        cache_key_item = f"evento:{id_evento}"
        db_redis.delete(cache_key_lista)
        db_redis.delete(cache_key_item)
    except Exception as e:
        print(f"AVISO: Evento deletado com sucesso, mas falha ao limpar o cache: {e}")

    # Retorna 204 No Content, que é o padrão para DELETE bem-sucedido
    return Response(status_code=status.HTTP_204_NO_CONTENT)