#!/usr/bin/env python3
"""📒 便利帳 → 便利ノート（暗号化して data/benricho.enc に公開）。
  python3 tools/publish_benricho.py [--no-push] [--dry-run]
入力: /workspace/みんなの便利帳/みんなの便利帳.md（## 日付 → 【種類】内容 / ## 予約・申込・リマインダー / ## フレンド募集サイト / ## 今朝の通話から）
「## みんなの思い出」節は思い出ページ側なのでここでは出さない。日付の暗号化と同じ鍵（index.json の salt・passphrase.txt）を使う。"""
import os,re,sys,json,base64,secrets,subprocess,datetime
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from publish import derive,ITER,b64,load_index,apply_muted
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
REPO=os.path.dirname(os.path.dirname(os.path.abspath(__file__)));MD='/workspace/みんなの便利帳/みんなの便利帳.md';PF='/workspace/benri-note-secret/passphrase.txt'
a=sys.argv[1:]
t=open(MD).read()
secs=[(s.split('\n')[0].strip(),[l[2:].strip() for l in s.split('\n')[1:] if l.startswith('- ')]) for s in re.split(r'^## ',t,flags=re.M)[1:]]
dated=[[k,v] for k,v in secs if re.match(r'\d{4}-\d\d-\d\d',k)];other={k:v for k,v in secs if not re.match(r'\d{4}-\d\d-\d\d',k)}
get=lambda p:next((v for k,v in other.items() if k.startswith(p)),[])
# muted.json の言葉は便利帳にも出さない
def mute(xs):
    e={'sections':[{'items':[{'title':x} for x in xs]}]};apply_muted(e);return [i['title'] for i in e['sections'][0]['items']]
now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec='minutes')
B={'v':1,'generated':now,'call':mute(get('今朝')),'rem':mute(get('予約')),'dated':[[k,mute(v)] for k,v in dated],
   'pik':mute([i for _,v in dated for i in v if '【ピクミン】' in i]),'sites':mute(get('フレンド'))}
print(f"便利帳: 通話{len(B['call'])} 予約{len(B['rem'])} 日付{len(B['dated'])} ピクミン{len(B['pik'])} サイト{len(B['sites'])}")
if '--dry-run' in a:sys.exit()
idx=load_index(os.path.join(REPO,'data','index.json'));pw=open(PF).read().strip()
salt=base64.b64decode(idx['kdf']['salt']);iv=secrets.token_bytes(12);aad='benri-note:benricho'
ct=AESGCM(derive(pw,salt)).encrypt(iv,json.dumps(B,ensure_ascii=False).encode(),aad.encode())
json.dump({'v':1,'alg':'AES-GCM','kdf':'PBKDF2-SHA256','iter':ITER,'salt':idx['kdf']['salt'],'iv':b64(iv),'aad':aad,'ct':b64(ct)},open(os.path.join(REPO,'data','benricho.enc'),'w'))
if '--no-push' not in a:
    subprocess.run(['git','-C',REPO,'add','data/benricho.enc'],check=True)
    if subprocess.run(['git','-C',REPO,'diff','--cached','--quiet']).returncode:
        subprocess.run(['git','-C',REPO,'commit','-qm','便利帳 update','--','data/benricho.enc'],check=True);subprocess.run(['git','-C',REPO,'push','-q'],check=True);print('pushed')
