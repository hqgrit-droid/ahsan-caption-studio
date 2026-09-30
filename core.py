"""Caption validation, interchange and deterministic ASS rendering. Standard library only."""
import json, math, re
from keywords import choose_keyword, keyword_lines

DEFAULT = dict(name='Creator Gold', fontFamily='Arial', fontFile='', fontSize=64, weight=800,
    textColor='#FFFFFF', highlightColor='#F6CF53', outlineColor='#101014', outline=4,
    shadow=2, background=False, backgroundColor='#15151D', position='bottom',
    maxWords=4, uppercase=True, animation='highlight', marginX=60, marginY=110,
    emphasis=False, emphasisScale=1.65, emphasisColor='#F6CF53', emphasisOwnLine=True,
    emphasisFontFamily='', emphasisItalic=False)
STARTERS = [dict(DEFAULT, id='creator-gold'),
    dict(DEFAULT, id='clean-story', name='Clean Story', fontSize=48, weight=400, uppercase=False,
         outline=1, shadow=1, maxWords=7, animation='none', marginY=70),
    dict(DEFAULT, id='midnight-box', name='Midnight Box', fontSize=54, background=True,
         outline=3, shadow=0, highlightColor='#B9A2FF', uppercase=False, maxWords=5),
    dict(DEFAULT,id='reel-punch',name='Reel Punch',fontSize=48,maxWords=3,emphasis=True,
         emphasisScale=1.8,outline=2,animation='none',marginY=210),
    dict(DEFAULT,id='editorial-focus',name='Editorial Focus',fontFamily='Georgia',fontSize=44,
         weight=400,maxWords=3,uppercase=False,outline=0,shadow=1,animation='fade',
         emphasis=True,emphasisScale=2.15,emphasisColor='#C67948',emphasisFontFamily='Georgia',
         emphasisItalic=True,position='middle',marginX=50)]

def number(value, lo, hi):
    value = float(value)
    if not math.isfinite(value) or not lo <= value <= hi:
        raise ValueError('Number must be between %s and %s' % (lo, hi))
    return value

def preset(raw):
    p = dict(DEFAULT)
    for k in p:
        if k in raw: p[k] = raw[k]
    for k, lo, hi in [('fontSize',10,200),('weight',100,900),('outline',0,15),('shadow',0,15),('maxWords',1,20),('marginX',0,400),('marginY',0,800)]:
        p[k] = int(number(p[k], lo, hi))
    p['emphasisScale']=number(p['emphasisScale'],1.1,3)
    for k in ['textColor','highlightColor','outlineColor','backgroundColor','emphasisColor']:
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', str(p[k])): raise ValueError('Invalid color')
    for k, allowed in [('position',['top','middle','bottom']),('animation',['none','highlight','fade'])]:
        if p[k] not in allowed: raise ValueError('Invalid '+k)
    for k in ['name','fontFamily','emphasisFontFamily']:
        p[k] = str(p[k]).strip()
        if (not p[k] and k!='emphasisFontFamily') or len(p[k]) > 100 or any(c in p[k] for c in ',\n\r{}\\'): raise ValueError('Invalid '+k)
    if not re.fullmatch(r'(?:[a-f0-9]{32}\.(?:ttf|otf))?', str(p['fontFile'])): raise ValueError('Invalid font file')
    for k in ['background','uppercase','emphasis','emphasisOwnLine','emphasisItalic']:p[k]=bool(p[k])
    return p

def captions(items):
    if not isinstance(items, list) or len(items)>20000: raise ValueError('Expected up to 20,000 captions')
    result=[]
    for item in items:
        start=number(item['start'],0,86400); end=number(item['end'],0,86400)
        text=str(item['text']).strip()
        if end <= start: raise ValueError('Caption end must be after start')
        if not text or len(text)>4000: raise ValueError('Caption text must contain 1–4000 characters')
        row=dict(start=start,end=end,text=text)
        if item.get('style'):
            raw=item['style']
            if not isinstance(raw,dict): raise ValueError('Invalid caption style')
            own={}
            if 'fontSize' in raw: own['fontSize']=int(number(raw['fontSize'],10,200))
            if 'fontFamily' in raw:
                family=str(raw['fontFamily']).strip()
                if not family or len(family)>100 or any(c in family for c in ',\n\r{}\\'):
                    raise ValueError('Invalid caption font')
                own['fontFamily']=family
            if 'fontFile' in raw:
                file=str(raw['fontFile'])
                if not re.fullmatch(r'[a-f0-9]{32}\.(?:ttf|otf)',file):raise ValueError('Invalid caption font file')
                own['fontFile']=file
            for axis in ('x','y'):
                if axis in raw: own[axis]=number(raw[axis],0,100)
            if own:row['style']=own
        if 'emphasisWord' in item:
            choice=item['emphasisWord']
            if not isinstance(choice,int) or not -1<=choice<len(text.split()):raise ValueError('Main-word selection is out of range')
            row['emphasisWord']=choice
        if item.get('sourceText'):row['sourceText']=str(item['sourceText'])[:4000]
        words=item.get('words',[])
        if words:
            cleaned=[]; last=start
            for w in words:
                a=number(w['start'],start,end); b=number(w['end'],a,end)
                if a < last or b <= a: raise ValueError('Word timings must be ordered and non-overlapping')
                cleaned.append(dict(start=a,end=b,text=str(w['text']).strip())); last=b
            if [w['text'] for w in cleaned] != text.split(): raise ValueError('Word timings must match caption text')
            row['words']=cleaned
        result.append(row)
    result.sort(key=lambda c:c['start'])
    for prev,cur in zip(result,result[1:]):
        if cur['start'] < prev['end']-0.001: raise ValueError('Captions overlap; adjust their start/end times')
    return result

