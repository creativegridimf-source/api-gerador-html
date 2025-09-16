const express = require("express");
const multer = require("multer");
const path = require("path");
const fs = require("fs");
const { execFile } = require("child_process");

const app = express();
const upload = multer({ dest: "uploads/" });

app.use(express.json());

// Rota principal para gerar o e-mail
app.post("/build-email", upload.single("image"), (req, res) => {
  const { title, snippet, template_id, cta_url, campaign_name } = req.body;
  const imagePath = req.file ? req.file.path : req.body.image_path;

  if (!title || !snippet || !template_id || !cta_url || !campaign_name || !imagePath) {
    return res.status(400).json({ error: "Parâmetros obrigatórios faltando." });
  }

  // Mapeia o nome do template recebido para o arquivo correspondente
  const templateMap = {
    "Cidade-Center-Norte": "Cidade-Center-Norte.html",
    "Incorporadora": "Incorporadora.html",
    "Shopping Center Norte": "Shopping Center Norte.html",
    "Expo Center Norte": "Expo Center Norte.html",
    "Lar Center": "Lar Center.html"
  };

  const templateFile = templateMap[template_id];
  if (!templateFile) {
    return res.status(400).json({ error: "template_id inválido." });
  }

  const templatePath = path.join(__dirname, "templates", templateFile);
  const outHtml = path.join(__dirname, "dist", `${campaign_name}.html`);
  const outZip = path.join(__dirname, "dist", `${campaign_name}-assets.zip`);

  // Executa o build-email.js com os parâmetros
  const args = [
    path.join(__dirname, "build-email.js"),
    `--template=${templatePath}`,
    `--image=${imagePath}`,
    `--title=${title}`,
    `--snippet=${snippet}`,
    `--cta=${cta_url}`,
    `--campaign=${campaign_name}`,
    `--out=${outHtml}`
  ];

  execFile("node", args, (err, stdout, stderr) => {
    if (err) {
      console.error("Erro:", stderr);
      return res.status(500).json({ error: "Falha ao gerar e-mail." });
    }

    // Retorna os dois arquivos como links de download
    res.json({
      html_file: `/download/${campaign_name}.html`,
      assets_zip: `/download/${campaign_name}-assets.zip`
    });
  });
});

// Rota de download dos arquivos
app.use("/download", express.static(path.join(__dirname, "dist")));

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Servidor rodando em http://localhost:${PORT}`));
