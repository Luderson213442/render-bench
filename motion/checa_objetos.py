r"""Trava de flick POR PEÇA (12/11/2026). python -X utf8 D:\motion-lab-r4\kit-rapido\checa_objetos.py <index.html>
O checa.py mede a tela inteira e não vê uma peça isolada dando ré. Este isola cada id de M.ve(id) (window.SO=id), desliga o
balanço de mão (window.MEDIR=1) e INTERCEPTA os comandos de desenho do canvas: para cada letra, imagem, retângulo e traço registra
a posição e o tamanho REAIS na tela (transformação atual × geometria), quadro a quadro, sem ruído de pixel nem de opacidade.
Reprova:
  FLICK  = ré curta (<=3 q, >=3 px) seguida do movimento maior no sentido contrário (antecipação seca, "ré e volta")
  TREMOR = mais de 1 inversão de sentido no mesmo movimento (vai-volta-vai) com idas e voltas visíveis
  VOLTA  = a peça anda >=8 q num sentido e depois volta >=60% do caminho, e continua na tela (ex.: se endireita e gira de volta)
O elástico aprovado (uma ultrapassagem e assentamento) e o clique com bounce passam. Ids que começam com 'fundo' (textura
periódica) não são medidos. Saída 'objetos: OK' ou 'objetos: REPROVADO (n)'; código 1 se reprovado; 1 linha por objeto."""
import sys, os, pathlib, time, math
from collections import defaultdict
from playwright.sync_api import sync_playwright

T0 = time.time()
html = pathlib.Path(sys.argv[1]).resolve()
ARGS = ['--headless=new', '--enable-gpu', '--ignore-gpu-blocklist', '--use-angle=d3d11',
        '--allow-file-access-from-files', '--disable-web-security']
JS = r"""([id,QS,NBS])=>{window.MEDIR=1;const cv=document.createElement('canvas');cv.width=1080;cv.height=1920;const x=cv.getContext('2d');
 let rec=[],pts=[];const P=CanvasRenderingContext2D.prototype;
 const T=(px,py)=>{const m=x.getTransform();return [m.a*px+m.c*py+m.e,m.b*px+m.d*py+m.f]};
 const sc=()=>{const m=x.getTransform();return Math.sqrt(Math.abs(m.a*m.d-m.b*m.c))};
 const box=ps=>{let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;for(const [u,v] of ps){if(u<x0)x0=u;if(u>x1)x1=u;if(v<y0)y0=v;if(v>y1)y1=v;}return [(x0+x1)/2,(y0+y1)/2,Math.max(1,Math.hypot(x1-x0,y1-y0))]};
 const vis=()=>x.globalAlpha>0.03;
 const wrap=(n,fn)=>{const o=P[n];x[n]=function(...a){fn(...a);return o.apply(x,a)}};
 wrap('beginPath',()=>{pts=[]});wrap('moveTo',(a,b)=>pts.push(T(a,b)));wrap('lineTo',(a,b)=>pts.push(T(a,b)));
 wrap('rect',(a,b,w,h)=>pts.push(T(a,b),T(a+w,b+h)));wrap('arc',(a,b,r)=>pts.push(T(a-r,b-r),T(a+r,b+r)));
 wrap('ellipse',(a,b,rx,ry)=>pts.push(T(a-rx,b-ry),T(a+rx,b+ry)));wrap('arcTo',(a,b,c,d)=>pts.push(T(a,b),T(c,d)));
 wrap('quadraticCurveTo',(a,b,c,d)=>pts.push(T(c,d)));wrap('bezierCurveTo',(a,b,c,d,e,f)=>pts.push(T(e,f)));
 wrap('fill',()=>{if(pts.length&&vis())rec.push(['p'+pts.length,...box(pts)])});wrap('stroke',()=>{if(pts.length&&vis())rec.push(['p'+pts.length,...box(pts)])});   // nº de pontos na chave: traço crescendo não é movimento
 wrap('fillRect',(a,b,w,h)=>{if(vis())rec.push(['r',...box([T(a,b),T(a+w,b+h)])])});
 wrap('fillText',(t,a,b)=>{if(!vis())return;const w=x.measureText(t).width,al=x.textAlign,ox=al==='center'?-w/2:(al==='right'||al==='end')?-w:0;
   const bx=box([T(a+ox,b),T(a+ox+w,b)]);rec.push(['t'+t,bx[0],bx[1],Math.max(1,w*sc())])});
 wrap('drawImage',(im,...a)=>{if(!vis())return;let dx,dy,dw,dh;if(a.length===2){dx=a[0];dy=a[1];dw=im.width;dh=im.height}else if(a.length===4){[dx,dy,dw,dh]=a}else{dx=a[4];dy=a[5];dw=a[6];dh=a[7]}
   rec.push(['i',...box([T(dx,dy),T(dx+dw,dy+dh)])])});
 const quadro=so=>{window.SO=so;rec=[];x.setTransform(1,0,0,1,0,0);x.globalAlpha=1;x.filter='none';return rec};
 const out=[];for(let j=0;j<QS.length;j++){const q=QS[j];let nb=NBS[j];if(nb<0){quadro('__nada__');__draw(x,q);nb=rec.length;}quadro(id);__draw(x,q);
   out.push([q,rec.slice(nb).map(r=>[r[0],Math.round(r[1]*100)/100,Math.round(r[2]*100)/100,Math.round(r[3]*100)/100])])}
 window.SO=undefined;window.MEDIR=0;return out;}"""

