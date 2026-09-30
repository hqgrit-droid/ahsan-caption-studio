#!/usr/bin/env python3
"""Caption studio: localhost by default, optional authenticated cloud mode."""
import argparse, base64, binascii, copy, hmac, importlib.util, json, mimetypes, os, re, secrets, shutil, subprocess, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from core import DEFAULT, STARTERS, preset, captions, parse_import, ass, srt
from keywords import STOPWORDS, IMPACT_WORDS
from fusion_import import import_fusion
from cloud_transcription import transcribe_cloud, MODEL as CLOUD_MODEL
from roman_urdu import romanize_captions, validate_spellings
from cloud_store import CloudStore, configured as cloud_configured
from fonts import system_font_families, font_family_from_file

ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get('CAPTION_DATA',str(ROOT/'data'))).resolve()
REMOTE_HOST=(os.environ.get('CAPTION_REMOTE_HOST') or os.environ.get('RENDER_EXTERNAL_HOSTNAME','')).strip().lower()
if REMOTE_HOST and (not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?',REMOTE_HOST)
                    or '..' in REMOTE_HOST or '.' not in REMOTE_HOST or len(REMOTE_HOST)>253):
    raise ValueError('CAPTION_REMOTE_HOST must be one exact DNS hostname')
for part in ['media','fonts','exports','projects']: (DATA/part).mkdir(parents=True,exist_ok=True)
STORE=CloudStore(DATA) if cloud_configured() else None
if STORE:
    if not REMOTE_HOST or not os.environ.get('CAPTION_SITE_USER') or not os.environ.get('CAPTION_SITE_PASSWORD'):
        raise ValueError('Cloud storage requires an exact remote hostname and site username/password')
    STORE.restore_metadata()
os.environ.setdefault('HF_HOME',str(DATA/'models'/'hub-cache'))
os.environ.setdefault('HF_HUB_DISABLE_TELEMETRY','1')
os.environ.setdefault('HF_HUB_DISABLE_XET','1')
KEY_FILE=DATA/'.gemini-api-key'
SHARE_FILE=DATA/'.share-session.json'
def share_session():
    if STORE or not SHARE_FILE.exists(): return None
    try:
        session=json.loads(SHARE_FILE.read_text())
        host=session.get('host','')
        if (re.fullmatch(r'[a-z0-9-]+\.trycloudflare\.com',host)
                and session.get('username') and session.get('password')):
            return session
    except (OSError,ValueError,TypeError): pass
    return None

def load_cloud_key():
    if os.environ.get('GEMINI_API_KEY'): return os.environ['GEMINI_API_KEY']
    return KEY_FILE.read_text().strip() if not STORE and KEY_FILE.exists() else ''

def save_cloud_key(key):
    global CLOUD_KEY
    if not isinstance(key,str) or len(key)>256 or any(c.isspace() for c in key):
        raise ValueError('Invalid API key format.')
    if not STORE:
        if key:
            tmp=KEY_FILE.with_name(KEY_FILE.name+'.'+secrets.token_hex(8)+'.tmp')
            try:
                fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                with os.fdopen(fd,'w') as output: output.write(key)
                os.replace(tmp,KEY_FILE)
            finally:
                tmp.unlink(missing_ok=True)
        else: KEY_FILE.unlink(missing_ok=True)
    CLOUD_KEY=key
    return bool(key)

CLOUD_KEY=load_cloud_key()
LOCK=threading.RLock(); JOBS={}; TOKEN=secrets.token_hex(24)
FFMPEG=os.environ.get('FFMPEG') or shutil.which('ffmpeg')

def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else copy.deepcopy(default)

def write(path,obj):
    tmp=path.with_suffix('.tmp')
    try:
        tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2))
        if STORE: STORE.upload(tmp, STORE.key(path))
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)

def delete_preset(preset_id):
    if not isinstance(preset_id,str) or not preset_id or len(preset_id)>64:
        raise ValueError('Choose a style to delete.')
    with LOCK:
        items=read(DATA/'presets.json',STARTERS)
        remaining=[item for item in items if item.get('id')!=preset_id]
        if len(remaining)==len(items): raise ValueError('Style not found. Reload the page and try again.')
        write(DATA/'presets.json',remaining)
    return dict(deleted=preset_id)

