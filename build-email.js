const fs = require('fs');
const path = require('path');
const sharp = require('sharp');
const Tesseract = require('tesseract.js');
const Archiver = require('archiver');

const AR_WIDTH = 700; // largura máxima do template

// --- helpers básicos ---
function htmlEscape(s){return s.replace(/[&<>"]/g,c=>({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function parseArgs() {
  const a = {};
  process.argv.slice(2).forEach(arg => {
    if (!arg.startsWith('--')) return;
    const [k,v] = arg.replace(/^--/,'').split(/=(.+)/);
    a[k] = v ?? true;
  });
  return a;
}

// --- OCR (caixas de texto) ---
async function ocrBoxes(imgBuf) {
  const { data } = await Tesseract.recognize(imgBuf, 'por+eng', { logger: ()=>{} });
  const boxes = [];
  const src = (data.blocks && data.blocks.length) ? data.blocks : data.lines || [];
  src.forEach(n => {
    if (n.text && n.text.trim()) {
      const { x0,y0,x1,y1 } = n.bbox;
      boxes.push({ x0,y0,x1,y1,text:n.text.trim() });
    }
  });
  return { text: (data.text||'').trim(), boxes };
}

// --- encontra “respiros” (linhas quase vazias/uniformes) ---
function findRespireLines(pixels, width, height) {
  const lines = [];
  for (let y=0; y<height; y++) {
    let sum=0, min=255, max=0;
    for (let x=0; x<width; x++) {
      const i=(y*width+x)*3;
      const r=pixels[i], g=pixels[i+1], b=pixels[i+2];
      const lum = 0.2126*r + 0.7152*g + 0.0722*b;
      sum += lum; min = Math.min(min, lum); max = Math.max(max, lum);
    }
    const mean = sum/width;
    lines.push({ mean, range:max-min });
  }
  const cuts = [];
  const W=8;
  for (let y=W; y<height-W; y++) {
    let s=0, min=1e9, max=-1e9;
    for (let k=-W; k<=W; k++) {
      const v = lines[y+k];
      s += v.mean; min=Math.min(min,v.mean); max=Math.max(max,v.mean);
    }
    const mean = s/(2*W+1);
    if (mean>235 && (max-min)<8) cuts.push(y);
  }
  // dedup contínuos → pega centro
  const dedup = [];
  let run=[];
  cuts.forEach(y=>{
    if (!run.length || y===run[run.length-1]+1) run.push(y);
    else { dedup.push(run[Math.floor(run.length/2)]); run=[y]; }
  });
  if (run.length) dedup.push(run[Math.floor(run.length/2)]);
  return dedup;
}
function avoidTextCuts(cutYs, boxes) {
  return cutYs.filter(y => !boxes.some(b => y >= (b.y0-6) && y <= (b.y1+6)));
}
function intervalsFromCuts(height, cutYs) {
  const cuts=[0, ...cutYs, height], iv=[];
  for (let i=0;i<cuts.length-1;i++){
    const y0=cuts[i], y1=cuts[i+1];
    if (y1-y0>=12) iv.push({y0,y1});
  }
  return iv;
}
function intervalHasText(interval, boxes) {
  const mid = (interval.y0+interval.y1)/2;
  return boxes.some(b => mid>=b.y0 && mid<=b.y1);
}

// --- zippa a pasta de assets ---
async function zipFolder(folderPath, zipPath){
  await fs.promises.mkdir(path.dirname(zipPath), { recursive:true });
  const output = fs.createWriteStream(zipPath);
  const archive = Archiver('zip', { zlib: { level: 0 } }); // sem recompressão
  const done = new Promise((res,rej)=>{ output.on('close',res); archive.on('error',rej); });
  archive.pipe(output);
  archive.directory(folderPath, false);
  archive.finalize();
  return done;
}

// --- principal ---
(async function run(){
  const args = parseArgs();
  const templatePath = args.template;
  const imagePath = args.image;
  const title = args.title || '';
  const snippet = args.snippet || '';
  const ctaUrl = args.cta || '';
  const outPath = args.out || `./dist/${args.campaign || 'email'}.html`;
  const campaign = args.campaign || 'email';
  if (!templatePath || !imagePath) {
    console.error('Obrigatórios: --template, --image, --title, --snippet, --cta, --campaign');
    process.exit(1);
  }

  // carrega e redimensiona a arte (sem ampliar)
  const base = sharp(imagePath);
  const meta = await base.metadata();
  const scale = Math.min(1, AR_WIDTH/(meta.width||AR_WIDTH));
  const resized = scale<1 ? await base.resize({ width: Math.round(meta.width*scale) }).toBuffer()
                          : await base.toBuffer();

  // OCR + projeção horizontal
  const { text: fullText, boxes } = await ocrBoxes(resized);
  const raw = await sharp(resized).raw().toColourspace('rgb').toBuffer({ resolveWithObject:true });
  const width = raw.info.width, height= raw.info.height;

  const cutCandidates = findRespireLines(raw.data, width, height);
  const safeCuts = avoidTextCuts(cutCandidates, boxes);
  const intervals = intervalsFromCuts(height, safeCuts);

  // gera fatias/trechos
  const assetsDir = path.join(path.dirname(outPath), `${campaign}-assets`);
  await fs.promises.mkdir(assetsDir, { recursive:true });

  const parts = [];
  for (const it of intervals){
    const hasText = intervalHasText(it, boxes);
    if (hasText){
      const text = boxes
        .filter(b => b.y0>=it.y0 && b.y1<=it.y1)
        .map(b => b.text).join(' ')
        .replace(/\s+/g,' ').trim();
      if (text){
        parts.push({ type:'text', html:
          `<tr><td align="left" style="padding:24px 6%; font-family:Inter, Arial, Helvetica, sans-serif; font-size:18px; line-height:1.5; color:#1D4E82;">${htmlEscape(text)}</td></tr>`
        });
        continue;
      }
    }
    // imagem (sem compressão extra)
    const buf = await sharp(resized).extract({ left:0, top:it.y0, width, height:it.y1-it.y0 }).png().toBuffer();
    const name = `slice_${it.y0}_${it.y1}.png`;
    await fs.promises.writeFile(path.join(assetsDir, name), buf);
    parts.push({ type:'img', src:`${campaign}-assets/${name}` });
  }

  // monta bloco CONTEÚDO
  let conteudo = `<!-- CONTEÚDO -->\n<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">`;
  for (const p of parts){
    if (p.type==='img'){
      conteudo += `
  <tr><td>
    <a href="${ctaUrl}" target="_blank" rel="noopener" title="Abrir">
      <img src="${p.src}" width="100%" height="auto" alt="" style="display:block;border:0;outline:0;text-decoration:none;-ms-interpolation-mode:bicubic;">
    </a>
  </td></tr>`;
    } else {
      conteudo += `\n  ${p.html}\n`;
    }
  }
  conteudo += `
  <tr><td align="center" style="padding:12px 0 32px;">
    <a href="${ctaUrl}" target="_blank" rel="noopener"
       style="text-decoration:none;background:#D22E2D;color:#ffffff;font-family:Inter, Arial, Helvetica, sans-serif;font-weight:700;font-size:16px;line-height:16px;display:inline-block;padding:14px 40px;border-radius:16px;">
      Saiba mais
    </a>
  </td></tr>
</table>\n<!-- /CONTEUDO -->`;

  // injeta no template
  let html = await fs.promises.readFile(templatePath,'utf8');
  html = html.replace(/<title>[\s\S]*?<\/title>/i, `<title>${title}</title>`);
  html = html.replace(
    /(<!--\s*SNIPPET\s*-->[\s\S]*?<font[^>]*>)([\s\S]*?)(<\/font>)/i,
    (_m, p1,_old,p3)=> `${p1}${snippet}${p3}`
  );
  const start = /<!--\s*CONTE[ÚU]DO\s*-->/i, end=/<!--\s*\/CONTEUDO\s*-->/i;
  html = html.replace(new RegExp(`${start.source}[\\s\\S]*?${end.source}`,'i'), conteudo);

  await fs.promises.mkdir(path.dirname(outPath), { recursive:true });
  await fs.promises.writeFile(outPath, html, 'utf8');

  // zipa assets
  const zipPath = path.join(path.dirname(outPath), `${campaign}-assets.zip`);
  await zipFolder(assetsDir, zipPath);

  console.log(`OK\nHTML: ${outPath}\nZIP:  ${zipPath}`);
})();