def series(frames):
    """chave = tipo/texto + ordem entre os iguais; quebra a série quando a quantidade de iguais muda (identidade incerta)"""
    S = defaultdict(dict); cont_prev = {}
    quebra = defaultdict(set)
    for q, rec in frames:
        cont = defaultdict(int); keys = []
        for r in rec:
            k = f'{r[0]}#{cont[r[0]]}'; cont[r[0]] += 1; keys.append((k, r))
        for k, r in keys:
            S[k][q] = (r[1], r[2], math.log(r[3]))
            base = k.rsplit('#', 1)[0]
            if cont_prev.get(base) != cont[base]: quebra[k].add(q)
        cont_prev = dict(cont)
    return S, quebra

def segs(v, thr):
    out = []
    for i, x in enumerate(v):
        if x is None or abs(x) < thr: continue
        s = 1 if x > 0 else -1
        if out and out[-1][0] == s: out[-1][2] = i; out[-1][3] += x
        else: out.append([s, i, i, x])
    return out

def analisa(nome, S, quebra, cortes, ult):
    falhas = []
    for k, pts in S.items():
        qs = sorted(pts)
        for eixo, rot, thr, amp, ampv in ((0, 'x', 0.8, 3, 25), (1, 'y', 0.8, 3, 25), (2, 'tamanho', 0.004, 0.02, 0.12)):
            # velocidades entre quadros consecutivos válidos
            v = {}; smax = max(p[2] for p in pts.values())
            for a, b in zip(qs, qs[1:]):
                if b != a + 1 or b in quebra[k] or b in cortes or a in cortes: continue
                if min(pts[a][2], pts[b][2]) < smax + math.log(0.35): continue   # nascendo/sumindo (escala ~0): não é trajetória
                v[a] = pts[b][eixo] - pts[a][eixo]
            if not v: continue
            # trechos contínuos de movimento (buracos de até 2 q)
            ks = sorted(v); trecho = []
            def fecha(tr):
                if len(tr) < 2: return
                vv = [v.get(q) for q in range(tr[0], tr[-1] + 1)]
                sg = segs(vv, thr)
                if len(sg) < 2: return
                tam = [abs(s[3]) for s in sg]; dur = [s[2] - s[1] + 1 for s in sg]; q0 = tr[0]
                m = tam.index(max(tam)); amortecido = m <= 1 and all(tam[i + 1] < tam[i] for i in range(m, len(tam) - 1))   # aperta-solta-assenta / ultrapassa e assenta
                if len(sg) > 2 and not amortecido and sorted(tam)[-2] >= amp:
                    falhas.append(f'{nome}:{k} {rot} q{q0+sg[0][1]}-{q0+sg[-1][2]}: TREMOR ({len(sg)-1} inversões {[round(s[3],2) for s in sg]})'); return
                for i in range(len(sg) - 1):
                    qa = q0 + sg[i][1]
                    repouso = all(q in v and abs(v[q]) < thr for q in (qa - 1, qa - 2))
                    escala = max((abs(pts[q + 1][2] - pts[q][2]) for q in range(qa, q0 + sg[i][2] + 1) if q in pts and q + 1 in pts), default=0)
                    # sem repouso medido antes (peça nascendo): só vale como ré se for deslocamento puro, sem escala mudando junto
                    nascendo_ok = (not repouso) and (eixo == 2 or escala > 0.01)
                    if dur[i] <= 3 and tam[i] >= amp and tam[i + 1] >= 3 * tam[i] and (i == 0 or tam[i - 1] < amp) and not nascendo_ok:
                        falhas.append(f'{nome}:{k} {rot} q{q0+sg[i][1]}: FLICK (ré de {dur[i]} q e {round(tam[i],2)} antes da ida de {round(tam[i+1],2)})'); return
                    fim = q0 + sg[i + 1][2]
                    if dur[i] >= 8 and dur[i + 1] >= 4 and tam[i + 1] >= 0.6 * tam[i] and tam[i] >= ampv and max(qs) >= fim + 8:
                        falhas.append(f'{nome}:{k} {rot} q{q0+sg[i][1]}-{fim}: VOLTA (vai {round(tam[i],2)} e volta {round(tam[i+1],2)})'); return
            for q in ks:
                if trecho and q - trecho[-1] > 3: fecha(trecho); trecho = []
                if abs(v[q]) >= thr: trecho.append(q)
            fecha(trecho)
    return falhas

