from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import FileResponse
import os, uuid, shutil, zipfile
from datetime import datetime

app = FastAPI(title="API HTML Inteligente - Nomeada")

BASE_DIR = "data"
os.makedirs(BASE_DIR, exist_ok=True)

HTML_TEMPLATE = """
<html>
  <head>
    <title>{subject}</title>
  </head>
  <body>
    <!-- SNIPPET -->
    <font face="sans-serif">{snippet}</font></a></td>

    <!-- CONTEÚDO -->
    {conteudo}
    <!-- /CONTEÚDO -->
  </body>
</html>
"""

def salvar_arquivo_temporario(upload: UploadFile, pasta: str) -> str:
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, upload.filename)
    with open(caminho, "wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)
    return caminho

def simular_fatiamento_com_nomeacao(imagem_path: str, destino: str, nome_evento: str) -> list:
    os.makedirs(destino, exist_ok=True)
    data_prefixo = datetime.now().strftime("%Y%m%d")
    extensao = os.path.splitext(imagem_path)[1].lower()

    blocos = []
    for i in range(1, 4):  # Simulando 3 blocos
        nome_imagem = f"{data_prefixo}_{nome_evento}-{i}{extensao}"
        caminho_destino = os.path.join(destino, nome_imagem)
        shutil.copy(imagem_path, caminho_destino)
        blocos.append({
            "arquivo": nome_imagem,
            "alt": f"Bloco {i} da campanha {nome_evento.replace('-', ' ')}"
        })
    return blocos

def gerar_html_conteudo(blocos: list) -> str:
    html = ""
    for bloco in blocos:
        html += f"<table><tr><td><img src='imagens/{bloco['arquivo']}' alt='{bloco['alt']}' /></td></tr></table>\n"
    html += "<table><tr><td style='font-family: Inter; font-size:16px;'>Texto convertido de imagem com fundo sólido.</td></tr></table>"
    html += "<table><tr><td><a href='#' style='display:inline-block;padding:12px 24px;background:#000;color:#fff;text-decoration:none;border-radius:4px;font-family: Inter;'>Ver mais</a></td></tr></table>"
    return html

@app.post("/gerar-html")
async def gerar_html(
    template: str = Form(...),
    subject: str = Form(...),
    snippet: str = Form(...),
    nome_evento_curto: str = Form(...),
    imagem: UploadFile = Form(...)
):
    job_id = str(uuid.uuid4())[:8]
    job_folder = os.path.join(BASE_DIR, f"job_{job_id}")
    imagens_folder = os.path.join(job_folder, "imagens")
    os.makedirs(imagens_folder, exist_ok=True)

    imagem_path = salvar_arquivo_temporario(imagem, imagens_folder)
    blocos = simular_fatiamento_com_nomeacao(imagem_path, imagens_folder, nome_evento_curto)
    conteudo = gerar_html_conteudo(blocos)

    html_filename = f"{nome_evento_curto}-{datetime.now().strftime('%Y%m%d')}.html"
    html_path = os.path.join(job_folder, html_filename)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(HTML_TEMPLATE.format(subject=subject, snippet=snippet, conteudo=conteudo))

    zip_path = os.path.join(job_folder, f"{nome_evento_curto}-imagens.zip")
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for bloco in blocos:
            zipf.write(os.path.join(imagens_folder, bloco["arquivo"]), arcname=f"imagens/{bloco['arquivo']}")

    return {
        "html_url": f"/baixar/{job_id}/{os.path.basename(html_path)}",
        "imagens_zip_url": f"/baixar/{job_id}/{os.path.basename(zip_path)}"
    }

@app.get("/baixar/{job_id}/{filename}")
def baixar(job_id: str, filename: str):
    caminho = os.path.join(BASE_DIR, f"job_{job_id}", filename)
    return FileResponse(caminho, filename=filename)

@app.get("/")
def status():
    return {"status": "API inteligente com nomeação no ar."}
