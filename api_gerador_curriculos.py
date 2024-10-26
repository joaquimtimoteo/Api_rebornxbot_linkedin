import os
from typing import Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Security
from fastapi.responses import JSONResponse, FileResponse
from fastapi import APIRouter, status
from pydantic import BaseModel, EmailStr
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from email.message import EmailMessage
from aiosmtplib import send
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import openai
import uvicorn
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi.security import OAuth2PasswordBearer

load_dotenv()
MONGO_URI = os.getenv('MONGO_URI')
DB_NAME = os.getenv('DATABASE_NAME')
SMTP_USER = os.getenv('SMTP_MAIL')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
SMTP_HOST = os.getenv('SMTP_HOST')
SMTP_PORT = int(os.getenv('SMTP_PORT'))
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]

app = FastAPI(title="API reborn Xboot- linkdin Resume generater", version="1.0.0")
router = APIRouter()

class UserBase(BaseModel):
    name: str
    location: Optional[str] = None
    email: EmailStr
    jobtitle: str
    password: str  

class UserInDB(UserBase):
    hashed_password: str

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def criar_curriculo_pdf(nome, local, telefone, email, experiencia, habilidades, educacao, projetos, caminho_arquivo):
    pdf = canvas.Canvas(caminho_arquivo, pagesize=letter)
    pdf.setTitle(f"Currículo de {nome}")

    margem_esquerda, margem_superior, linha_espaco = 100, 750, 20

    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(margem_esquerda, margem_superior, nome)

    pdf.setFont("Helvetica", 12)
    pdf.drawString(margem_esquerda, margem_superior - linha_espaco, f"{local} – {telefone} – {email}")

    def adicionar_secao(titulo, conteudo, y_pos):
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(margem_esquerda, y_pos, titulo)
        pdf.setFont("Helvetica", 12)
        text = pdf.beginText(margem_esquerda, y_pos - linha_espaco)
        text.textLines(conteudo)
        pdf.drawText(text)

    adicionar_secao("Experiência Profissional:", experiencia, margem_superior - linha_espaco * 3)
    adicionar_secao("Habilidades e Interesses:", habilidades, margem_superior - linha_espaco * 8)
    adicionar_secao("Educação:", educacao, margem_superior - linha_espaco * 12)
    adicionar_secao("Projetos Técnicos:", projetos, margem_superior - linha_espaco * 16)

    pdf.save()

async def gerar_conteudo_openai(prompt: str) -> str:
    openai.api_key = OPENAI_API_KEY
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não pôde validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        user = await db.users.find_one({"email": email})
        if user is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return user

@app.post("/register/")
async def register_user(user: UserBase):
    hashed_password = get_password_hash(user.password)
    user_dict = user.dict()
    user_dict["hashed_password"] = hashed_password
    await db.users.insert_one(user_dict)
    return JSONResponse(content={"detail": "Usuário registrado com sucesso."}, status_code=201)

@app.post("/token/")
async def login(user: UserBase):
    db_user = await db.users.find_one({"email": user.email})
    if not db_user or not verify_password(user.password, db_user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Credenciais inválidas")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@app.post("/activate/")
async def activate_account(email: EmailStr, code: str):
    user = await db.users.find_one({"email": email})
    if not user or user["activation_code"] != code:
        raise HTTPException(status_code=400, detail="Código de ativação inválido.")
    
    await db.users.update_one({"email": email}, {"$set": {"is_active": True}})
    return JSONResponse(content={"detail": "Conta ativada com sucesso."})

@app.post("/curriculo/generate/")
async def gerar_curriculo(curriculo: UserBase, background_tasks: BackgroundTasks, current_user: UserBase = Depends(get_current_user)):
    experiencia = await gerar_conteudo_openai(f"Generate work experience details for {curriculo.name}.")
    habilidades = await gerar_conteudo_openai(f"Generate skills for {curriculo.jobtitle}.")
    
    caminho_arquivo = f"{curriculo.name}_curriculo.pdf"
    criar_curriculo_pdf(
        curriculo.name, curriculo.location or "N/A", "N/A", curriculo.email, 
        experiencia, habilidades, "Educação não fornecida.", "Projetos não fornecidos.", caminho_arquivo
    )
    await db.curriculos.insert_one(curriculo.dict())
    return FileResponse(caminho_arquivo, media_type='application/pdf', filename=caminho_arquivo)

@app.get("/curriculo/{nome}/")
async def obter_curriculo(nome: str, current_user: UserBase = Depends(get_current_user)):
    curriculo = await db.curriculos.find_one({"nome": nome})
    if not curriculo:
        raise HTTPException(status_code=404, detail="Currículo não encontrado.")
    return curriculo

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
