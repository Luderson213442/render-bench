"""Roda no runner: renderiza a faixa de quadros da parte K de N de uma página Three.js (?render) e grava parte.mp4."""
import sys, time, subprocess, argparse
from playwright.sync_api import sync_playwright
ap = argparse.ArgumentParser()
ap.add_argument('--url'); ap.add_argument('--k', type=int); ap.add_argument('--n', type=int)
ap.add_argument('--w', type=int, default=1920); ap.add_argument('--h', type=int, default=1080)
ap.add_argument('--out', default='parte.mp4'); ap.add_argument('--fps', type=int, default=30)
a = ap.parse_args()
T0 = time.time()
def log(*x): print(f'{time.time()-T0:6.1f}s', *x, flush=True)
ARGS = ['--use-angle=swiftshader', '--use-gl=angle', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--enable-webgl', '--allow-file-access-from-files']
with sync_playwright() as p:
    br = p.chromium.launch(args=ARGS)
    pg = br.new_page(viewport={'width': a.w, 'height': a.h})
    erros = []
    pg.on('pageerror', lambda e: erros.append(str(e)))
    pg.on('console', lambda m: print('console:', m.text[:200]) if m.type == 'error' else None)
    pg.goto(a.url)
    pg.wait_for_function('window.__TOTAL > 0', timeout=120000)
    pg.evaluate('window.__pronto')
    pg.wait_for_timeout(500)
    F = pg.evaluate('window.__TOTAL')
    cortes = [round(F * i / a.n) for i in range(a.n + 1)]
    ini, fim = cortes[a.k], cortes[a.k + 1]
    log(f'parte {a.k}/{a.n}: quadros {ini}..{fim - 1} de {F}; GL:', pg.evaluate("(()=>{const c=document.createElement('canvas');const g=c.getContext('webgl2')||c.getContext('webgl');if(!g)return 'SEM WEBGL';const e=g.getExtension('WEBGL_debug_renderer_info');return e?g.getParameter(e.UNMASKED_RENDERER_WEBGL):'ok'})()"))
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', str(a.fps), '-c:v', 'mjpeg', '-i', '-',
                           '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', '-r', str(a.fps), a.out], stdin=subprocess.PIPE)
    if ini > 0: pg.evaluate(f'window.__quadro({ini - 1})')
    log('simulou até a véspera')
    for q in range(ini, fim):
        pg.evaluate(f'window.__quadro({q})')
        img = pg.screenshot(type='jpeg', quality=95)
        if q == ini + (fim - ini) // 2 and len(img) < 15000:
            log(f'ERRO: quadro {q} parece preto/vazio ({len(img)} bytes)'); sys.exit(2)
        ff.stdin.write(img)
        if (q - ini) % 20 == 0: log(f'quadro {q}')
    ff.stdin.close(); ff.wait()
    br.close()
if erros: log('erros JS:', erros[:3])
log('ok', ff.returncode)
sys.exit(ff.returncode)
