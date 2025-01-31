from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware  # Importe o middleware CORS
from aiohttp import ClientSession

# Configurações iniciais
app = FastAPI(title="API Reborn XBoot - LinkedIn Recrutamento", version="1.0.0")

# Configuração do CORS
# Adicione os domínios permitidos na lista origins
origins = [
    "http://localhost",          # Permite o frontend local
    "http://localhost:3000",     # Permite o frontend React (ou outro framework) na porta 3000
    "https://reborntechnology.tech", 
    "https://api-rebornxbot-linkedin.onrender.com",
    # Permite o domínio do seu frontend em produção
]

# Adicione o middleware CORS ao app
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # Domínios permitidos
    allow_credentials=True,      # Permite cookies e cabeçalhos de autenticação
    allow_methods=["*"],         # Permite todos os métodos (GET, POST, etc.)
    allow_headers=["*"],         # Permite todos os cabeçalhos
)

# Credenciais do LinkedIn (inseridas diretamente no código)
LINKEDIN_CLIENT_ID = "78uay85qzgek0z"
LINKEDIN_CLIENT_SECRET = "WPL_AP1.PimxB5DEz3xA75xh.FA0hoA=="
LINKEDIN_REDIRECT_URI = "https://reborntechnology.tech/"

# URLs da API do LinkedIn
LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_API_URL = "https://api.linkedin.com/v2"

# Escopos necessários
SCOPES = ["openid", "profile", "w_member_social", "email"]

# Iniciar o fluxo OAuth 2.0
@app.get("/login/linkedin")
async def login_linkedin():
    auth_url = (
        f"{LINKEDIN_AUTH_URL}?response_type=code&client_id={LINKEDIN_CLIENT_ID}"
        f"&redirect_uri={LINKEDIN_REDIRECT_URI}&scope={' '.join(SCOPES)}"
    )
    return RedirectResponse(url=auth_url)

# Callback para receber o código de autorização
@app.get("/callback/linkedin")
async def callback_linkedin(code: str):
    try:
        # Trocar o código por um token de acesso
        async with ClientSession() as session:
            data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": LINKEDIN_REDIRECT_URI,
                "client_id": LINKEDIN_CLIENT_ID,
                "client_secret": LINKEDIN_CLIENT_SECRET,
            }
            async with session.post(LINKEDIN_TOKEN_URL, data=data) as response:
                token_data = await response.json()
                access_token = token_data.get("access_token")
                if not access_token:
                    raise HTTPException(status_code=400, detail="Falha ao obter token de acesso.")
                
                # Retornar o token de acesso (ou armazená-lo de forma segura)
                return {"access_token": access_token}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no callback do LinkedIn: {str(e)}")

# Função para buscar informações do perfil
async def buscar_perfil_linkedin(access_token: str):
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        async with ClientSession() as session:
            # Buscar informações básicas do perfil
            async with session.get(f"{LINKEDIN_API_URL}/me", headers=headers) as response:
                perfil = await response.json()
                return perfil
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar perfil: {str(e)}")

# Endpoint para buscar informações do usuário
@app.get("/buscar/usuario")
async def buscar_usuario(access_token: str = Depends()):
    try:
        perfil = await buscar_perfil_linkedin(access_token)
        return {"perfil": perfil}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar usuário: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
