from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import shutil, os, zipfile, uuid

app = FastAPI(title="Gerador de HTML de Campanha")

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

    conteudo_html = f"""
    <table><tr><td><img src="imagens/{imagem.filename}" alt="Imagem da campanha" /></td></tr>
    <tr><td style='font-family: Inter, sans-serif;'>Conteúdo gerado com base na imagem do template {template}.</td></tr></table>
    """

    html_final = TEMPLATE_HTML.format(subject=subject, snippet=snippet, conteudo=conteudo_html)

    html_filename = f"{template.lower().replace(' ', '-')}-{job_id}.html"
    html_path = os.path.join(folder, html_filename)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_final)

    zip_filename = f"{template.lower().replace(' ', '-')}-{job_id}-imagens.zip"
    zip_path = os.path.join(folder, zip_filename)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(imagens_folder):
            for file in files:
                full_path = os.path.join(root, file)
                arcname = os.path.relpath(full_path, folder)
                zipf.write(full_path, arcname)

    return {
        "html_url": f"/baixar/{job_id}/{html_filename}",
        "imagens_zip_url": f"/baixar/{job_id}/{zip_filename}"
    }

@app.get("/baixar/{job_id}/{filename}")
def baixar_arquivo(job_id: str, filename: str):
    file_path = os.path.join(BASE_DIR, f"job_{job_id}", filename)
    return FileResponse(file_path, filename=filename)
