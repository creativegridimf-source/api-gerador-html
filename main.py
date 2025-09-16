from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import shutil, os, zipfile, uuid
from typing import Optional

app = FastAPI(title="API Completa - Gerador de HTML de Campanha")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = "data"
os.makedirs(BASE_DIR, exist_ok=True)

TEMPLATE_HTML = """<html><head><title>{subject}</title></head><body>
<!-- SNIPPET --><font face="sans-serif">{snippet}</font></a></td>
<!-- CONTEÚDO -->
{conteudo}
<!-- /CONTEÚDO -->
</body></html>"""

@app.post("/gerar-html")
async def gerar_html(
    template: str = Form(...),
    subject: str = Form(...),
    snippet: str = Form(...),
    imagem: UploadFile = Form(...)
):
    job_id = str(uuid.uuid4())[:8]
    folder = os.path.join(BASE_DIR, f"job_{job_id}")
    imagens_folder = os.path.join(folder, "imagens")
    os.makedirs(imagens_folder, exist_ok=True)

    image_path = os.path.join(imagens_folder, imagem.filename)
    with open(image_path, "wb") as buffer:
        shutil.copyfileobj(imagem.file, buffer)

    conteudo_html = f"<table><tr><td><img src='imagens/{imagem.filename}' alt='Imagem da campanha' /></td></tr><tr><td style='font-family: Inter;'>Conteúdo gerado com base na imagem do template {template}.</td></tr></table>"
    html_final = TEMPLATE_HTML.format(subject=subject, snippet=snippet, conteudo=conteudo_html)

    html_filename = f"{template.lower().replace(' ', '-')}-{job_id}.html"
    html_path = os.path.join(folder, html_filename)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_final)

    zip_filename = f"{template.lower().replace(' ', '-')}-{job_id}-imagens.zip"
    zip_path = os.path.join(folder, zip_filename)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(image_path, arcname=f"imagens/{imagem.filename}")

    return {
        "html_url": f"/baixar/{job_id}/{html_filename}",
        "imagens_zip_url": f"/baixar/{job_id}/{zip_filename}"
    }

@app.post("/fatiar-imagem")
async def fatiar_imagem(imagem: UploadFile = Form(...)):
    job_id = str(uuid.uuid4())[:8]
    folder = os.path.join(BASE_DIR, f"job_{job_id}")
    imagens_folder = os.path.join(folder, "imagens")
    os.makedirs(imagens_folder, exist_ok=True)

    image_path = os.path.join(imagens_folder, imagem.filename)
    with open(image_path, "wb") as buffer:
        shutil.copyfileobj(imagem.file, buffer)

    zip_filename = f"fatiado-{job_id}.zip"
    zip_path = os.path.join(folder, zip_filename)
    with zipfile.ZipFile(zip_path, "w") as zipf:
        zipf.write(image_path, arcname=imagem.filename)

    return {
        "imagens_zip_url": f"/baixar/{job_id}/{zip_filename}",
        "blocos": [
            {
                "arquivo": imagem.filename,
                "alt_sugerido": "Imagem de campanha fatiada (exemplo)"
            }
        ]
    }

@app.post("/converter-texto-html")
async def converter_texto_em_html(imagem: UploadFile = Form(...)):
    return {
        "html_gerado": "<div style='font-family: Inter; font-size:16px;'>Texto extraído da imagem com fundo sólido (simulado)</div>"
    }

@app.post("/substituir-meta-tags")
async def substituir_subject_e_snippet(
    html: str = Form(...),
    subject: str = Form(...),
    snippet: str = Form(...)
):
    html = html.replace("<title>", f"<title>{subject}")
    if "<!-- SNIPPET -->" in html:
        before, after = html.split("<!-- SNIPPET -->", 1)
        snippet_start = after.find("<font")
        snippet_end = after.find("</font>")
        if snippet_start != -1 and snippet_end != -1:
            snippet_html = after[snippet_start:snippet_end+7]
            after = after.replace(snippet_html, f"<font face='sans-serif'>{snippet}</font>", 1)
        html = before + "<!-- SNIPPET -->" + after
    return {"html_atualizado": html}

@app.post("/gerar-alt")
async def gerar_alt_automatico(imagem: UploadFile = Form(...)):
    return {
        "alt_sugerido": f"Texto descritivo automático para {imagem.filename}"
    }

@app.post("/entregar-arquivos")
async def entregar_arquivos(job_id: str = Form(...), html_nome: str = Form(...), zip_nome: str = Form(...)):
    return {
        "html_url": f"/baixar/{job_id}/{html_nome}",
        "imagens_zip_url": f"/baixar/{job_id}/{zip_nome}"
    }

@app.get("/baixar/{job_id}/{filename}")
def baixar_arquivo(job_id: str, filename: str):
    file_path = os.path.join(BASE_DIR, f"job_{job_id}", filename)
    return FileResponse(file_path, filename=filename)
