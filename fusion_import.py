"""Read static Text+ values from Fusion text files without executing Lua or expressions.

This is a deliberately bounded importer, not a Fusion renderer. Quoted strings and
comments are masked before structural scanning; only literal Input.Value data is read.
"""
import json, re
from pathlib import Path
from core import DEFAULT, preset

NUMBER=r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?'

def mask_source(text):
    pattern=r'--\[\[.*?\]\]|--[^\n]*|\[\[.*?\]\]|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\''
    return re.sub(pattern,lambda m:' '*len(m.group()),text,flags=re.S)

def block_end(mask,start):
    depth=0
    for i in range(start,len(mask)):
        if mask[i]=='{':depth+=1
        elif mask[i]=='}':
            depth-=1
            if depth==0:return i
    raise ValueError('Incomplete Fusion file: unmatched braces')

def blocks(text, pattern):
    masked=mask_source(text)
    for m in re.finditer(pattern,masked):
        start=masked.find('{',m.start(),m.end())
        end=block_end(masked,start)
        yield m,text[start+1:end]

def literal(body):
    masked=mask_source(body);m=re.search(r'\bValue\s*=\s*',masked)
    if not m:return None
    value=body[m.end():].lstrip()
    # Masking consumes quoted contents as spaces, so locate '=' in original span.
    value=body[masked.find('=',m.start())+1:].lstrip()
    if value.startswith('"'):
        match=re.match(r'"(?:\\.|[^"\\])*"',value,re.S)
        if not match:return None
        try:return json.loads(match.group())
        except ValueError:return None
    if value.startswith("'"):
        match=re.match(r"'((?:\\.|[^'\\])*)'",value,re.S)
        return match.group(1).replace("\\'", "'").replace('\\\\','\\') if match else None
    match=re.match('('+NUMBER+r')\s*(?:,|$)',value)
    if match:return float(match.group(1))
    if re.match(r'true\s*(?:,|$)',value):return True
    if re.match(r'false\s*(?:,|$)',value):return False
    match=re.match(r'\{\s*('+NUMBER+r')\s*,\s*('+NUMBER+r')\s*\}',value)
    if match:return tuple(float(v) for v in match.groups())
    return None

def import_fusion(text, filename='Fusion.setting'):
    if not isinstance(text,str) or len(text)>2_000_000:raise ValueError('Fusion file limit is 2 MB')
    candidates=[]
    for match,body in blocks(text,r'\b(\w+)\s*=\s*TextPlus\s*\{'):
        values={}; animated=[]
        inputs=next(blocks(body,r'\bInputs\s*=\s*\{'),None)
        if not inputs:continue
        for field,entry in blocks(inputs[1],r'\b(\w+)\s*=\s*Input\s*\{'):
            key=field.group(1)
            if re.search(r'\b(?:Expression|SourceOp)\s*=',mask_source(entry)):
                animated.append(key)
            value=literal(entry)
            if value is not None:values[key]=value
        p=dict(DEFAULT,name=(Path(filename).stem+' · '+match.group(1))[:100],animation='none',uppercase=False,
               outline=0,shadow=0,marginX=40)
        mapped=[]; warnings=[]
        def put(key,value,label):p[key]=value;mapped.append(label)
        if isinstance(values.get('Font'),str):put('fontFamily',values['Font'],'Font family')
        if isinstance(values.get('Style'),str):
            put('weight',800 if any(x in values['Style'].lower() for x in ['bold','heavy','black']) else 400,'Weight (regular/bold approximation)')
        if isinstance(values.get('Size'),(int,float)):
            put('fontSize',max(10,min(200,round(values['Size']*1080))),'Font size (Fusion normalized → 1080px approximation)')
        def rgb(keys,target,label):
            if all(isinstance(values.get(k),(int,float)) for k in keys):
                put(target,'#'+''.join(f'{round(max(0,min(1,values[k]))*255):02X}' for k in keys),label)
        rgb(['Red1','Green1','Blue1'],'textColor','Text color')
        center=values.get('Center') or values.get('LayoutCenter')
        if isinstance(center,tuple):
            _,y=center
            # Fusion y runs bottom to top. Preserve region, approximate baseline/margin.
            position='top' if y>.66 else 'bottom' if y<.34 else 'middle'
            put('position',position,'Vertical position (nearest top / center / bottom)')
            if position!='middle':put('marginY',max(0,min(450,round((1-y if position=='top' else y)*1080))),'Vertical margin (approximate)')
            if abs(center[0]-.5)>.01:warnings.append('Horizontal placement is centered in Caption Studio.')
        # Only map an explicit second shading element configured as an outline.
        if values.get('Enabled2') and values.get('Appearance2')==1:
            rgb(['Red2','Green2','Blue2'],'outlineColor','Outline color')
            if isinstance(values.get('Thickness2'),(int,float)):
                put('outline',max(0,min(15,round(values['Thickness2']*1080))),'Outline width (approximate)')
        elif values.get('Enabled2'):
            warnings.append('Second shading element is not a supported outline; it was not imported.')
        if animated:warnings.append('Animated/expression inputs use static Value only when present: '+', '.join(animated[:12])+'.')
        warnings.append('Fusion keyframes, modifiers, expressions, transforms, masks, images and custom shading are not rendered. Font files are not included; install or upload the matching font.')
        if not mapped:continue
        candidates.append(dict(node=match.group(1),style=preset(p),mapped=mapped,warnings=warnings))
    if not candidates:raise ValueError('No supported static Text+ style found. Export a Fusion TextPlus macro as .setting or a composition as .comp. A .drfx archive or .drp project is not supported.')
    return dict(candidates=candidates,source='fusion')
