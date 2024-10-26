from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
import bcrypt
import motor.motor_asyncio
from pymongo import MongoClient
import os
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from dotenv import load_dotenv
from twilio.rest import Client
import openai
import time
from typing import Optional
from pydantic import BaseModel, EmailStr, Field  
from bson import ObjectId
from pymongo.collection import Collection 
from contextlib import asynccontextmanager

# Carregar variáveis de ambiente
load_dotenv()

app = FastAPI(
    title="Reborn Technology - Xbot WhatsApp",
    description="API para gerenciar usuários e autenticação. Integra o XBot para WhatsApp.",
    version="1.0.0"
)

MONGO_URI = os.getenv("MONGO_URI")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
DATABASE_NAME = os.getenv("DATABASE_NAME")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SMTP_USER = os.getenv("SMTP_MAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
USER_COLLECTION_NAME = os.getenv("USER_COLLECTION_NAME")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")


client = MongoClient(MONGO_URI)
db = client[DATABASE_NAME] 

async def get_users_collection():
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI) 
    db = client[DATABASE_NAME]  
    return db[USER_COLLECTION_NAME]  

@app.on_event("startup")
async def startup_event():
    app.state.db_client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        await app.state.db_client.admin.command('ping')
        app.state.users_collection = app.state.db_client['UserDatabase']['users']
        print("Conexão com MongoDB estabelecida com sucesso.")
    except Exception as e:
        print(f"Erro ao conectar ao MongoDB: {e}")
        raise HTTPException(status_code=500, detail="Erro ao conectar ao MongoDB")

@app.on_event("shutdown")
async def shutdown_event():
    client = app.state.db_client
    if client:
        client.close()
        print("Conexão com MongoDB fechada.")

@app.get("/")
async def read_root():
    return {"message": "Bem-vindo à API Reborn Technology!"}

async def get_users_collection():
    return app.state.users_collection

class UserBase(BaseModel):
    id: Optional[str] = None  
    location: Optional[str] = None
    username: str
    email: EmailStr
    name: str
    jobtitle: Optional[str] = None
    role: Optional[str] = None
    posts: Optional[str] = None
    coverImg: Optional[str] = None
    followers: Optional[str] = None
    description: Optional[str] = None
    whatsapp_number: str
    activation_code: Optional[str] = None  
    is_active: bool = False
    password: str = Field(..., min_length=6)  

class UserRegister(UserBase):
    password: str

class UserLogin(BaseModel):
   username: str
   email: EmailStr
   password: str

class Token(BaseModel):
    access_token: str
    token_type: str
class ActivationRequest(BaseModel):
    username: str = None
    email: EmailStr = None
    activation_code: str

    def __init__(self, **data):
        super().__init__(**data)
        if not self.username and not self.email:
           raise ValueError("É necessário fornecer um nome de usuário ou email.")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.get("/items/{item_id}", summary="Get an item by ID", description="Retrieve an item from the inventory using its unique ID.")
async def read_item(item_id: int):
    return {"item_id": item_id}

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
class ResendActivationRequest(BaseModel):
    username: str

def validate_whatsapp_number(number: str) -> bool:
    return number.startswith("+") and number[1:].isdigit() and 10 <= len(number[1:]) <= 15

def send_whatsapp_message(to_number: str, message: str):
    if not validate_whatsapp_number(to_number):
        raise HTTPException(status_code=400, detail="Número de WhatsApp inválido.")
    
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    try:
        message = client.messages.create(
            body=message,
            from_=f'whatsapp:{TWILIO_WHATSAPP_NUMBER}',
            to=f'whatsapp:{to_number}'
        )
        print(f"Mensagem enviada com sucesso para {to_number}: {message.sid}")
    except Exception as e:
        print(f"Erro ao enviar mensagem: {e}")
        raise HTTPException(status_code=500, detail="Erro ao enviar mensagem no WhatsApp.")

async def get_user_by_username(username: str):
    users_collection = await get_users_collection()  
    return await users_collection.find_one({'username': username})  
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        user = await get_user_by_username(username)
        if user is None:
            raise credentials_exception
        return user
    except JWTError:
        raise credentials_exception

