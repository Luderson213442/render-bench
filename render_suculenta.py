# Render de 1 reel da suculenta no GitHub Actions: frame a frame (Playwright, Chrome) em N processos + ffmpeg.
# Uso: python render_suculenta.py <pasta_do_video> <saida.mp4> [workers]
import os, sys, json, subprocess, tempfile, time
from multiprocessing import Pool

def mix_audio(pasta, saida):
    s = open(os.path.join(pasta, "sfx", "cues.js"), encoding="utf-8").read()
    d = json.loads(s[s.index("{"):s.rindex("}") + 1])
    ins = ["-i", os.path.join(pasta, d["voz"])]; fil = []; labs = ["[0]"]
    for i, c in enumerate(d.get("cues", [])):
        src = os.path.join(pasta, c["src"])
        if not os.path.exists(src): continue
        ins += ["-i", src]; ms = int(c["t"] * 1000)
        fil.append("[%d]adelay=%d|%d,volume=%.2f[s%d]" % (len(labs), ms, ms, c.get("vol", .35), i)); labs.append("[s%d]" % i)
    fc = ";".join(fil + ["".join(labs) + "amix=inputs=%d:normalize=0:duration=first[a]" % len(labs)])
    subprocess.run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", fc, "-map", "[a]", "-c:a", "aac", "-b:a", "96k", saida], check=True)

def chunk(a):
    pasta, frames, fps, ini, fim = a
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", args=["--force-color-profile=srgb", "--autoplay-policy=no-user-gesture-required"])
        pg = b.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=1)
        pg.goto("file://" + os.path.join(pasta, "index.html") + "?render")
        pg.wait_for_function("window.renderAt && window.CENA_DADOS", timeout=60000)
        pg.wait_for_timeout(1500)
        el = pg.locator("#c")
        for f in range(ini, fim):
            pg.evaluate("t => window.renderAt(t)", round(f / fps, 4))
            el.screenshot(path=os.path.join(frames, "f%05d.jpg" % f), type="jpeg", quality=92)
        b.close()

if __name__ == "__main__":
    pasta, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    w = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    s = open(os.path.join(pasta, "cena.js"), encoding="utf-8").read()
    cena = json.loads(s[s.index("{"):s.rindex("}") + 1])
    dur, fps = cena["dur"], cena["fps"]; nf = int(round(dur * fps)); t0 = time.time()
    frames = tempfile.mkdtemp(); passo = -(-nf // w)
    with Pool(w) as pool: pool.map(chunk, [(pasta, frames, fps, i, min(nf, i + passo)) for i in range(0, nf, passo)])
    print("frames %d em %.0f s" % (nf, time.time() - t0), flush=True)
    aud = os.path.join(frames, "a.m4a"); mix_audio(pasta, aud)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", str(fps), "-i", os.path.join(frames, "f%05d.jpg"), "-i", aud,
                    "-vf", "scale=720:1280:flags=lanczos", "-c:v", "libx264", "-crf", "28", "-preset", "medium", "-pix_fmt", "yuv420p",
                    "-maxrate", "1600k", "-bufsize", "3200k", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", "-shortest", out], check=True)
    print("OK", out, "%.2f MB" % (os.path.getsize(out) / 1048576), "%.0f s" % (time.time() - t0))