def available_fonts():
    known={}
    for item in read(DATA/'presets.json',STARTERS):
        if item.get('fontFile'): known[item['fontFile']]=item.get('fontFamily','')
    for file in (DATA/'projects').glob('*.json'):
        item=read(file)
        styles=[item.get('style',{})]+[cue.get('style',{}) for cue in item.get('captions',[])]
        for style in styles:
            if style.get('fontFile'): known[style['fontFile']]=style.get('fontFamily','')
    files={p.name for p in (DATA/'fonts').iterdir() if p.suffix.lower() in ('.ttf','.otf')}
    uploaded=[]
    for filename in sorted(files|set(known)):
        if not re.fullmatch(r'[a-f0-9]{32}\.(?:ttf|otf)',filename): continue
        path=DATA/'fonts'/filename
        family=(font_family_from_file(path) if path.exists() else None) or known.get(filename) or 'Uploaded font'
        uploaded.append(dict(file=filename,family=family))
    return dict(system=system_font_families(),uploaded=uploaded)

def local_file(path):
    return STORE.download(path) if STORE else path

def ident(value):
    if not re.fullmatch('[a-f0-9]{32}',str(value)): raise ValueError('Invalid identifier')
    return value

def project(pid):
    p=DATA/'projects'/(ident(pid)+'.json')
    if not p.exists(): raise ValueError('Project not found')
    return read(p)

def save_project(p):
    p['updated']=time.time()
    with LOCK: write(DATA/'projects'/(p['id']+'.json'),p)

def ffcheck():
    if not FFMPEG: return False
    try: return ' ass ' in subprocess.run([FFMPEG,'-hide_banner','-filters'],capture_output=True,text=True,timeout=10).stdout
    except (OSError,subprocess.SubprocessError): return False

HAS_ASS=ffcheck()
if not HAS_ASS and not os.environ.get('FFMPEG'):
    try:
        import imageio_ffmpeg
        FFMPEG=imageio_ffmpeg.get_ffmpeg_exe()
        HAS_ASS=ffcheck()
    except (ImportError,RuntimeError): pass

def run_job(fn):
    jid=uuid.uuid4().hex
    with LOCK: JOBS[jid]=dict(status='running',message='Starting…')
    def update(message):
        with LOCK: JOBS[jid]['message']=message
    def work():
        try:
            result=fn(update)
            with LOCK: JOBS[jid].update(status='done',result=result,message='Complete')
        except Exception as e:
            with LOCK: JOBS[jid].update(status='error',message=str(e)[-2500:])
    threading.Thread(target=work,daemon=True).start()
    return dict(job=jid)

def export_job(p, update):
    if not HAS_ASS: raise ValueError('FFmpeg with libass is required. See README setup instructions, then restart the app.')
    rows=captions(p['captions']); style=preset(p['style'])
    if not rows: raise ValueError('Add or import captions before exporting')
    font_files={style['fontFile']} if style['fontFile'] else set()
    font_files.update(c.get('style',{}).get('fontFile') for c in rows if c.get('style',{}).get('fontFile'))
    for filename in font_files:
        font=DATA/'fonts'/filename
        try: local_file(font)
        except Exception: raise ValueError('Custom font missing. Upload it again, or choose Use system font.')
        if not font.exists(): raise ValueError('Custom font missing. Upload it again, or choose Use system font.')
    if STORE: update('Fetching video from private storage…')
    local_file(DATA/'media'/p['media'])
    eid=uuid.uuid4().hex; out=DATA/'exports'/eid; out.mkdir()
    (out/'captions.ass').write_text(ass(rows,style,p['width'],p['height']))
    (out/'captions.srt').write_text(srt(rows))
    update('Burning captions into MP4…')
    cmd=[FFMPEG,'-hide_banner','-y','-i',str(DATA/'media'/p['media']),'-map','0:v:0','-map','0:a:0?',
        '-filter_threads','1' if STORE else str(min(os.cpu_count() or 4,8)),
        '-vf','scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1,ass=captions.ass:fontsdir=../../fonts',
        '-c:v','libx264','-threads','1' if STORE else str(min(os.cpu_count() or 4,8)),
        '-preset','ultrafast' if STORE else 'veryfast','-crf','20','-pix_fmt','yuv420p',
        '-c:a','aac','-b:a','192k','-movflags','+faststart','captioned.mp4']
    with (out/'render.log').open('w') as log:
        result=subprocess.run(cmd,cwd=out,stdout=log,stderr=log)
    if result.returncode: raise ValueError('FFmpeg export failed: '+(out/'render.log').read_text()[-1800:])
    if STORE:
        update('Saving MP4 and subtitles to private cloud storage…')
        STORE.upload(out/'captioned.mp4')
        STORE.upload(out/'captions.srt')
    return dict(url=f'/files/exports/{eid}/captioned.mp4',srt=f'/files/exports/{eid}/captions.srt')

