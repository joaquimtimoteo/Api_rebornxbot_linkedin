import os
import logging
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from api_recrutmento_linkedin import app as recruitment_app
from api_gerador_curriculos import app as curriculum_app
from whatsapp_rebornbot_api import app as whatsapp_reborn_app

# Carregar variáveis do .env
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

main_app = FastAPI(
    title="API de Recrutamento, Geração de Currículos e XBot WhatsApp",
    description="API para gerenciar recrutamento, geração de currículos automatizada e integração com XBot para WhatsApp",
    version="1.0.0",
)

origins = [
    "https://rebornbot.vercel.app",  
    "http://localhost:3000",  
    "http://localhost:8000",        
    "http://127.0.0.1", 
    "https://www.linkedin.com",
    "https://register-and-login-rebornxboot.onrender.com",  
    "https://register-and-login-rebornxboot.onrender.com", 
    'https://register-and-login-rebornxboot.onrender.com/docs#/default/user_login_api_user_login_post'
]

main_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montando os microserviços na aplicação principal
main_app.mount("/recrutamento", recruitment_app)
main_app.mount("/curriculos", curriculum_app)
main_app.mount("/whatsapp", whatsapp_reborn_app)

# Configurações do LinkedIn
LINKEDIN_CLIENT_ID = "78uay85qzgek0z"
LINKEDIN_CLIENT_SECRET = "WPL_AP1.PimxB5DEz3xA75xh.FA0hoA=="
LINKEDIN_REDIRECT_URI = "http://localhost:8000/auth/linkedin/callback"

LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_PROFILE_URL = "https://api.linkedin.com/v2/me"

# Rota inicial
@main_app.get("/", tags=["Home"])
async def read_root():
    return {
        "message": "Bem-vindo à API de Recrutamento e Geração de Currículos",
        "endpoints": {
            "/recrutamento": "Endpoints relacionados ao recrutamento.",
            "/curriculos": "Endpoints para geração e manipulação de currículos.",
            "/whatsapp": "Endpoints para integração com o XBot no WhatsApp.",
            "/auth/linkedin": "Iniciar autenticação com LinkedIn."
        }
    }

# Informações da API
@main_app.get("/info", tags=["Info"])
async def get_info():
    return {
        "title": main_app.title,
        "description": main_app.description,
        "version": main_app.version,
        "docs": "/docs",
        "redoc": "/redoc"
    }

# Endpoint para iniciar o processo de autenticação do LinkedIn
@main_app.get("/auth/linkedin", tags=["LinkedIn Auth"])
async def auth_linkedin():
    auth_url = (
        f"{LINKEDIN_AUTH_URL}?response_type=code&client_id={LINKEDIN_CLIENT_ID}"
        f"&redirect_uri={LINKEDIN_REDIRECT_URI}&scope=r_liteprofile%20r_emailaddress"
    )
    return RedirectResponse(url=auth_url)

# Endpoint de callback após a autenticação do LinkedIn
@main_app.get("/auth/linkedin/callback", tags=["LinkedIn Auth"])
async def auth_linkedin_callback(code: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            LINKEDIN_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": LINKEDIN_REDIRECT_URI,
                "client_id": LINKEDIN_CLIENT_ID,
                "client_secret": LINKEDIN_CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Erro ao obter token de acesso")
        
        token_data = response.json()
        access_token = token_data.get("access_token")

        # Buscar informações do usuário autenticado
        profile_response = await client.get(
            LINKEDIN_PROFILE_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if profile_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Erro ao obter perfil do LinkedIn")
        
        profile_data = profile_response.json()
        return {"profile": profile_data}

# Tratamento de exceções globais
@main_app.exception_handler(Exception)
async def custom_exception_handler(request, exc):
    logger.error(f"Erro ocorrido: {exc}")
    return JSONResponse(
        status_code=500,
        content={"message": "Ocorreu um erro interno. Tente novamente mais tarde."}
    )

app = main_app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
