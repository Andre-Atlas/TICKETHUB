import secrets

# Chave secreta para assinar os tokens JWT
# Para gerar uma nova chave, rode no terminal: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 # O token expira em 30 minutos
