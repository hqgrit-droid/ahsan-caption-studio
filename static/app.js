'use strict';
const $=s=>document.querySelector(s), video=$('#video'), form=$('#styleForm');
let state,project=null,style={},selectedPresetId=null,fontCatalog={system:[],uploaded:[]},dirty=false,busy=false,toastTimer,loadedFonts=new Set(),loadingFonts=new Set(),romanBackup=null,pendingImport=null;
function toast(message,duration=6500){$('#status').textContent=message;$('#status').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#status').hidden=true,duration)}
function changed(){dirty=true;$('#saveState').textContent='Unsaved changes'}
function savedLabel(){return state?.cloudStorage?'Saved in private cloud':'Saved locally'}
async function api(path,body){const r=await fetch(path,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json','X-Studio-Token':state.token},body:body===undefined?undefined:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw Error(data.error||'Request failed');return data}
function action(fn){return async e=>{try{await fn(e)}catch(err){toast(err.message)}}}
function requireProject(){if(!project)throw Error('Upload or open a video first')}
function time(s){s=Math.max(0,s||0);return `${Math.floor(s/60)}:${String(Math.floor(s%60)).padStart(2,'0')}`}
function download(name,data,type='application/json'){const url=URL.createObjectURL(new Blob([data],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
function styles(){for(const el of form.elements){if(!el.name)continue;if(el.type==='checkbox')style[el.name]=el.checked;else if(el.type==='number'||el.name==='weight')style[el.name]=Number(el.value);else style[el.name]=el.value}return {...style}}
async function loadFontFile(file){if(!file||loadedFonts.has(file)||loadingFonts.has(file))return;loadingFonts.add(file);try{const font=new FontFace('uploaded-'+file,`url(/files/fonts/${file})`);await font.load();document.fonts.add(font);loadedFonts.add(file)}catch(e){toast('Custom font unavailable. Upload the font file again.')}finally{loadingFonts.delete(file)}}
function fontValue(family,file){if(file&&fontCatalog.uploaded.some(item=>item.file===file))return 'upload:'+file;return !file&&fontCatalog.system.includes(family)?'system:'+family:''}
function fillFontList(select,family='',file='',placeholder='Choose a font…'){select.replaceChildren(new Option(placeholder,''));const system=document.createElement('optgroup');system.label='Fonts on this device';for(const name of fontCatalog.system)system.append(new Option(name,'system:'+name));select.append(system);if(fontCatalog.uploaded.length){const uploaded=document.createElement('optgroup');uploaded.label='Uploaded fonts';for(const item of fontCatalog.uploaded)uploaded.append(new Option(item.family,'upload:'+item.file));select.append(uploaded)}select.value=fontValue(family,file)}
function selectedFont(value){if(value.startsWith('system:'))return {family:value.slice(7),file:''};if(value.startsWith('upload:')){const item=fontCatalog.uploaded.find(item=>item.file===value.slice(7));if(item)return {family:item.family,file:item.file}}return null}
function addUploadedFont(file,family){if(!fontCatalog.uploaded.some(item=>item.file===file))fontCatalog.uploaded.push({file,family:family||'Uploaded font'})}
function setStyle(p){selectedPresetId=p.id||null;style={...state.defaults,...p};delete style.id;for(const el of form.elements){if(!el.name)continue;if(el.type==='checkbox')el.checked=!!style[el.name];else el.value=style[el.name]}$('#fontNote').textContent=style.fontFile?'Uploaded font attached.':'Choose a font from the list or type a family name.';$('#selectedFontLabel').textContent=style.fontFamily;$('#fontListDetails').open=false;fillFontList($('#fontPicker'),style.fontFamily,style.fontFile);loadFontFile(style.fontFile);renderPresets()}
function renderPresets(){const box=$('#presets');box.replaceChildren();if(!state.presets.length){const empty=document.createElement('p');empty.className='hint';empty.textContent='No saved styles. Adjust the controls below and save a new style.';box.append(empty);return}for(const p of state.presets){const row=document.createElement('div');row.className='preset-row';const b=document.createElement('button');b.type='button';b.className='preset'+(p.id===selectedPresetId?' selected':'');b.textContent=p.name;const tag=document.createElement('span');tag.textContent=p.animation==='highlight'?'Aa ✦':'Aa';b.append(tag);b.onclick=()=>{setStyle(p);changed()};const del=document.createElement('button');del.type='button';del.className='preset-delete';del.textContent='Delete';del.setAttribute('aria-label','Delete style '+p.name);del.title='Delete this saved style';del.onclick=action(async()=>{if(!confirm(`Delete style "${p.name}" from your library? This cannot be undone. Saved projects will keep their appearance.`))return;await api('/api/delete-preset',{id:p.id});state.presets=state.presets.filter(item=>item.id!==p.id);if(selectedPresetId===p.id)selectedPresetId=null;renderPresets();toast('Style deleted from library')});row.append(b,del);box.append(row)}}
function renderProjects(){const select=$('#projects');select.replaceChildren(new Option('Open a saved project…',''));for(const p of state.projects)select.add(new Option(p.name,p.id));select.value=project?.id||''}
function openProject(p){project=p;romanBackup=null;$('#undoRoman').hidden=true;$('#romanReport').hidden=true;$('#language').value=p.language||'';setStyle(p.style);for(const cue of p.captions)loadFontFile(cue.style?.fontFile);video.src='/files/media/'+p.media;$('#empty').hidden=true;$('#frame').hidden=false;$('#projectName').textContent=p.name;dirty=false;$('#saveState').textContent=savedLabel();renderCues();renderProjects()}
async function save(){requireProject();if(!form.reportValidity())throw Error('Please fix the style fields');project.style=styles();const p=await api('/api/save',{id:project.id,expectedUpdated:project.updated,captions:project.captions,style:project.style,language:$('#language').value});project.captions=p.captions;project.updated=p.updated;dirty=false;$('#saveState').textContent=savedLabel();return p}
async function upload(file,kind,meta={}){if(!file)return;const query=new URLSearchParams({name:file.name,kind,...meta});const r=await fetch('/api/upload?'+query,{method:'POST',headers:{'X-Studio-Token':state.token},body:file});const data=await r.json();if(!r.ok)throw Error(data.error);return data}
async function uploadVideo(file){if(!file)return;if(location.hostname.endsWith('.trycloudflare.com')&&file.size>90*1000*1000)throw Error('Temporary link accepts videos up to about 90 MB. Use the tool on this Mac for larger videos.');if(dirty&&project)await save();toast('Reading video…');const objectUrl=URL.createObjectURL(file), probe=document.createElement('video');try{await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Unable to read video metadata. Use H.264 MP4.')),15000);probe.onloadedmetadata=()=>{clearTimeout(timer);resolve()};probe.onerror=()=>{clearTimeout(timer);reject(Error('This browser cannot open the video. Convert it to H.264 MP4 first.'))};probe.src=objectUrl});toast(state.cloudStorage?'Uploading to private cloud storage…':'Uploading to your local workspace…',600000);const p=await upload(file,'video',{width:probe.videoWidth,height:probe.videoHeight,duration:probe.duration});state.projects.unshift({id:p.id,name:p.name});openProject(p);toast('Video ready. Generate, import, or add captions.')}finally{URL.revokeObjectURL(objectUrl)}}
function renderCues(){const box=$('#captions');box.replaceChildren();$('#count').textContent=project?.captions.length||0;if(!project?.captions.length){const p=document.createElement('p');p.className='blank';p.textContent='No captions yet. Generate from speech, import SRT / VTT / JSON, or add a cue.';box.append(p);return}project.captions.forEach((cue,index)=>{const row=document.createElement('div');row.className='cue';row.dataset.index=index;const seek=document.createElement('button');seek.textContent=String(index+1).padStart(2,'0');seek.title='Seek to caption';seek.onclick=()=>video.currentTime=cue.start;row.append(seek);for(const k of ['start','end']){const label=document.createElement('label');label.textContent=k.toUpperCase()+' (s)';const input=document.createElement('input');input.type='number';input.min=0;input.step=.01;input.value=Number(cue[k].toFixed(2));input.setAttribute('aria-label',`${k} time, cue ${index+1}`);input.onchange=()=>{cue[k]=Number(input.value);delete cue.words;changed()};label.append(input);row.append(label)}const text=document.createElement('textarea');text.value=cue.text;text.setAttribute('aria-label',`Caption ${index+1}`);text.oninput=()=>{cue.text=text.value;delete cue.words;delete cue.emphasisWord;changed();updateChoice()};row.append(text);const del=document.createElement('button');del.className='delete';del.textContent='×';del.title='Delete cue';del.onclick=()=>{project.captions.splice(index,1);changed();renderCues()};row.append(del);
const focus=document.createElement('label');focus.className='cue-focus';focus.textContent='Main word';
const select=document.createElement('select');select.setAttribute('aria-label',`Main word, cue ${index+1}`);
function updateChoice(){const tokens=cue.text.trim().split(/\s+/).filter(Boolean);const auto=CaptionLogic.chooseKeyword({...cue,emphasisWord:undefined},state.keywordRules);select.replaceChildren(new Option('Auto'+(auto>=0?' · '+tokens[auto]:' · no content word'),'auto'),new Option('No emphasis','-1'));tokens.forEach((w,i)=>select.add(new Option(w,String(i))));select.value=Number.isInteger(cue.emphasisWord)?String(cue.emphasisWord):'auto';}
updateChoice();select.onchange=()=>{if(select.value==='auto')delete cue.emphasisWord;else cue.emphasisWord=Number(select.value);changed()};focus.append(select);row.append(focus);
appendCueAppearance(row,cue,index);
if(cue.sourceText){const original=document.createElement('small');original.className='source-text';original.textContent='Original: '+cue.sourceText;row.append(original)}
box.append(row)})}
function appendCueAppearance(row,cue,index){
  const details=document.createElement('details');details.className='cue-appearance';
  const summary=document.createElement('summary');summary.textContent='Font · size · position';details.append(summary);
  const grid=document.createElement('div');grid.className='cue-options';details.append(grid);
  function update(key,value){cue.style??={};if(value==='')delete cue.style[key];else cue.style[key]=value;if(!Object.keys(cue.style).length)delete cue.style;changed()}
  function field(label,key,type,placeholder,min,max){const wrapper=document.createElement('label');wrapper.textContent=label;const input=document.createElement('input');input.type=type;input.value=cue.style?.[key]??'';input.placeholder=placeholder;input.setAttribute('aria-label',`${label}, cue ${index+1}`);if(type==='number'){input.min=min;input.max=max;input.step='1'}input.oninput=()=>update(key,input.value===''?'':type==='number'?Number(input.value):input.value);wrapper.append(input);grid.append(wrapper);return input}
  const fontName=field('Font name','fontFamily','text',style.fontFamily);
  const fontListLabel=document.createElement('label');fontListLabel.textContent='Font list';const fontPicker=document.createElement('select');fontPicker.setAttribute('aria-label',`Font list, cue ${index+1}`);fillFontList(fontPicker,cue.style?.fontFamily,cue.style?.fontFile,'Use preset font');fontPicker.onchange=()=>{const chosen=selectedFont(fontPicker.value);if(chosen){update('fontFamily',chosen.family);update('fontFile',chosen.file);fontName.value=chosen.family;loadFontFile(chosen.file)}else{update('fontFamily','');update('fontFile','');fontName.value=''}};fontListLabel.append(fontPicker);grid.append(fontListLabel);
  fontName.oninput=()=>{update('fontFamily',fontName.value);update('fontFile','');fontPicker.value=fontValue(fontName.value,'')};
  field('Size','fontSize','number',String(style.fontSize),10,200);
  field('Horizontal %','x','number','50',0,100);
  field('Vertical %','y','number','Preset',0,100);
  const note=document.createElement('p');note.className='hint';note.textContent='Blank fields use the preset. Position is the caption center: 50% horizontal is centered. Use an installed font name, or upload a font below.';details.append(note);
  const controls=document.createElement('div');controls.className='cue-style-actions';details.append(controls);
  const uploadLabel=document.createElement('label');uploadLabel.className='button compact';uploadLabel.textContent='Upload font';const fileInput=document.createElement('input');fileInput.type='file';fileInput.accept='.ttf,.otf';fileInput.hidden=true;fileInput.onchange=action(async()=>{const file=fileInput.files?.[0];if(!file)return;const result=await upload(file,'font');addUploadedFont(result.fontFile,result.fontFamily||fontName.value);update('fontFile',result.fontFile);if(result.fontFamily){update('fontFamily',result.fontFamily);fontName.value=result.fontFamily}fillFontList(fontPicker,fontName.value,result.fontFile,'Use preset font');fillFontList($('#fontPicker'),style.fontFamily,style.fontFile);await loadFontFile(result.fontFile);fontNote.textContent='Uploaded font attached';fileInput.value=''});uploadLabel.append(fileInput);controls.append(uploadLabel);
  const fontNote=document.createElement('span');fontNote.className='cue-font-note';fontNote.textContent=cue.style?.fontFile?'Custom font attached':'Preset or system font';controls.append(fontNote);
  const reset=document.createElement('button');reset.type='button';reset.className='compact';reset.textContent='Reset cue style';reset.onclick=()=>{delete cue.style;changed();renderCues();const reopened=$('#captions').querySelector(`.cue[data-index="${index}"] .cue-appearance`);if(reopened)reopened.open=true};controls.append(reset);
  row.append(details);
}
function words(c){if(c.words?.length)return c.words;const parts=c.text.trim().split(/\s+/);return parts.map((text,i)=>({text,start:c.start+(c.end-c.start)*i/parts.length,end:c.start+(c.end-c.start)*(i+1)/parts.length}))}
function draw(){
  if(project){
    const stage=$('.stage'),frame=$('#frame'),ratio=project.width/project.height;
    const height=Math.min(stage.clientHeight,stage.clientWidth/ratio);
    frame.style.width=height*ratio+'px';frame.style.height=height+'px';
    const scale=height/1080,t=video.currentTime,c=project.captions.find(c=>c.start<=t&&t<c.end),overlay=$('#overlay');
    overlay.replaceChildren();
    if(c){
      const own=c.style||{},fontSize=own.fontSize??style.fontSize;
      const side=Math.min(style.marginX,1080*ratio*.4)*scale,vertical=Math.min(style.marginY,450)*scale;
      const fontFile=own.fontFile||(!own.fontFamily?style.fontFile:'');
      const baseFont=fontFile&&loadedFonts.has(fontFile)?`"uploaded-${fontFile}"`:own.fontFamily||style.fontFamily;
      const customPosition=own.x!==undefined||own.y!==undefined;
      const defaultY=style.position==='top'?vertical/height*100:style.position==='middle'?50:100-vertical/height*100;
      Object.assign(overlay.style,{left:customPosition?(own.x??50)+'%':side+'px',right:customPosition?'auto':side+'px',width:customPosition?`calc(100% - ${side*2}px)`:'auto',top:customPosition?(own.y??defaultY)+'%':style.position==='top'?vertical+'px':style.position==='middle'?'50%':'auto',bottom:customPosition?'auto':style.position==='bottom'?vertical+'px':'auto',transform:customPosition?'translate(-50%,-50%)':style.position==='middle'?'translateY(-50%)':'none',fontFamily:baseFont,fontSize:fontSize*scale+'px',fontWeight:style.weight>=600?'700':'400',color:style.textColor,opacity:style.animation==='fade'?String(Math.max(0,Math.min(1,(t-c.start)/.12,(c.end-t)/.12))):1});
      const cueWords=words(c),selected=style.emphasis?CaptionLogic.chooseKeyword(c,state.keywordRules):-1;
      const groups=CaptionLogic.keywordLines(cueWords.length,selected,Math.max(1,style.maxWords),style.emphasisOwnLine&&selected>=0);
      for(const group of groups){
        const line=document.createElement('div');line.className='line';
        if(style.background){line.style.background=style.backgroundColor;line.style.padding=`0 ${4*scale}px`}
        for(const [j,i] of group.entries()){
          const w=cueWords[i],span=document.createElement('span');span.className='word';
          span.textContent=(j?' ':'')+(style.uppercase?w.text.toUpperCase():w.text);
          span.style.webkitTextStroke=`${style.outline*scale*2}px ${style.outlineColor}`;
          span.style.textShadow=`${style.shadow*scale}px ${style.shadow*scale}px 0 ${style.backgroundColor}`;
          if(i===selected){span.classList.add('main-word');span.style.fontSize=Math.round(fontSize*style.emphasisScale)*scale+'px';span.style.color=style.emphasisColor;span.style.fontFamily=style.emphasisFontFamily||baseFont;span.style.fontStyle=style.emphasisItalic?'italic':'normal';}
          if(style.animation==='highlight'&&w.start<=t&&t<w.end)span.style.color=style.highlightColor;
          line.append(span);
        }
        overlay.append(line);
      }
    }
    $('#time').textContent=`${time(t)} / ${time(video.duration)}`;$('#scrub').max=video.duration||1;$('#scrub').value=t;$('#play').textContent=video.paused?'▶':'Ⅱ';
    document.querySelectorAll('.cue').forEach(el=>el.classList.toggle('active',project.captions[Number(el.dataset.index)]===c));
  }
  requestAnimationFrame(draw);
}
async function job(endpoint,title,extra={}){requireProject();if(busy)return;await save();busy=true;video.pause();const dialog=$('#jobDialog');$('#jobTitle').textContent=title;$('#jobMessage').textContent='Starting…';dialog.showModal();try{const {job}=await api(endpoint,{id:project.id,...extra});while(true){await new Promise(r=>setTimeout(r,1000));const result=await api('/api/jobs/'+job);$('#jobMessage').textContent=result.message;if(result.status==='error')throw Error(result.message);if(result.status==='done')return result.result}}finally{busy=false;dialog.close()}}
$('#jobDialog').addEventListener('cancel',e=>e.preventDefault());
$('#videoFile').onchange=action(e=>uploadVideo(e.target.files[0]));$('#emptyFile').onchange=action(e=>uploadVideo(e.target.files[0]));
$('#projects').onchange=action(async e=>{const id=e.target.value;if(!id)return;if(dirty&&project)await save();openProject(await api('/api/projects/'+id))});
$('#save').onclick=action(async()=>{await save();renderCues();toast(state.cloudStorage?'Project saved in private cloud storage':'Project saved on this computer')});
$('#language').onchange=changed;
function cloudStatus(){ $('#cloudStatus').textContent=state.cloudReady?(state.cloudStorage?'Gemini key connected for this server session.':'Gemini key saved privately on this Mac.'):('No key connected. '+(state.cloudStorage?'Key stays in server memory until restart.':'Save a key to this Mac to enable Gemini.')); }
$('#saveCloudKey').onclick=action(async()=>{const result=await api('/api/cloud-key',{key:$('#cloudKey').value.trim()});$('#cloudKey').value='';state.cloudReady=result.ready;cloudStatus();toast(state.cloudStorage?'Key stored for this session':'Key saved privately on this Mac');});
$('#clearCloudKey').onclick=action(async()=>{await api('/api/cloud-key',{key:''});$('#cloudKey').value='';state.cloudReady=false;cloudStatus();});
$('#provider').onchange=()=>{const cloud=$('#provider').value==='gemini';$('#model').disabled=cloud;$('#model').closest('label').hidden=cloud;$('#generate').textContent=cloud?'✦ Generate with Gemini':'✦ Generate locally';$('#providerNote').textContent=cloud?'Audio is sent to Google. Up to 10 minutes; free quota applies. Review estimated caption timings.':state.cloudStorage?'Local Whisper is not installed on the free cloud server. Use Gemini or import captions.':'Local mode keeps audio on your Mac.';if(cloud){$('#language').value='ur-Latn';$('#cloudSetup').open=!state.cloudReady;}};

$('#play').onclick=action(async()=>{requireProject();if(video.paused)await video.play();else video.pause()});$('#scrub').oninput=e=>video.currentTime=Number(e.target.value);$('#mute').onclick=()=>{video.muted=!video.muted;$('#mute').textContent=video.muted?'Sound off':'Sound on'};
$('#add').onclick=action(()=>{requireProject();const start=Number(video.currentTime.toFixed(2));project.captions.push({start,end:Math.max(start+.1,Math.min(start+2,project.duration)),text:'Your next great line'});changed();renderCues()});
$('#captionFile').onchange=action(async e=>{requireProject();const file=e.target.files[0];if(!file)return;const result=await api('/api/import',{text:await file.text(),ext:'.'+file.name.split('.').pop().toLowerCase()});if(project.captions.length&&!confirm('Replace current captions with this import?'))return;project.captions=result.captions;changed();renderCues();toast('Captions imported');e.target.value=''});
form.oninput=()=>{styles();$('#selectedFontLabel').textContent=style.fontFamily;selectedPresetId=null;renderPresets();changed()};form.onsubmit=action(async e=>{e.preventDefault();const p=await api('/api/presets',styles());state.presets.push(p);setStyle(p);toast(state.cloudStorage?'Reusable preset saved in private cloud storage':'Reusable preset saved locally')});
$('#fontPicker').onchange=()=>{const chosen=selectedFont($('#fontPicker').value);if(!chosen)return;style.fontFamily=chosen.family;style.fontFile=chosen.file;form.elements.namedItem('fontFamily').value=chosen.family;$('#fontNote').textContent=chosen.file?'Uploaded font attached.':'Font available on this device.';$('#selectedFontLabel').textContent=chosen.family;$('#fontListDetails').open=false;loadFontFile(chosen.file);selectedPresetId=null;renderPresets();changed()};
function showImportCandidate(){
  const item=pendingImport.candidates[Number($('#fusionCandidate').value)];
  $('#fusionMapped').textContent='Imported: '+item.mapped.join(', ');
  $('#fusionWarnings').replaceChildren();
  for(const message of item.warnings){const li=document.createElement('li');li.textContent=message;$('#fusionWarnings').append(li)}
}
$('#presetFile').onchange=action(async e=>{
  const file=e.target.files[0];if(!file)return;
  try{
    pendingImport=await api('/api/import-style',{name:file.name,text:await file.text()});
    $('#fusionCandidate').replaceChildren(...pendingImport.candidates.map((item,i)=>new Option(item.node,String(i))));
    showImportCandidate();$('#importDialog').showModal();
  }finally{e.target.value=''}
});
$('#fusionCandidate').onchange=showImportCandidate;
$('#cancelImport').onclick=()=>$('#importDialog').close();
$('#applyImport').onclick=action(async()=>{
  const item=pendingImport.candidates[Number($('#fusionCandidate').value)];
  const p=await api('/api/presets',item.style);state.presets.push(p);setStyle(p);changed();
  $('#importReport').textContent=item.node+': '+item.mapped.join(', ')+'. '+item.warnings.join(' ');
  $('#importReport').hidden=false;$('#importDialog').close();toast('Style imported and saved in your library');
});
function romanReport(result){$('#romanReport').hidden=false;$('#romanReport').textContent=(result.notice||'Roman Urdu ready.')+(result.reviewWords?.length?' Check spellings: '+result.reviewWords.slice(0,16).join('، ')+(result.reviewWords.length>16?' …':''):'');}
$('#saveSpellings').onclick=action(async()=>{
  const spellings={};
  for(const line of $('#romanSpellings').value.split('\n').map(x=>x.trim()).filter(Boolean)){
    const at=line.indexOf('=');if(at<1)throw Error('Use source=spelling, one word per line.');
    spellings[line.slice(0,at).trim()]=line.slice(at+1).trim();
  }
  const result=await api('/api/roman-spellings',{spellings});state.romanSpellings=result.spellings;
  toast('Spellings saved. Generate or convert captions to apply them.');
});
$('#romanize').onclick=action(async()=>{
  requireProject();const result=await api('/api/romanize',{captions:project.captions});
  romanBackup=JSON.parse(JSON.stringify(project.captions));project.captions=result.captions;
  $('#undoRoman').hidden=false;$('#language').value='ur-Latn';changed();renderCues();romanReport(result);
});
$('#undoRoman').onclick=()=>{if(!romanBackup)return;project.captions=romanBackup;romanBackup=null;$('#undoRoman').hidden=true;$('#romanReport').hidden=true;changed();renderCues()};
$('#downloadPreset').onclick=()=>download((style.name||'preset')+'.json',JSON.stringify(styles(),null,2));
$('#fontFile').onchange=action(async e=>{const file=e.target.files[0];if(!file)return;const result=await upload(file,'font');addUploadedFont(result.fontFile,result.fontFamily||style.fontFamily);style.fontFile=result.fontFile;if(result.fontFamily)style.fontFamily=result.fontFamily;setStyle(style);changed();toast(result.fontFamily?'Font uploaded and added to the list':'Font uploaded. Enter its family name for export.');e.target.value=''});
$('#clearFont').onclick=()=>{style.fontFile='';setStyle(style);changed()};
$('#generate').onclick=action(async()=>{requireProject();if(busy)return;if($('#provider').value==='gemini'&&!state.cloudReady){$('#cloudSetup').open=true;throw Error('Add your Gemini key in Cloud setup first.');}if(project.captions.length&&!confirm('Replace current captions with a new transcription?'))return;const result=await job('/api/transcribe','Finding your words…',{provider:$('#provider').value,model:$('#model').value,language:$('#language').value});project.captions=result.captions;$('#language').value=result.language||$('#language').value;romanBackup=null;$('#undoRoman').hidden=true;changed();renderCues();await save();if(result.notice)romanReport(result);else $('#romanReport').hidden=true;toast('Captions generated and saved')});
$('#export').onclick=action(async()=>{const result=await job('/api/export','Making the final cut…');const a=document.createElement('a');a.href=result.url;a.download='captioned.mp4';a.click();toast('Captioned MP4 ready — download started')});
$('#downloadJson').onclick=action(()=>{requireProject();download('captions.json',JSON.stringify({captions:project.captions},null,2))});
function stamp(t){let ms=Math.round(t*1000),s=Math.floor(ms/1000);return `${String(Math.floor(s/3600)).padStart(2,'0')}:${String(Math.floor(s/60)%60).padStart(2,'0')}:${String(s%60).padStart(2,'0')},${String(ms%1000).padStart(3,'0')}`}
$('#downloadSrt').onclick=action(()=>{requireProject();download('captions.srt',project.captions.map((c,i)=>`${i+1}\n${stamp(c.start)} --> ${stamp(c.end)}\n${c.text}\n`).join('\n'),'text/plain')});
window.addEventListener('beforeunload',e=>{if(dirty||busy){e.preventDefault();e.returnValue=''}});
video.onerror=()=>toast('Video playback failed. Use a browser-compatible H.264 MP4.');
(async()=>{try{state=await api('/api/state');if(location.hostname.endsWith('.trycloudflare.com'))$('#empty small').textContent='MP4 recommended · temporary link · video limit about 90 MB';try{fontCatalog=await api('/api/fonts')}catch(e){fontCatalog={system:[],uploaded:[]};toast('Font list unavailable. You can still type a font name.')}if(state.cloudStorage){$('.local').textContent='● PRIVATE CLOUD WORKSPACE';$('#empty small').textContent='MP4 recommended · stored in your private bucket';$('#jobDialog .eyebrow').textContent='CLOUD PROCESSING';$('#jobDialog .hint').textContent='Keep this page open while the job runs. Completed files are saved to your private bucket.';$('.system .eyebrow').textContent='CLOUD SERVER';$('.system p:last-child').textContent='Gemini transcription sends audio to Google. Saved videos and captions use your private storage bucket.';$('#styleForm + .hint').textContent='Style applies to all cues. Import JSON or a Fusion Text+ style. Uploaded fonts are stored in your private bucket.';$('#saveCloudKey').textContent='Use key for this session'}if(state.cloudReady||!state.whisper){$('#provider').value='gemini';$('#provider').onchange();}cloudStatus();$('#romanSpellings').value=Object.entries(state.romanSpellings||{}).map(([a,b])=>a+'='+b).join('\n');setStyle(state.presets[0]||state.defaults);renderProjects();$('#dependencies').textContent=`FFmpeg: ${state.ffmpeg?'ready':'not installed / libass missing'} · Whisper: ${state.whisper?'ready':'not installed'} · Roman Urdu: ${state.roman?'ready':'not installed'}`;requestAnimationFrame(draw)}catch(e){toast(e.message)}})();
