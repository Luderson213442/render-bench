# -*- coding: utf-8 -*-
"""Um job = um título, várias contas. Cada conta recebe o SEU arquivo:
zoom da cena, brilho/saturação e tom do áudio levemente diferentes (imperceptível),
comment com conta:código e capa própria. Sobe tudo no R2 e grava o resultado em
semana/res/<id>.json para o PC agendar.

    python render_semana.py job.json
"""
import hashlib, json, os, subprocess, sys, urllib.request
import boto3

job = json.load(open(sys.argv[1], encoding="utf-8"))
s3 = boto3.client("s3", endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
                  aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                  aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"], region_name="auto")
BUCKET, PUB = os.environ["R2_BUCKET"], os.environ["R2_PUBLIC"].rstrip("/")


def baixar(url, destino):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=300) as r, open(destino, "wb") as f:
        f.write(r.read())


def par(n):
    return int(n) // 2 * 2


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


baixar(job["src_url"], "in.mp4")
baixar(job["png_url"], "m.png")
g = job["geo"]
falhas = 0
for v in job["variantes"]:
    try:
        cw, ch, cx, cy = g["crop"]
        z = v["zoom"]
        cw2, ch2 = par(cw * (1 - z)), par(ch * (1 - z))
        cx2, cy2 = cx + (cw - cw2) // 2, cy + (ch - ch2) // 2
        larg, alt = g["escala"]
        px, py = g["pos"]
        vf = list(job["delogo"]) + [
            f"crop={cw2}:{ch2}:{cx2}:{cy2}", f"scale={larg}:{alt}:flags=lanczos", "setsar=1",
            f"eq=brightness={v['brilho']}:saturation={v['saturacao']}",
            f"pad={g['L']}:{g['A']}:{px}:{py}:color=0x0a0a0a", "format=yuv420p"]
        F = v["pitch"]
        fc = (f"[0:v]{','.join(vf)}[base];[1:v]format=rgba[m];"
              f"[base][m]overlay=0:0:eof_action=repeat:format=auto,format=yuv420p[v];"
              f"[0:a:0]aresample=48000,asetrate={48000 * F:.1f},aresample=48000,atempo={1 / F:.6f}[a]")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", "in.mp4", "-i", "m.png", "-filter_complex", fc,
                        "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                        "-r", "30", "-c:a", "aac", "-b:a", "160k", "-map_metadata", "-1",
                        "-metadata", f"comment={v['conta']}:{job['code']}",
                        "-fflags", "+bitexact", "-flags:v", "+bitexact", "-flags:a", "+bitexact",
                        "-movflags", "+faststart", "out.mp4"], check=True, timeout=900)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "1.5", "-i", "out.mp4", "-frames:v", "1",
                        "-q:v", "3", "-metadata", f"comment={v['conta']}:{job['code']}", "capa.jpg"], check=True)
        h = sha("out.mp4")
        s3.upload_file("out.mp4", BUCKET, f"reels/{h[:32]}.mp4",
                       ExtraArgs={"ContentType": "video/mp4", "CacheControl": "public, max-age=31536000"})
        hc = sha("capa.jpg")
        s3.upload_file("capa.jpg", BUCKET, f"capas/{hc[:32]}.jpg",
                       ExtraArgs={"ContentType": "image/jpeg", "CacheControl": "public, max-age=31536000"})
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                    "csv=p=0", "out.mp4"], capture_output=True, text=True).stdout.strip())
        res = {"id": v["id"], "url_video": f"{PUB}/reels/{h[:32]}.mp4", "url_capa": f"{PUB}/capas/{hc[:32]}.jpg",
               "sha256": h, "tamanho": os.path.getsize("out.mp4"), "duracao": round(dur, 2)}
        s3.put_object(Bucket=BUCKET, Key=f"semana/res/{v['id']}.json", Body=json.dumps(res).encode(),
                      ContentType="application/json")
        print("ok", v["id"], flush=True)
    except Exception as e:  # noqa: BLE001
        falhas += 1
        print("ERRO", v["id"], e, flush=True)
sys.exit(1 if falhas == len(job["variantes"]) else 0)
