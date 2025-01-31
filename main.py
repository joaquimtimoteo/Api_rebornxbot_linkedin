import os
from typing import List
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from aiohttp import ClientSession
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="API Reborn XBoot - LinkedIn Recrutamento", version="1.0.0")
GOOGLE_API_KEY = "AIzaSyCxFo3x8k0BCQEEfNQLFS-6HWux4--0sjY"
GOOGLE_CX = "809f68bfa513949ca"  

async def buscar_no_google(query: str):
    url = f"https://www.googleapis.com/customsearch/v1?key={GOOGLE_API_KEY}&cx={GOOGLE_CX}&q={query}"
    async with ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

@app.post("/buscar/usuario", summary="Buscar informações de um usuário")
async def buscar_usuario(palavras_chave: List[str], localizacao: str, cargo: str):
    query = f"{' '.join(palavras_chave)} {localizacao} {cargo}"
    try:
        resultados = await buscar_no_google(query)
        
        # Processamento para extrair informações de interesse
        if 'items' in resultados:
            usuarios = []
            for item in resultados['items']:
                usuario_info = {
                    "titulo": item.get("title"),
                    "link": item.get("link"),
                    "descricao": item.get("snippet")
                }
                usuarios.append(usuario_info)
            return JSONResponse(content={"resultados": usuarios})
        else:
            raise HTTPException(status_code=404, detail="Nenhum usuário encontrado.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar usuário: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
