"""Render de um vídeo do kit: o próprio player (index.html) quadro a quadro, 1080x1920 + audio/narracao_sfx.m4a -> render/<pasta>.mp4
uso: python -X utf8 render.py <pasta> [preset]"""
import asyncio, json, os, base64, subprocess, sys, time
from playwright.async_api import async_playwright
AQUI = os.path.abspath(sys.argv[1]); PRESET = sys.argv[2] if len(sys.argv) > 2 else "slow"
os.makedirs(os.path.join(AQUI, "render"), exist_ok=True)
URL = "file:///" + AQUI.replace("\\", "/") + "/index.html"
OUT = os.path.join(AQUI, "render", os.path.basename(AQUI) + ".mp4")
TIT = json.load(open(os.path.join(AQUI, "cena.json"), encoding="utf-8"))["titulo"]


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--allow-file-access-from-files"])
        pg = await b.new_page(viewport={"width": 1400, "height": 1000}); erros = []; pg.on("pageerror", lambda e: erros.append(str(e)))
        aj = os.path.join(AQUI, "ajustes_editor.json")
        if os.path.exists(aj): await pg.add_init_script(f"localStorage.setItem({json.dumps('mustang_ajustes::' + TIT)}, {json.dumps(open(aj, encoding='utf-8').read())})")
        await pg.goto(URL); await pg.wait_for_timeout(4000)
        dur, fps = await pg.evaluate("[CENA.dur, CENA.fps || 25]")
        n = int(round(dur * fps)); print(os.path.basename(AQUI), "quadros", n, flush=True)
        ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg", "-i", "-",
                               "-i", os.path.join(AQUI, "audio", "narracao_sfx.m4a"), "-vf", "scale=1080:1920:flags=lanczos,format=yuv420p",
                               "-c:v", "libx264", "-preset", PRESET, "-crf", "17", "-af", "apad", "-t", f"{n / fps:.3f}", "-c:a", "aac", "-b:a", "192k",
                               "-movflags", "+faststart", OUT], stdin=subprocess.PIPE)
        t0 = time.time()
        for q in range(n):
            d = await pg.evaluate(f"(renderAt({q / fps}), document.getElementById('c').toDataURL('image/jpeg', .96))")
            ff.stdin.write(base64.b64decode(d.split(",", 1)[1]))
            if q % 250 == 0: print(f"{q}/{n} · {time.time() - t0:.0f} s", flush=True)
        ff.stdin.close(); ff.wait(); print("erros:", erros[:5]); await b.close()
    print("OK", OUT, f"{time.time() - t0:.0f} s")
asyncio.run(main())
