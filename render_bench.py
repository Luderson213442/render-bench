# -*- coding: utf-8 -*-
"""Render frio self-contained: headline no topo, cena no meio, CTA 'link da bio'
embaixo (SEM @/nome de perfil) + pitch imperceptível no áudio (anti-dedup Meta).

    python render_bench.py --input reel.mp4 --output frio.mp4 \
        --headline "ESSE FILME VAI TE PRENDER" --pitch 1.013
"""
import argparse, json, subprocess, time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
TOP = 300          # faixa da headline
BOT = 170          # faixa da CTA
BG = (10, 10, 10)
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _font(sz): return ImageFont.truetype(FONT_BOLD, sz)


def _wrap(draw, text, font, maxw):
    linhas, atual = [], ""
    for p in text.split():
        t = (atual + " " + p).strip()
        if draw.textlength(t, font=font) <= maxw:
            atual = t
        else:
            if atual: linhas.append(atual)
            atual = p
    if atual: linhas.append(atual)
    return linhas[:3]


def overlay_png(headline, destino):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # faixas sólidas topo e base (mesma cor do fundo = sem cabeçalho de perfil)
    d.rectangle([0, 0, W, TOP], fill=(10, 10, 10, 255))
    d.rectangle([0, H - BOT, W, H], fill=(10, 10, 10, 255))
    # headline (branco, caixa alta, 2-3 linhas, centralizado na faixa de cima)
    hz = headline.upper()
    sz = 74
    while sz > 40:
        f = _font(sz); ls = _wrap(d, hz, f, W - 120)
        lh = int(sz * 1.18); bloco = lh * len(ls)
        if bloco <= TOP - 48: break
        sz -= 4
    f = _font(sz); ls = _wrap(d, hz, f, W - 120)
    lh = int(sz * 1.18); y = (TOP - lh * len(ls)) // 2
    for ln in ls:
        w = d.textlength(ln, font=f)
        d.text(((W - w) / 2, y), ln, font=f, fill=(255, 255, 255, 255))
        y += lh
    # CTA embaixo, rosa, com seta
    cta = "ASSISTA NO LINK DA BIO"
    fc = _font(52); w = d.textlength(cta, font=fc)
    yc = H - BOT + (BOT - 60) // 2
    d.text(((W - w) / 2, yc), cta, font=fc, fill=(255, 90, 122, 255))
    img.save(destino)


def render(inp, out, headline, pitch):
    t0 = time.time()
    png = Path(out).with_suffix(".ov.png")
    overlay_png(headline, png)
    meio = H - TOP - BOT  # altura da cena
    grafo = (
        f"[0:v]scale={W}:{meio}:force_original_aspect_ratio=decrease,setsar=1[s];"
        f"[s]pad={W}:{H}:(ow-iw)/2:{TOP}:color=0x0a0a0a[bg];"
        f"[bg][1:v]overlay=0:0:format=auto,format=yuv420p[v];"
        f"[0:a]aresample=48000,asetrate=48000*{pitch:.4f},aresample=48000,atempo={1/pitch:.4f}[a]"
    )
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-i", inp, "-i", str(png), "-filter_complex", grafo,
           "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
           "-map_metadata", "-1", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    png.unlink(missing_ok=True)
    if r.returncode != 0:
        raise SystemExit("ffmpeg falhou: " + r.stderr[-500:])
    seg = round(time.time() - t0, 2)
    print(json.dumps({"out": out, "headline": headline, "pitch": pitch, "segundos": seg}))
    return seg


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--headline", required=True)
    ap.add_argument("--pitch", type=float, default=1.0)
    a = ap.parse_args()
    render(a.input, a.output, a.headline, a.pitch)