def transcribe_job(p, model, language, update):
    try: from faster_whisper import WhisperModel
    except ImportError: raise ValueError('Local Whisper is not installed. Run the optional transcription setup in README, then restart.')
    if model not in ['tiny','base','small','medium']: raise ValueError('Unknown model')
    update('Loading local Whisper model. First use downloads model weights; this can take a few minutes…')
    engine=WhisperModel(model,device='cpu',compute_type='int8',cpu_threads=max(1,min(os.cpu_count() or 4,8)),download_root=str(DATA/'models'))
    update('Transcribing locally with word timings…')
    roman=language=='ur-Latn'
    segments,info=engine.transcribe(str(local_file(DATA/'media'/p['media'])),word_timestamps=True,language='ur' if roman else language or None, beam_size=5, vad_filter=True, condition_on_previous_text=False)
    rows=[]
    for segment in segments:
        words=[]
        for word in segment.words or []:
            tokens=word.word.strip().split()
            duration=max(.01,word.end-word.start)
            for i,t in enumerate(tokens):
                words.append(dict(text=t,start=word.start+duration*i/len(tokens),end=word.start+duration*(i+1)/len(tokens)))
        # Short cues are easier to read and keep mobile previews uncluttered.
        for i in range(0,len(words),6):
            group=words[i:i+6]
            for j,w in enumerate(group):
                if j: w['start']=max(w['start'],group[j-1]['end'])
                w['end']=max(w['end'],w['start']+.01)
            if rows and group[0]['start'] < rows[-1]['end']:
                shift=rows[-1]['end']-group[0]['start']
                for w in group: w['start']+=shift; w['end']+=shift
            rows.append(dict(start=group[0]['start'],end=group[-1]['end'],text=' '.join(w['text'] for w in group),words=group))
        update(f'Transcribed through {segment.end:.0f}s…')
    if not rows: raise ValueError('No speech found. Try another language/model or import captions.')
    result=romanize_captions(captions(rows),read(DATA/'roman-spellings.json',{})) if roman else dict(captions=captions(rows))
    result['language']='ur-Latn' if roman else info.language
    return result

