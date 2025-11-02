from sqlalchemy.orm import Session
from pymongo.collection import Collection
from bson.objectid import ObjectId
from sqlalchemy import text
from . import schemas, security


# --- FUNÇÕES DE CRUD DE USUÁRIO ---

def get_user_by_email(db_sql: Session, email: str) -> schemas.UserInDB | None:
    """Busca um usuário pelo email."""
    query = text("SELECT * FROM usuarios WHERE email = :email")
    user_row = db_sql.execute(query, {"email": email}).first()
    if user_row:

        return schemas.UserInDB.from_orm(user_row)
    return None


def get_user_by_id(db_sql: Session, id_usuario: str) -> schemas.UserInDB | None:
    """Busca um usuário pelo ID."""
    query = text("SELECT * FROM usuarios WHERE id_usuario = :id_usuario")
    user_row = db_sql.execute(query, {"id_usuario": id_usuario}).first()
    if user_row:
        return schemas.UserInDB.from_orm(user_row)
    return None


def create_user(db_sql: Session, user: schemas.UserCreate) -> schemas.UserInDB:
    """Cria um novo usuário no banco de dados."""
    # Gera o hash da senha
    hashed_password = security.get_password_hash(user.password)

    # Gera o ID do usuário usando a função do SQL
    user_id_row = db_sql.execute(text("SELECT FUNC_GERAR_ID_USUARIO() as id")).first()

    new_user_id = user_id_row[0]

    # Define o grupo padrão como 2 (Usuario Comum)
    id_grupo_padrao = 2

    query_insert = text(
        """
        INSERT INTO usuarios (id_usuario, id_grupo, email, senha_hash, nome_completo)
        VALUES (:id_usuario, :id_grupo, :email, :senha_hash, :nome_completo)
        """
    )
    db_sql.execute(
        query_insert,
        {
            "id_usuario": new_user_id,
            "id_grupo": id_grupo_padrao,
            "email": user.email,
            "senha_hash": hashed_password,
            "nome_completo": user.nome_completo
        }
    )
    db_sql.commit()

    # Retorna os dados do usuário recém-criado
    return get_user_by_id(db_sql, new_user_id)


# --- FUNÇÕES DE CRUD DE EVENTO ---


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
        db_sql.execute(
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
        db_sql.commit()
        return mongo_id
    except Exception as e:
        db_mongo.delete_one({"_id": ObjectId(mongo_id)})
        print(f"ERRO DE SQL: Rollback do MongoDB executado. Erro: {e}")
        raise e


def obter_agenda_do_banco(db_sql: Session, db_mongo: Collection, id_usuario: str) -> list[dict]:

    query = text("SELECT * FROM VIEW_AGENDA_FUTURA_USUARIO WHERE id_usuario = :id_usuario")
    eventos_sql = db_sql.execute(query, {"id_usuario": id_usuario}).fetchall()
    if not eventos_sql:
        return []
    mongo_ids_str = [row.mongo_detalhes_id for row in eventos_sql if row.mongo_detalhes_id]
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