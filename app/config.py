from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """
    Armazena todas as configurações da aplicação, lidas de variáveis de ambiente.
    Esta é a forma correta de gerenciar configurações.
    """
    # Chave secreta para assinar os tokens JWT.

    SECRET_KEY: str = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"

    # Algoritmo de assinatura para o JWT
    ALGORITHM: str = "HS256"

    # Tempo de vida do token de acesso em minutos
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # O token expira em 30 minutos

    class Config:
        env_file = ".env"


# Cria uma instância única das configurações que será importada
# por outros módulos (como o security.py)
settings = Settings()