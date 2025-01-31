import os
import secrets
from typing import Optional, List
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from fastapi import APIRouter
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from email.message import EmailMessage
from aiohttp import ClientSession
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import jwt
from datetime import datetime, timedelta
from passlib.hash import bcrypt

load_dotenv()
app = FastAPI()
app = FastAPI(title="API reborn Xboot- linkdin recrutmento", version="1.0.0")
router = APIRouter()

MONGO_URI = os.getenv('MONGO_URI')
DB_NAME = os.getenv('DATABASE_NAME')
client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]

SMTP_USER = os.getenv('SMTP_MAIL')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
SMTP_HOST = os.getenv('SMTP_HOST')
SMTP_PORT = int(os.getenv('SMTP_PORT'))
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class MensagemRequest(BaseModel):
    nome: str
    area: str
    habilidades: List[str]

class Avaliacao(BaseModel):
    comentario: str
    empresa: str
    usuario_id: str
    sentimento: Optional[str] = None

class FiltrosPesquisa(BaseModel):
    palavras_chave: List[str]
    localizacao: str
    tipo_trabalho: str
    setor: str
    email: EmailStr

class User(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    password: str

class UserInDB(User):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def hash_password(password: str) -> str:
    if isinstance(password, bytes):
        password = password.decode('utf-8')
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, os.getenv('SECRET_KEY'), algorithm="HS256")

async def gerar_mensagem(nome: str, area: str, habilidades: List[str]) -> str:
    prompt = (
        f"Crie uma mensagem formal para um recrutador explicando o interesse "
        f"em uma vaga na área de {area}. Destaque: {', '.join(habilidades)}."
    )
    try:
        async with ClientSession() as session:
            response = await session.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": prompt}], "temperature": 0.7},
            )
            response_data = await response.json()
            return response_data['choices'][0]['message']['content']
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na API do OpenAI: {str(e)}")

async def analisar_sentimento(comentario: str) -> str:
    prompt = f"Qual é o sentimento da seguinte avaliação? '{comentario}'"
    try:
        async with ClientSession() as session:
            response = await session.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": prompt}], "temperature": 0.7},
            )
            response_data = await response.json()
            return response_data['choices'][0]['message']['content']
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na API do OpenAI: {str(e)}")

async def buscar_no_google(query: str):
    url = f"https://www.googleapis.com/customsearch/v1?key={os.getenv('GOOGLE_API_KEY')}&cx={os.getenv('GOOGLE_CX')}&q={query}"
    async with ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, os.getenv('SECRET_KEY'), algorithms=["HS256"])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    user = await db.users.find_one({"username": username})
    if user is None:
        raise credentials_exception
    return user

@app.post("/register/", response_model=User)
async def register(user: User):
    user_in_db = await db.users.find_one({"username": user.username})
    if user_in_db:
        raise HTTPException(status_code=400, detail="Username already registered")

    hashed_password = hash_password(user.password)
    user_data = user.dict()
    user_data['hashed_password'] = hashed_password
    await db.users.insert_one(user_data)
    return user

@app.post("/token/", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await db.users.find_one({"username": form_data.username})
    if not user or not verify_password(form_data.password, user['hashed_password']):
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user['username']}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me/")
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@app.post("/mensagem-recrutador/")
async def mensagem_recrutador(request: MensagemRequest, current_user: User = Depends(get_current_user)):
    mensagem = await gerar_mensagem(request.nome, request.area, request.habilidades)
    return JSONResponse(content={"mensagem": mensagem})

@app.post("/avaliacao/")
async def avaliar_empresa(avaliacao: Avaliacao, current_user: User = Depends(get_current_user)):
    sentimento = await analisar_sentimento(avaliacao.comentario)
    avaliacao.sentimento = sentimento
    await db.avaliacoes.insert_one(avaliacao.dict())
    return JSONResponse(content={"detail": "Avaliação registrada com sucesso.", "sentimento": sentimento})

@app.post("/alerta-vagas/")
async def criar_alerta(alerta: FiltrosPesquisa, current_user: User = Depends(get_current_user)):
    await db.alertas.insert_one(alerta.dict())
    return JSONResponse(content={"detail": "Alerta de vagas criado com sucesso."})

@app.post("/buscar/vagas", summary="Buscar vagas com filtros")
async def buscar_vagas(filtros: FiltrosPesquisa):
    query = f"{' '.join(filtros.palavras_chave)} {filtros.localizacao} {filtros.tipo_trabalho} {filtros.setor}"
    resultados = await buscar_no_google(query)
    return {"resultados": resultados}

@app.put("/avaliar/empresa/{avaliacao_id}", summary="Atualizar avaliação de empresa", response_model=Avaliacao)
async def atualizar_avaliacao(avaliacao_id: str, avaliacao: Avaliacao, current_user: User = Depends(get_current_user)):
    resultado = await db.avaliacoes.update_one({"_id": avaliacao_id}, {"$set": avaliacao.dict()})
    if resultado.modified_count == 1:
        return {"status": "Avaliação atualizada com sucesso!"}
    else:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada.")

@app.get("/sugerir/vagas", summary="Sugestões de vagas personalizadas")
async def sugerir_vagas(usuario_id: str, current_user: User = Depends(get_current_user)):
    alertas = await db.alertas.find({"email": usuario_id}).to_list(100)
    return {"alertas": alertas}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
