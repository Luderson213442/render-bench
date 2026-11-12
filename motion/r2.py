"""Entrada/saída de uma fatia de motion. Só imprime "ok": arquivos ficam no armazenamento privado (motion-jobs/<JOB>/).
python motion/r2.py baixar          -> in.tar.gz para /tmp/job e o caminho da página em /tmp/job/html.txt
python motion/r2.py enviar <ini>    -> /tmp/out.mp4 e /tmp/out.json como f<ini>.*"""
import json, os, sys, tarfile, boto3
s3 = boto3.client('s3', endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
                  aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'], aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'], region_name='auto')
B, P = os.environ['R2_BUCKET'], f"motion-jobs/{os.environ['JOB']}"
if sys.argv[1] == 'baixar':
    s3.download_file(B, f'{P}/in.tar.gz', '/tmp/in.tar.gz')
    with tarfile.open('/tmp/in.tar.gz') as t: t.extractall('/tmp/job', filter='data')
    os.remove('/tmp/in.tar.gz')
    open('/tmp/job/html.txt', 'w').write(os.path.join('/tmp/job', json.load(open('/tmp/job/job.json'))['html']))
else:
    k = sys.argv[2]
    s3.upload_file('/tmp/out.json', B, f'{P}/f{k}.json')
    s3.upload_file('/tmp/out.mp4', B, f'{P}/f{k}.mp4')   # o .mp4 por último: é o sinal de pronto
print('ok')
