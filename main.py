import os
from typing import List
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from aiohttp import ClientSession
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="API Reborn XBoot - LinkedIn Recrutamento", version="1.0.0")

# Variáveis de ambiente
GOOGLE_API_KEY = "AIzaSyCxFo3x8k0BCQEEfNQLFS-6HWux4--0sjY"
GOOGLE_CX = "809f68bfa513949ca"  # ID do motor de pesquisa fornecido

async def buscar_no_google(query: str):
    url = f"https://www.googleapis.com/customsearch/v1?key={GOOGLE_API_KEY}&cx={GOOGLE_CX}&q={query}"
    async with ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

@app.post("/buscar/vagas", summary="Buscar vagas com filtros")
async def buscar_vagas(palavras_chave: List[str], localizacao: str, tipo_trabalho: str, setor: str):
    query = f"{' '.join(palavras_chave)} {localizacao} {tipo_trabalho} {setor}"
    try:
        resultados = await buscar_no_google(query)
        return JSONResponse(content={"resultados": resultados})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar vagas: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