def send_email(to_email: str, subject: str, user_name: str, activation_code: str):
    email_body = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Email de Ativação</title>
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #f4f4f4; }}
            .container {{ width: 100%; max-width: 600px; margin: 0 auto; background-color: #fff; padding: 20px; border-radius: 8px; }}
            .header {{ background-color: #007bff; color: #fff; padding: 10px; text-align: center; border-radius: 8px 8px 0 0; }}
            .content {{ margin: 20px 0; }}
            .footer {{ font-size: 12px; color: #777; text-align: center; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Ativação de Conta</h1>
            </div>
            <div class="content">
                <p>Olá, {user_name}</p>
                <p>Obrigado por se registrar. Para ativar sua conta, use o seguinte código de ativação:</p>
                <h2>{activation_code}</h2>
                <p>Por favor, insira este código na página de ativação dentro de 5 minutos.</p>
                <p>Se você não se registrou, ignore este e-mail.</p>
            </div>
            <div class="footer">
                <p>Se você tiver dúvidas, entre em contato conosco pelo e-mail <a href="mailto:support@yourcompany.com">reborntechnology.tech</a>.</p>
            </div>
        </div>
    </body>
    </html>
    """
    msg = EmailMessage()
    msg.set_content(email_body, subtype='html')
    msg['Subject'] = subject
    msg['From'] = formataddr(('Reborn Technology', SMTP_USER))
    msg['To'] = to_email

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        raise HTTPException(status_code=500, detail="Erro ao enviar e-mail")

@app.post("/register", response_model=Token)
async def register(user: UserRegister):
    existing_user = await get_user_by_username(user.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="Usuário já existe")
    
    if not validate_whatsapp_number(user.whatsapp_number):
        raise HTTPException(status_code=400, detail="Número de WhatsApp inválido")

    hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())
    activation_code = str(os.urandom(3).hex()) 
    users_collection = await get_users_collection()
    
    await users_collection.insert_one({
        **user.model_dump(),  
        "password": hashed_password.decode('utf-8'),  
        "activation_code": activation_code,
        "_id": ObjectId()  
    })
    
    send_email(user.email, "Código de Ativação", user.name, activation_code)

    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await get_user_by_username(form_data.username)
    if user is None or not bcrypt.checkpw(form_data.password.encode('utf-8'), user['password']):
        raise HTTPException(status_code=400, detail="Usuário ou senha inválidos")
    
    access_token = create_access_token(data={"sub": form_data.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/activate", response_model=dict)
async def activate_user(activation_request: ActivationRequest):
    user = await get_user_by_username(activation_request.username)
    if user is None or user['activation_code'] != activation_request.activation_code:
        raise HTTPException(status_code=400, detail="Código de ativação inválido ou usuário não encontrado")
    
    users_collection = await get_users_collection() 
    
    await users_collection.update_one(
        {"username": activation_request.username}, 
        {"$set": {"is_active": True, "activation_code": None}}
    )
    
    return {"message": "Conta ativada com sucesso."}

@app.post("/send-message/")
async def send_message(to_number: str, message: str, current_user: dict = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não autenticado.")
    
    try:
        sentiment_analysis = await analyze_sentiment_with_openai(message)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao analisar sentimento: {str(e)}")


    sentiment_label = sentiment_analysis.get("label", "neutro")

    
    response_message = await get_openai_chat_completion(message, sentiment_label, [], current_user['name'])

    send_whatsapp_message(to_number, response_message)
    return {"message": "Mensagem enviada com sucesso!"}

async def analyze_sentiment_with_openai(message: str):
    prompt = (
        f"Analise o sentimento da seguinte mensagem e classifique como 'positivo', 'negativo' ou 'neutro': {message}"
    )

    max_retries = 3
    delay_between_attempts = 120  
    for attempt in range(max_retries):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}]
            )
            sentiment_response = response.choices[0].message.content.strip()
            sentiment_label = extract_sentiment_label(sentiment_response)
            return {"label": sentiment_label}
        except openai.error.RateLimitError:
            if attempt < max_retries - 1:
                time.sleep(delay_between_attempts)  
                continue  
            else:
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Limite de taxa excedido. Tente novamente mais tarde.")
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao chamar a API: {str(e)}")

def extract_sentiment_label(sentiment_response: str) -> str:
    sentiment_response = sentiment_response.lower()  

    if "positivo" in sentiment_response:
        return "positivo"
    elif "negativo" in sentiment_response:
        return "negativo"
    elif "neutro" in sentiment_response:
        return "neutro"
    else:
        return "neutro"  
async def get_openai_chat_completion(message: str, sentiment_label: str, history: list, username: str) -> str:
    context_prompt = (
        f"Você é um assistente virtual que responde de forma amigável e útil. "
        f"Considerando o sentimento da mensagem '{message}' que é '{sentiment_label}', "
        f"responda de maneira apropriada, levando em conta o contexto e o tom da conversa. "
        f"Histórico da conversa: {history}. "
        f"Usuário: {username}"
    )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": context_prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao obter resposta da API: {str(e)}")
    
def send_whatsapp_message(to_number: str, response_message: str):
    if not validate_whatsapp_number(to_number):
        raise HTTPException(status_code=400, detail="Número de WhatsApp inválido.")
    
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    try:
        message = client.messages.create(
            body=response_message,
            from_=f'whatsapp:{TWILIO_WHATSAPP_NUMBER}', 
            to=f'whatsapp:{to_number}'  
        )
        print(f"Mensagem enviada com sucesso para {to_number}: {message.sid}")
    except Exception as e:
        print(f"Erro ao enviar mensagem: {e}")
        raise HTTPException(status_code=500, detail="Erro ao enviar mensagem no WhatsApp.")

def validate_whatsapp_number(number: str) -> bool:
    return number.startswith("+") and number[1:].isdigit() and 10 <= len(number[1:]) <= 15


@app.post("/resend-activation", response_model=dict)
async def resend_activation(request: ResendActivationRequest):
    user = await get_user_by_username(request.username)
    if user is None:
        raise HTTPException(status_code=400, detail="Usuário não encontrado")

    activation_code = str(os.urandom(3).hex())
    users_collection = await get_users_collection()

    await users_collection.update_one(
        {"username": request.username}, 
        {"$set": {"activation_code": activation_code}}
    )
    
    send_email(user['email'], "Novo Código de Ativação", user['name'], activation_code)
    return {"message": "Código de ativação reenviado com sucesso."}


@app.get("/users/me", response_model=UserBase)
async def read_users_me(current_user: UserBase = Depends(get_current_user)):
    return current_user

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
