from fastapi import FastAPI, Depends
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx

# Definir as variáveis diretamente no código
CLIENT_ID = "78uay85qzgek0z"
CLIENT_SECRET = "WPL_AP1.PimxB5DEz3xA75xh.FA0hoA=="
REDIRECT_URI = "https://reborntechnology.tech/"
AUTHORIZATION_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
API_URL = "https://api.linkedin.com/v2/me"  # Para pegar informações básicas do usuário

app = FastAPI()

# Configuração de CORS
origins = [
    "http://localhost:3000",  # Se o frontend estiver rodando no localhost:3000
    "https://reborntechnology.tech",
    "https://api-rebornxbot-linkedin.onrender.com"
    # Substitua pelo domínio do seu frontend
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Permite domínios específicos
    allow_credentials=True,
    allow_methods=["*"],  # Permite todos os métodos HTTP (GET, POST, etc.)
    allow_headers=["*"],  # Permite todos os cabeçalhos
)

# Endpoint para redirecionar o usuário para o LinkedIn para autenticação
@app.get("/login")
async def login():
    authorization_url = f"{AUTHORIZATION_URL}?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope=r_liteprofile%20r_emailaddress%20w_member_social"
    return RedirectResponse(url=authorization_url)

# Endpoint de callback que recebe o código de autorização e troca por um token de acesso
@app.get("/auth/callback")
async def auth_callback(code: str):
    # Trocar o authorization code por um access token
    async with httpx.AsyncClient() as client:
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': REDIRECT_URI,
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET
        }
        response = await client.post(TOKEN_URL, data=data)
        token_data = response.json()
        access_token = token_data['access_token']
        
    return {"access_token": access_token}

# Endpoint para obter os dados do perfil LinkedIn usando o access token
@app.get("/profile")
async def get_profile(access_token: str):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0"
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(API_URL, headers=headers)
        profile_data = response.json()

    return profile_data
