from sqlalchemy.orm import Session
from pymongo.collection import Collection
from bson.objectid import ObjectId
from sqlalchemy import text
from . import schemas, security


# --- Funções de CRUD de Usuário ---

def get_user_by_email(db_sql: Session, email: str) -> schemas.UserInDB | None:
    query = text(
        "SELECT id_usuario, email, senha_hash, id_grupo, nome_completo "
        "FROM usuarios WHERE email = :email"
    )
    user_row = db_sql.execute(query, {"email": email}).first()
    if user_row:
        return schemas.UserInDB(**dict(user_row._mapping))
    return None


def get_user_by_id_in_db(db_sql: Session, id_usuario: str) -> schemas.UserInDB | None:
    query = text(
        "SELECT id_usuario, email, senha_hash, id_grupo, nome_completo "
        "FROM usuarios WHERE id_usuario = :id_usuario"
    )
    user_row = db_sql.execute(query, {"id_usuario": id_usuario}).first()
    if user_row:
        return schemas.UserInDB(**dict(user_row._mapping))
    return None


def create_user(db_sql: Session, user: schemas.UserCreate):
    hashed_password = security.get_password_hash(user.password)
    id_query = text("SELECT FUNC_GERAR_ID_USUARIO() as id")
    new_user_id = db_sql.execute(id_query).scalar_one()
    insert_query = text(
        "INSERT INTO usuarios (id_usuario, id_grupo, email, senha_hash, nome_completo) "
        "VALUES (:id_usuario, 2, :email, :senha_hash, :nome_completo)"
    )
    db_sql.execute(insert_query, {
        "id_usuario": new_user_id,
        "email": user.email,
        "senha_hash": hashed_password,
        "nome_completo": user.nome_completo
    })
    db_sql.commit()
    return new_user_id


def update_user_profile(db_sql: Session, id_usuario: str, data: schemas.UserUpdateProfile) -> schemas.UserInDB | None:
    query = text("UPDATE usuarios SET nome_completo = :nome_completo WHERE id_usuario = :id_usuario")
    db_sql.execute(query, {"nome_completo": data.nome_completo, "id_usuario": id_usuario})
    db_sql.commit()
    return get_user_by_id_in_db(db_sql, id_usuario)


def update_user_password(db_sql: Session, id_usuario: str, data: schemas.UserUpdatePassword) -> bool:
    user = get_user_by_id_in_db(db_sql, id_usuario)
    if not user or not security.verify_password(data.old_password, user.senha_hash):
        return False
    new_hashed_password = security.get_password_hash(data.new_password)
    query = text("UPDATE usuarios SET senha_hash = :senha_hash WHERE id_usuario = :id_usuario")
    db_sql.execute(query, {"senha_hash": new_hashed_password, "id_usuario": id_usuario})
    db_sql.commit()
    return True


def delete_user_by_id(db_sql: Session, id_usuario: str) -> bool:
    query = text("DELETE FROM usuarios WHERE id_usuario = :id_usuario")
    result = db_sql.execute(query, {"id_usuario": id_usuario})
    db_sql.commit()
    return result.rowcount > 0


# --- NOVAS FUNÇÕES DE CRUD (Recuperação de Senha e Busca de Admin) ---

def update_password_by_id(db_sql: Session, id_usuario: str, new_password: str) -> bool:
    """Atualiza a senha de um usuário diretamente (usado para recuperação)."""
    new_hashed_password = security.get_password_hash(new_password)
    query = text("UPDATE usuarios SET senha_hash = :senha_hash WHERE id_usuario = :id_usuario")
    result = db_sql.execute(query, {"senha_hash": new_hashed_password, "id_usuario": id_usuario})
    db_sql.commit()
    return result.rowcount > 0


def search_users(db_sql: Session, search_term: str) -> list[schemas.UserInDB]:
    """Busca usuários por email ou nome completo."""
    # Adiciona wildcards (%) para a busca com LIKE
    search_pattern = f"%{search_term}%"
    query = text(
        "SELECT id_usuario, email, nome_completo, id_grupo, senha_hash "
        "FROM usuarios "
        "WHERE email LIKE :pattern OR nome_completo LIKE :pattern"
    )
    result = db_sql.execute(query, {"pattern": search_pattern}).fetchall()
    # Converte as linhas do resultado em uma lista de objetos UserInDB
    return [schemas.UserInDB(**dict(row._mapping)) for row in result]


# --- Funções de CRUD de Eventos (sem alterações) ---
# ... (o restante do seu arquivo crud.py continua igual)
def criar_evento_completo(
        db_sql: Session,
        db_mongo: Collection,
        evento: schemas.EventoCriacao,
        id_usuario: str
):
    dados_mongo = evento.dados_mongo
    resultado_mongo = db_mongo.insert_one(dados_mongo)
    mongo_id = str(resultado_mongo.inserted_id)

    if not mongo_id:
        raise Exception("Falha ao criar documento no MongoDB")

    try:
        query = text(
            "CALL SP_ADICIONAR_EVENTO_PRINCIPAL(:id_usuario, :id_categoria, :titulo, :data_inicio, :local, :mongo_id)"
        )

        result = db_sql.execute(
            query,
            {
                "id_usuario": id_usuario,
                "id_categoria": evento.id_categoria,
                "titulo": evento.titulo,
                "data_inicio": evento.data_hora_inicio,
                "local": evento.local_evento,
                "mongo_id": mongo_id
            }
        )

        novo_evento_row = result.first()
        if not novo_evento_row:
            raise Exception("Stored procedure não retornou o ID do novo evento.")

        novo_evento_id_sql = novo_evento_row._mapping['id_novo_evento']
        db_sql.commit()
        return novo_evento_id_sql

    except Exception as e:
        db_mongo.delete_one({"_id": ObjectId(mongo_id)})
        db_sql.rollback()
        print(f"ERRO DE SQL: Rollback do MongoDB executado. Erro: {e}")
        raise e


