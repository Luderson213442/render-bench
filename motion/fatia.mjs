// Renderiza uma FATIA [ini, fim) de um motion do kit (quadro(q) = 16 subquadros de blur, glow do herói) em MP4 sem perda visível.
//   node fatia.mjs <index.html> <ini> <fim> <saida.mp4> <stats.json> [paginas=4] [gpu=0]
// env: CHROME (executável do Chromium), FFMPEG (opcional). Cada página é um navegador próprio (1 núcleo cada).
// stats.json: diferença média entre quadros consecutivos (régua do atividade.py: cinza 270x480, % de 255) e o
// primeiro/último quadro cinza de cada pedaço, para o PC calcular a energia do vídeo inteiro sem renderizar de novo.
import { spawn } from 'node:child_process';
import { writeFileSync, rmSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { chromium } from 'playwright-core';

const [, , HTML, INI_, FIM_, SAIDA, STATS, PAG_ = '4', GPU_ = '0'] = process.argv;
const INI = +INI_, FIM = +FIM_, PAG = Math.max(1, +PAG_), GPU = GPU_ === '1';
const FF = process.env.FFMPEG || 'ffmpeg';
const t0 = Date.now(), log = (...a) => console.log(((Date.now() - t0) / 1000).toFixed(1).padStart(6), ...a);
const ARGS = ['--headless=new', '--allow-file-access-from-files', '--disable-web-security', '--disable-gpu-vsync', '--font-render-hinting=none',
  ...(GPU ? ['--enable-gpu', '--ignore-gpu-blocklist', '--use-angle=d3d11'] : [])];
const URL_ = pathToFileURL(resolve(HTML)).href + '?render';

const QUADRO = `async q=>{quadro(q);const cv=document.getElementById('cv');
  const s=window.__s||(window.__s=Object.assign(document.createElement('canvas'),{width:270,height:480}));const x=s.getContext('2d',{willReadFrequently:true});
  x.drawImage(cv,0,0,270,480);const d=x.getImageData(0,0,270,480).data,g=new Uint8Array(270*480);
  for(let i=0;i<g.length;i++)g[i]=(d[i*4]*0.299+d[i*4+1]*0.587+d[i*4+2]*0.114);
  let dif=null;if(window.__g){let s2=0;for(let i=0;i<g.length;i++){const v=g[i]-window.__g[i];s2+=v<0?-v:v;}dif=s2/g.length/255*100;}window.__g=g;
  const png=cv.toDataURL('image/png');return [png.slice(png.indexOf(',')+1),dif]}`;
const CINZA = `()=>{let st='';const g=window.__g;for(let i=0;i<g.length;i+=8192)st+=String.fromCharCode.apply(null,g.subarray(i,i+8192));return btoa(st)}`;

function codificador(arq) {
  const ff = spawn(FF, ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', '30', '-c:v', 'png', '-i', '-',
    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '16', '-pix_fmt', 'yuv420p', '-g', '60', '-bf', '0', '-r', '30',
    '-video_track_timescale', '15360', arq], { stdio: ['pipe', 'inherit', 'inherit'] });
  const fim = new Promise((ok, erro) => ff.on('close', c => c === 0 ? ok() : erro(new Error('ffmpeg ' + c))));
  const escrever = b => new Promise(ok => ff.stdin.write(b) ? ok() : ff.stdin.once('drain', ok));
  return { escrever, fechar: () => { ff.stdin.end(); return fim; } };
}

async function pedaco(k, a, b) {
  const nav = await chromium.launch({ executablePath: process.env.CHROME, args: ARGS });
  const pg = await nav.newPage({ viewport: { width: 540, height: 960 } });
  const erros = []; pg.on('pageerror', e => erros.push(e.message));
  await pg.goto(URL_);
  await pg.waitForFunction('window.__pronto===true', null, { timeout: 120000 }).catch(() => { throw new Error('página não ficou pronta: ' + erros.join('; ')); });
  await pg.evaluate(`window.__Q=${QUADRO};window.__C=${CINZA}`);
  const arq = `${SAIDA}.p${k}.mp4`, enc = codificador(arq), difs = [];
  let primeiro = null;
  for (let q = a; q < b; q++) {
    const [png, dif] = await pg.evaluate(q => window.__Q(q), q);
    if (q === a) primeiro = await pg.evaluate(() => window.__C()); else difs.push(dif);
    await enc.escrever(Buffer.from(png, 'base64'));
    if ((q - a) % 60 === 0) log(`pedaço ${k}: ${q - a}/${b - a}`);
  }
  const ultimo = await pg.evaluate(() => window.__C());
  await enc.fechar(); await nav.close();
  if (erros.length) throw new Error('erros na página: ' + erros.join('; '));
  return { arq, a, b, difs, primeiro, ultimo };
}

const n = FIM - INI, tam = Math.ceil(n / PAG), jobs = [];
for (let k = 0; k < PAG; k++) { const a = INI + k * tam, b = Math.min(FIM, a + tam); if (a < b) jobs.push(pedaco(k, a, b)); }
const res = await Promise.all(jobs);
writeFileSync(SAIDA + '.txt', res.map(r => `file '${resolve(r.arq).replace(/\\/g, '/')}'`).join('\n') + '\n');
await new Promise((ok, erro) => spawn(FF, ['-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', SAIDA + '.txt', '-c', 'copy', SAIDA], { stdio: 'inherit' })
  .on('close', c => c === 0 ? ok() : erro(new Error('concat ' + c))));
for (const r of res) rmSync(r.arq, { force: true }); rmSync(SAIDA + '.txt', { force: true });
writeFileSync(STATS, JSON.stringify(res.map(({ a, b, difs, primeiro, ultimo }) => ({ a, b, difs, primeiro, ultimo }))));
log(`fatia [${INI},${FIM}) pronta: ${n} quadros em ${((Date.now() - t0) / 1000).toFixed(1)} s (${(n / ((Date.now() - t0) / 1000)).toFixed(2)} q/s)`);
