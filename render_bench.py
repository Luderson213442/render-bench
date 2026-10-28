# -*- coding: utf-8 -*-
"""Render do motor real (mesmo grafo do renderizar_frio): cena recortada + moldura PNG + pitch imperceptível.

    python render_bench.py --input in.mp4 --moldura m.png --vf "<filtros>" --pitch 1.01 --output out.mp4
"""
import argparse, subprocess

ap = argparse.ArgumentParser()
ap.add_argument("--input", required=True)
ap.add_argument("--moldura", required=True)
ap.add_argument("--vf", required=True)
ap.add_argument("--pitch", type=float, default=1.0)
ap.add_argument("--output", required=True)
a = ap.parse_args()

F = a.pitch
fc = (f"[0:v]{a.vf}[base];[1:v]format=rgba[m];"
      f"[base][m]overlay=0:0:eof_action=repeat:format=auto,format=yuv420p[v];"
      f"[0:a:0]aresample=48000,asetrate={48000 * F:.1f},aresample=48000,atempo={1 / F:.6f}[a]")
cmd = ["ffmpeg", "-v", "error", "-y", "-i", a.input, "-i", a.moldura,
       "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
       "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", "30",
       "-c:a", "aac", "-b:a", "192k",
       "-map_metadata", "-1", "-fflags", "+bitexact", "-flags:v", "+bitexact", "-flags:a", "+bitexact",
       "-movflags", "+faststart", a.output]
subprocess.run(cmd, check=True)
print("ok", a.output, "pitch", F)
