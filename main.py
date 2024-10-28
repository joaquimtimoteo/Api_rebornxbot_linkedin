from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from api_recrutmento_linkedin import app as recruitment_app
from api_gerador_curriculos import app as curriculum_app
from whatsapp_rebornbot_api import app as whatsapp_reborn_app


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

main_app = FastAPI(
    title="API de Recrutamento, Geração de Currículos e Xbot WhatsApp",
    description="API para gerenciar recrutamento, geração de currículos automatizada e integração com XBot para WhatsApp",
    version="1.0.0",
)

main_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

main_app.mount("/recrutamento", recruitment_app)
main_app.mount("/curriculos", curriculum_app)
main_app.mount("/whatsapp", whatsapp_reborn_app)

@main_app.get("/", tags=["Home"])
async def read_root():
    return {
        "message": "Bem-vindo à API de Recrutamento e Geração de Currículos",
        "endpoints": {
            "/recrutamento": "Endpoints relacionados ao recrutamento.",
            "/curriculos": "Endpoints para geração e manipulação de currículos.",
            "/whatsapp": "Endpoints para integração com o XBot no WhatsApp."
        }
    }

@main_app.get("/info", tags=["Info"])
async def get_info():
    return {
        "title": main_app.title,
        "description": main_app.description,
        "version": main_app.version,
        "docs": "/docs",
        "redoc": "/redoc"
    }

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