erros = []
with sync_playwright() as p:
    br = p.chromium.launch(args=ARGS if not os.environ.get('CHROME') else ['--headless=new', '--allow-file-access-from-files'], executable_path=os.environ.get('CHROME') or None); pg = br.new_page(viewport={'width': 540, 'height': 960})
    pg.on('pageerror', lambda e: erros.append(str(e)))
    pg.goto(html.as_uri() + '?render')
    try: pg.wait_for_function('window.__pronto', timeout=40000)
    except Exception: raise SystemExit('página não ficou pronta: ' + '; '.join(erros))
    TOTAL, CORTES = pg.evaluate('[TOTAL,CORTES]')
    # --faixa A B: só os quadros [A,B) (portão de uma fatia; a fatia vem com sobra de 60 q em cada ponta)
    FA, FB = (int(sys.argv[sys.argv.index('--faixa') + 1]), int(sys.argv[sys.argv.index('--faixa') + 2])) if '--faixa' in sys.argv else (0, TOTAL + 1)
    FA, FB = max(0, FA), min(TOTAL + 1, FB)
    # onde cada peça existe (M.ve registra o id no quadro em que é chamada): mede só ali, +3 q de margem
    onde = pg.evaluate("""(TOTAL)=>{if(!M.ids)return null;const c=document.createElement('canvas').getContext('2d');const O={};let q=0;
      M.ids={add:id=>{(O[id]=O[id]||[]).push(q)}};for(q=FA;q<FB;q++)__draw(c,q);return O}""".replace('FA', str(FA)).replace('FB', str(FB)), TOTAL)
    ids = list(onde) if onde else None
    NB = dict(zip(range(FA, FB), pg.evaluate(JS.replace('const out=[];', 'const out=[];return QS.map(q=>{quadro("__nada__");__draw(x,q);return rec.length});', 1), ['__nada__', list(range(FA, FB)), []]))) if ids else {}
    if not ids: raise SystemExit('a cena não usa M.ve(id): sem peças isoladas não há garantia. Troque ve() por M.ve().')
    cortes = set()
    for c in CORTES: cortes |= {int(c) - 1, int(c)}
    falhas = []
    medidos = [i for i in ids if not i.startswith('fundo')]
    if '--grupo' in sys.argv:   # k/n: divide as peças entre n processos, pelo nº de quadros em que cada uma existe
        gk, gn = map(int, sys.argv[sys.argv.index('--grupo') + 1].split('/')); cx = [0] * gn; meu = []
        for i in sorted(medidos, key=lambda i: -len(onde[i])):
            b = cx.index(min(cx)); cx[b] += len(onde[i])
            if b == gk: meu.append(i)
        medidos = meu
    for n, i in enumerate(medidos):
        t = time.time()
        qs = sorted({min(FB - 1, max(FA, q + d)) for q in onde[i] for d in range(-3, 4)})
        S, qb = series(pg.evaluate(JS, [i, qs, [NB.get(q, -1) for q in qs]]))
        f = analisa(i, S, qb, cortes, TOTAL); falhas += f
        print(f'  [{n+1}/{len(medidos)}] {i}: {"OK" if not f else "REPROVADO"} ({len(S)} peças, {time.time()-t:.0f}s)', flush=True)
    br.close()
for f in falhas[:60]: print('  ✗', f)
print(f'objetos: {"OK" if not falhas else "REPROVADO ("+str(len(falhas))+")"} | {len(medidos)} objetos, {TOTAL+1} q | {time.time()-T0:.0f}s')
sys.exit(1 if falhas else 0)