def word_times(c):
    if c.get('words'): return c['words']
    words=c['text'].split(); step=(c['end']-c['start'])/len(words)
    return [dict(text=t,start=c['start']+i*step,end=c['start']+(i+1)*step) for i,t in enumerate(words)]

def stamp(s):
    parts=s.replace(',','.').split(':')
    if len(parts) not in (2,3): raise ValueError('Invalid subtitle timestamp')
    return sum(float(v)*60**i for i,v in enumerate(reversed(parts)))

def parse_import(text, ext):
    if ext == '.json':
        obj=json.loads(text.lstrip('\ufeff')); return captions(obj.get('captions',[]) if isinstance(obj,dict) else obj)
    rows=[]
    for block in re.split(r'\n\s*\n', text.replace('\r','').lstrip('\ufeff').strip()):
        lines=block.splitlines()
        for i,line in enumerate(lines):
            if '-->' in line:
                a,b=line.split('-->',1)
                body=' '.join(lines[i+1:]); body=re.sub(r'<[^>]*>','',body)
                rows.append(dict(start=stamp(a.strip()),end=stamp(b.strip().split()[0]),text=body)); break
    if not rows: raise ValueError('No timed captions found; import SRT, VTT or caption JSON')
    return captions(rows)

def clock(s, ass=False):
    ticks=round(s*(100 if ass else 1000)); rate=100 if ass else 1000
    seconds,fraction=divmod(ticks,rate); minutes,sec=divmod(seconds,60); hour,minute=divmod(minutes,60)
    return f'{hour}:{minute:02}:{sec:02}.{fraction:02}' if ass else f'{hour:02}:{minute:02}:{sec:02},{fraction:03}'

def srt(rows):
    return '\n\n'.join(f'{i+1}\n{clock(c["start"])} --> {clock(c["end"])}\n{c["text"]}' for i,c in enumerate(rows))+'\n'

def color(hex): return '&H00'+hex[5:7]+hex[3:5]+hex[1:3]
def safe(text): return text.replace('\\','＼').replace('{','｛').replace('}','｝').replace('\n',' ')

def ass(rows, p, width, height):
    p=preset(p)
    # All style sizes use a 1080-high reference canvas, shared with browser preview.
    h=1080; w=round(width/height*h); align={'bottom':2,'middle':5,'top':8}[p['position']]
    mx=min(p['marginX'],int(w*.4)); my=min(p['marginY'],450)
    styles=[]
    for name,box in [('Default',False),('Box',True)]:
        styles.append(f'Style: {name},{p["fontFamily"]},{p["fontSize"]},{color(p["textColor"])},{color(p["textColor"])},{color(p["backgroundColor"] if box else p["outlineColor"])},{color(p["backgroundColor"])},{-1 if p["weight"]>=600 else 0},0,0,0,100,100,0,0,{3 if box else 1},{max(4,p["outline"]) if box else p["outline"]},{0 if box else p["shadow"]},{align},{mx},{mx},{my},1')
    header=f'''[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
'''+ '\n'.join(styles)+'''

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    events=[]
    for c in rows:
        own=c.get('style',{})
        cp=dict(p,**own)
        custom_pos=''
        if 'x' in own or 'y' in own:
            default_y=540 if p['position']=='middle' else my if p['position']=='top' else h-my
            x=round(w*own.get('x',50)/100)
            y=round(h*own.get('y',default_y/h*100)/100)
            custom_pos=f'\\an5\\pos({x},{y})'
        cue_tags=''
        if 'fontFamily' in own:cue_tags+='\\fn'+cp['fontFamily']
        if 'fontSize' in own:cue_tags+='\\fs'+str(cp['fontSize'])
        cue_tags+=custom_pos
        words=word_times(c)
        selected=choose_keyword(c) if p['emphasis'] else -1
        groups=keyword_lines(len(words),selected,p['maxWords'],p['emphasisOwnLine'] and selected>=0)
        line_starts={group[0] for group in groups}
        boundaries=sorted(set([c['start'],c['end']]+[v for word in words for v in (word['start'],word['end'])])) if p['animation']=='highlight' else [c['start'],c['end']]
        for a,b in zip(boundaries,boundaries[1:]):
            pieces=[]
            for i,word in enumerate(words):
                t=safe(word['text'].upper() if p['uppercase'] else word['text'])
                active=p['animation']=='highlight' and word['start'] <= (a+b)/2 < word['end']
                ink=p['highlightColor'] if active else p['emphasisColor'] if i==selected else p['textColor']
                tags='\\c'+color(ink)+'&'
                if i==selected:
                    tags+='\\fs'+str(round(cp['fontSize']*p['emphasisScale']))
                    if p['emphasisFontFamily']:tags+='\\fn'+p['emphasisFontFamily']
                    if p['emphasisItalic']:tags+='\\i1'
                reset='\\fs'+str(cp['fontSize'])+'\\fn'+cp['fontFamily']+'\\i0\\c'+color(p['textColor'])+'&'
                t='{'+tags+'}'+t+'{'+reset+'}'
                pieces.append(('\\N' if i and i in line_starts else ' ' if i else '')+t)
            body=''.join(pieces)
            if p['animation']=='fade': body='{\\fad(120,120)}'+body
            if cue_tags:body='{'+cue_tags+'}'+body
            if p['background']:
                events.append(f'Dialogue: 0,{clock(a,True)},{clock(b,True)},Box,,0,0,0,,{body}')
            events.append(f'Dialogue: 1,{clock(a,True)},{clock(b,True)},Default,,0,0,0,,{body}')
    return header+'\n'.join(events)+'\n'