class AuthenticationRequired(Exception):
    pass

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def send_json(self,obj,status=200):
        raw=json.dumps(obj,ensure_ascii=False).encode(); self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(raw))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(raw)
    def body(self):
        size=int(self.headers.get('Content-Length','0'))
        if size>15*1024*1024: raise ValueError('Request too large')
        return json.loads(self.rfile.read(size))
    def guard(self, mutation=False):
        host=self.headers.get('Host','').lower()
        allowed={f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
        if REMOTE_HOST: allowed.update({REMOTE_HOST,f'{REMOTE_HOST}:443'})
        sharing=share_session()
        shared=bool(sharing and host in (sharing['host'],sharing['host']+':443'))
        if shared: allowed.update({sharing['host'],sharing['host']+':443'})
        if host not in allowed: raise ValueError('Invalid host; open the localhost or configured HTTPS URL')
        if STORE or shared:
            auth=self.headers.get('Authorization','')
            try:
                scheme, encoded=auth.split(' ',1)
                credentials=base64.b64decode(encoded,validate=True).decode('utf-8')
                username,password=credentials.split(':',1)
            except (ValueError,UnicodeError,binascii.Error):
                raise AuthenticationRequired
            expected_user=os.environ.get('CAPTION_SITE_USER','') if STORE else sharing['username']
            expected_password=os.environ.get('CAPTION_SITE_PASSWORD','') if STORE else sharing['password']
            if scheme.lower()!='basic' or not (hmac.compare_digest(username,expected_user)
                                                    and hmac.compare_digest(password,expected_password)):
                raise AuthenticationRequired
        if mutation and self.headers.get('X-Studio-Token')!=TOKEN: raise ValueError('Session expired. Reload the page.')
    def send_auth(self):
        self.send_response(401)
        self.send_header('WWW-Authenticate','Basic realm="Ahsan Caption Studio", charset="UTF-8"')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length','0')
        self.end_headers()
    def send_health(self):
        raw=b'<!doctype html><meta http-equiv="refresh" content="0;url=/app"><a href="/app">Open Caption Studio</a>'
        self.send_response(200)
        self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        self.wfile.write(raw)
    def do_GET(self):
        try:
            path=urlparse(self.path).path
            if STORE and path=='/': return self.send_health()
            self.guard()
            if path=='/api/state':
                with LOCK:
                    presets=read(DATA/'presets.json',STARTERS)
                    presets=[dict(preset(p),id=p.get('id','')) for p in presets]
                    projects=[dict(id=p['id'],name=p['name'],updated=p.get('updated',0)) for p in [read(f) for f in (DATA/'projects').glob('*.json')]]
                return self.send_json(dict(token=TOKEN,cloudStorage=bool(STORE),cloudReady=bool(CLOUD_KEY),cloudModel=CLOUD_MODEL,romanSpellings=read(DATA/'roman-spellings.json',{}),presets=presets,projects=sorted(projects,key=lambda p:-p['updated']),ffmpeg=HAS_ASS,whisper=importlib.util.find_spec('faster_whisper') is not None,roman=importlib.util.find_spec('uroman') is not None,defaults=DEFAULT,keywordRules=dict(stopwords=sorted(STOPWORDS),impactWords=sorted(IMPACT_WORDS))))
            if path=='/api/fonts':
                with LOCK: fonts=available_fonts()
                return self.send_json(fonts)
            if path.startswith('/api/projects/'):
                p=project(path.rsplit('/',1)[1]);p['style']=preset(p['style']);return self.send_json(p)
            if path.startswith('/api/jobs/'):
                with LOCK: job=copy.deepcopy(JOBS.get(path.rsplit('/',1)[1]))
                if not job: raise ValueError('Job not found (server may have restarted)')
                return self.send_json(job)
            if path.startswith('/files/'):
                file=(DATA/path[len('/files/'):]).resolve()
                if not file.is_relative_to(DATA) or file.suffix.lower() not in ['.mp4','.mov','.m4v','.webm','.mkv','.ttf','.otf','.srt']: raise ValueError('File unavailable')
            else:
                file=(ROOT/'static'/('index.html' if path in ('/','/app') else path.lstrip('/'))).resolve()
                if not file.is_relative_to(ROOT/'static'): raise ValueError('Invalid path')
            return self.send_file(file)
        except AuthenticationRequired: self.send_auth()
        except (ValueError,KeyError,TypeError) as e: self.send_json(dict(error=str(e)),400)
        except FileNotFoundError: self.send_json(dict(error='File not found'),404)
        except (BrokenPipeError,ConnectionResetError): pass
        except Exception as e: self.send_json(dict(error=str(e)),500)
    def send_file(self,file):
        remote=STORE and not file.exists() and file.is_relative_to(DATA)
        size=int(STORE.head(file)['ContentLength']) if remote else file.stat().st_size
        start=0; end=size-1; status=200
        requested=self.headers.get('Range')
        if requested:
            match=re.fullmatch(r'bytes=(\d*)-(\d*)',requested)
            if not match: raise ValueError('Invalid range')
            a,b=match.groups()
            if a: start=int(a); end=min(int(b) if b else end,end)
            elif b: start=max(0,size-int(b))
            if start>end or start>=size:
                self.send_response(416); self.send_header('Content-Range',f'bytes */{size}'); self.end_headers(); return
            status=206
        self.send_response(status); self.send_header('Content-Type',mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
        self.send_header('Accept-Ranges','bytes'); self.send_header('Content-Length',str(end-start+1)); self.send_header('Cache-Control','no-cache')
        if status==206: self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.end_headers()
        stream=STORE.open_range(file,start,end) if remote else file.open('rb')
        try:
            if not remote: stream.seek(start)
            remaining=end-start+1
            while remaining:
                chunk=stream.read(min(1024*1024,remaining))
                if not chunk: break
                self.wfile.write(chunk); remaining-=len(chunk)
        finally:
            stream.close()
    def do_POST(self):
        try:
            self.guard(True); parsed=urlparse(self.path); path=parsed.path
            if path=='/api/upload': return self.send_json(self.upload(parse_qs(parsed.query)))
            body=self.body()
            if path=='/api/presets':
                p=preset(body); p['id']=uuid.uuid4().hex
                with LOCK:
                    items=read(DATA/'presets.json',STARTERS); items.append(p); write(DATA/'presets.json',items)
                return self.send_json(p)
            if path=='/api/delete-preset':
                return self.send_json(delete_preset(body.get('id')))
            if path=='/api/import-style':
                ext=Path(body['name']).suffix.lower()
                if ext in ['.setting','.comp']:return self.send_json(import_fusion(body['text'],body['name']))
                if ext!='.json':raise ValueError('Import a preset .json or Fusion .setting / .comp file')
                raw=json.loads(body['text'].lstrip('\ufeff'))
                if not isinstance(raw,dict) or not any(k in raw for k in ['fontFamily','fontSize','textColor']):raise ValueError('This JSON is not a Caption Studio preset. Lottie/After Effects JSON is not supported.')
                return self.send_json(dict(source='json',candidates=[dict(node=raw.get('name','Imported style'),style=preset(raw),mapped=['Caption Studio style settings'],warnings=[])]))
            if path=='/api/cloud-key':
                return self.send_json(dict(ready=save_cloud_key(body.get('key',''))))
            if path=='/api/roman-spellings':
                entries=validate_spellings(body.get('spellings',{}))
                with LOCK:write(DATA/'roman-spellings.json',entries)
                return self.send_json(dict(spellings=entries))
            if path=='/api/romanize':return self.send_json(romanize_captions(captions(body['captions']),read(DATA/'roman-spellings.json',{})))
            if path=='/api/import': return self.send_json(dict(captions=parse_import(body['text'],body['ext'])))
            if path=='/api/save':
                with LOCK:
                    p=project(body['id'])
                    expected=body.get('expectedUpdated')
                    if expected is not None and expected!=p.get('updated'):
                        raise ValueError('This project changed on another device. Download your caption JSON, then reopen the project before editing.')
                    p['captions']=captions(body['captions']); p['style']=preset(body['style']); p['language']=str(body.get('language',p.get('language',''))); save_project(p)
                return self.send_json(p)
            if path in ['/api/export','/api/transcribe']:
                p=project(body['id'])
                if path=='/api/export': return self.send_json(run_job(lambda u:export_job(p,u)))
                provider=body.get('provider','local')
                if provider=='gemini':
                    key=CLOUD_KEY
                    if not key:raise ValueError('Add your Gemini API key in Cloud setup first.')
                    return self.send_json(run_job(lambda u:transcribe_cloud(local_file(DATA/'media'/p['media']),FFMPEG,key,float(p['duration']),body.get('language','ur-Latn'),u,read(DATA/'roman-spellings.json',{}))))
                if provider!='local':raise ValueError('Unknown transcription provider')
                return self.send_json(run_job(lambda u:transcribe_job(p,body.get('model','small'),body.get('language',''),u)))
            raise ValueError('Unknown action')
        except AuthenticationRequired: self.send_auth()
        except (ValueError,KeyError,TypeError,json.JSONDecodeError) as e: self.send_json(dict(error=str(e)),400)
        except Exception as e: self.send_json(dict(error=str(e)),500)
    def upload(self,query):
        name=query.get('name',['upload'])[0]; kind=query.get('kind',['video'])[0]; ext=Path(name).suffix.lower()
        if kind not in ['font','video']: raise ValueError('Unknown upload type')
        allowed=['.ttf','.otf'] if kind=='font' else ['.mp4','.mov','.m4v','.webm','.mkv']
        if ext not in allowed: raise ValueError('Supported formats: '+', '.join(allowed))
        size=int(self.headers.get('Content-Length','0')); limit=20*1024**2 if kind=='font' else 4*1024**3
        if size<=0 or size>limit: raise ValueError('Empty file or file too large (video limit 4 GB; font limit 20 MB)')
        uid=uuid.uuid4().hex; filename=uid+ext; dest=DATA/('fonts' if kind=='font' else 'media')/filename
        try:
            with dest.open('wb') as f:
                remaining=size
                while remaining:
                    chunk=self.rfile.read(min(1024*1024,remaining))
                    if not chunk: raise ValueError('Upload interrupted')
                    f.write(chunk); remaining-=len(chunk)
            if kind=='font':
                with dest.open('rb') as f: signature=f.read(4)
                if signature not in [b'\x00\x01\x00\x00',b'OTTO',b'true']: raise ValueError('Not a valid TTF/OTF font')
                family=font_family_from_file(dest)
                if STORE: STORE.upload(dest)
                return dict(fontFile=filename,fontFamily=family,url='/files/fonts/'+filename)
            width=int(query.get('width',['0'])[0]); height=int(query.get('height',['0'])[0]); duration=float(query.get('duration',['0'])[0])
            if not (1<=width<=16384 and 1<=height<=16384 and 0<duration<=86400): raise ValueError('Browser could not read this video; convert to H.264 MP4 first')
            p=dict(id=uid,name=Path(name).name,media=filename,width=width,height=height,duration=duration,captions=[],style=preset(STARTERS[0]))
            if STORE: STORE.upload(dest)
            save_project(p); return p
        except Exception:
            dest.unlink(missing_ok=True); raise

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--port',type=int,default=int(os.environ.get('PORT','8765'))); args=parser.parse_args()
    bind='0.0.0.0' if STORE else '127.0.0.1'
    server=ThreadingHTTPServer((bind,args.port),Handler)
    print(f'Ahsan Caption Studio → {"https://"+REMOTE_HOST if REMOTE_HOST else "http://127.0.0.1:"+str(args.port)}',flush=True)
    print(f'Local data: {DATA}\nFFmpeg captions: {HAS_ASS}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: server.server_close()