def obter_agenda_do_banco(db_sql: Session, db_mongo: Collection, id_usuario: str) -> list[dict]:
    query = text("SELECT * FROM VIEW_AGENDA_FUTURA_USUARIO WHERE id_usuario = :id_usuario")
    eventos_sql = db_sql.execute(query, {"id_usuario": id_usuario}).fetchall()

    if not eventos_sql:
        return []

    mongo_ids_str = [row.mongo_detalhes_id for row in eventos_sql if row.mongo_detalhes_id]

    if not mongo_ids_str:
        return [dict(evento._mapping) for evento in eventos_sql]

    mongo_ids_obj = [ObjectId(mid) for mid in mongo_ids_str]
    detalhes_mongo_cursor = db_mongo.find({"_id": {"$in": mongo_ids_obj}})
    detalhes_map = {str(doc["_id"]): doc for doc in detalhes_mongo_cursor}

    agenda_completa = []
    for evento in eventos_sql:
        evento_dict = dict(evento._mapping)
        mongo_id = evento_dict.get("mongo_detalhes_id")
        if mongo_id in detalhes_map:
            detalhes = detalhes_map[mongo_id]
            detalhes["_id"] = str(detalhes["_id"])
            evento_dict["detalhes_mongo"] = detalhes
        agenda_completa.append(evento_dict)
    return agenda_completa


def get_single_event_by_id(
        db_sql: Session,
        db_mongo: Collection,
        id_evento: str,
        id_usuario: str
) -> dict | None:
    query = text(
        "SELECT * FROM VIEW_AGENDA_FUTURA_USUARIO "
        "WHERE id_usuario = :id_usuario AND id_evento = :id_evento"
    )
    evento_sql = db_sql.execute(
        query,
        {"id_usuario": id_usuario, "id_evento": id_evento}
    ).first()

    if not evento_sql:
        return None

    evento_dict = dict(evento_sql._mapping)
    mongo_id = evento_dict.get("mongo_detalhes_id")

    if mongo_id:
        detalhes_mongo = db_mongo.find_one({"_id": ObjectId(mongo_id)})
        if detalhes_mongo:
            detalhes_mongo["_id"] = str(detalhes_mongo["_id"])
            evento_dict["detalhes_mongo"] = detalhes_mongo
    return evento_dict


def deletar_evento_completo(
        db_sql: Session,
        db_mongo: Collection,
        id_evento: str,
        id_usuario: str
):
    query_find = text(
        "SELECT mongo_detalhes_id FROM eventos "
        "WHERE id_evento = :id_evento AND id_usuario = :id_usuario"
    )
    evento_sql = db_sql.execute(
        query_find,
        {"id_evento": id_evento, "id_usuario": id_usuario}
    ).first()

    if not evento_sql:
        return None

    evento_dict = dict(evento_sql._mapping)
    mongo_id = evento_dict.get('mongo_detalhes_id')

    try:
        query_delete = text("DELETE FROM eventos WHERE id_evento = :id_evento")
        db_sql.execute(query_delete, {"id_evento": id_evento})

        if mongo_id:
            db_mongo.delete_one({"_id": ObjectId(mongo_id)})

        db_sql.commit()
        return True
    except Exception as e:
        db_sql.rollback()
        print(f"ERRO AO DELETAR: Rollback executado. Erro: {e}")
        raise e


def atualizar_evento_completo(
        db_sql: Session,
        db_mongo: Collection,
        id_evento: str,
        id_usuario: str,
        evento_data: schemas.EventoCriacao
):
    query_find = text(
        "SELECT mongo_detalhes_id FROM eventos "
        "WHERE id_evento = :id_evento AND id_usuario = :id_usuario"
    )
    evento_sql = db_sql.execute(
        query_find,
        {"id_evento": id_evento, "id_usuario": id_usuario}
    ).first()

    if not evento_sql:
        return None

    evento_dict = dict(evento_sql._mapping)
    mongo_id = evento_dict.get('mongo_detalhes_id')

    try:
        query_update_sql = text(
            """
            UPDATE eventos
            SET titulo           = :titulo,
                id_categoria     = :id_categoria,
                data_hora_inicio = :data_inicio,
                local_evento     = :local
            WHERE id_evento = :id_evento
            """
        )
        db_sql.execute(
            query_update_sql,
            {
                "titulo": evento_data.titulo,
                "id_categoria": evento_data.id_categoria,
                "data_inicio": evento_data.data_hora_inicio,
                "local": evento_data.local_evento,
                "id_evento": id_evento
            }
        )

        if mongo_id:
            db_mongo.replace_one(
                {"_id": ObjectId(mongo_id)},
                evento_data.dados_mongo
            )

        db_sql.commit()
        return True
    except Exception as e:
        db_sql.rollback()
        print(f"ERRO AO ATUALIZAR: Rollback executado. Erro: {e}")
        raise e