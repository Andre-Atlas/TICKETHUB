from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pymongo import MongoClient
import redis

# --- 1. Conexão MySQL (SQLAlchemy) ---
# Lembre-se de usar o usuário e senha que você criou no script SQL.
# NÃO USE ROOT.
MYSQL_DATABASE_URL = "mysql+pymysql://dev_backend:DevControl1@localhost/tickethub_db"
engine = create_engine(MYSQL_DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- 2. Conexão MongoDB (PyMongo) ---
# Como seu MongoDB está local sem autenticação, a URL é simples.
MONGO_URL = "mongodb://localhost:27017/"
mongo_client = MongoClient(MONGO_URL)
# Nome do banco de dados que será criado no MongoDB
mongo_db = mongo_client["tickethub_nosql_db"]

# --- 3. Conexão Redis ---
# Aponta para o seu container Docker do Redis na porta padrão
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# --- Funções "Dependency Injector" para o FastAPI ---
# Elas garantem que cada requisição tenha sua própria sessão de banco.

def get_db_sql():
    """Retorna uma sessão do banco de dados MySQL."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db_mongo_collection():
    """Retorna a collection 'detalhes_eventos' do MongoDB."""
    # O nome da "tabela" (collection) onde os detalhes serão salvos
    return mongo_db["detalhes_eventos"]

def get_db_redis():
    """Retorna o cliente de conexão do Redis."""
    return redis_client