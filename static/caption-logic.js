/* Shared deterministic rules mirror keywords.py. Rules arrive from the local server. */
(function(root){
  function chooseKeyword(cue,rules){
    const words=cue.text.trim().split(/\s+/).filter(Boolean);
    if(Number.isInteger(cue.emphasisWord)&&cue.emphasisWord>=-1&&cue.emphasisWord<words.length)return cue.emphasisWord;
    const stop=new Set(rules.stopwords),impact=new Set(rules.impactWords);let selected=-1,best=-Infinity;
    words.forEach((word,i)=>{
      const token=word.toLowerCase().replace(/[^\p{L}\p{N}_\u0600-\u06ff]/gu,'');
      if(!token||stop.has(token))return;
      let score=Math.min([...token].length,12)*.12;
      if(impact.has(token))score+=3;
      if(/\p{N}/u.test(token))score+=2;
      if(/[!؟?]$/.test(word))score+=.35;
      if(cue.words?.length===words.length)score+=Math.min(Math.max(cue.words[i].end-cue.words[i].start,0),1)*.5;
      if(score>best){best=score;selected=i;}
    });return selected;
  }
  function keywordLines(count,index,maxWords,ownLine){
    const groups=[];let current=[];
    for(let i=0;i<count;i++){
      if(ownLine&&i===index){if(current.length)groups.push(current);current=[];groups.push([i]);}
      else{current.push(i);if(current.length>=maxWords){groups.push(current);current=[];}}
    }
    if(current.length)groups.push(current);return groups;
  }
  const api={chooseKeyword,keywordLines};
  if(typeof module!=='undefined')module.exports=api;else root.CaptionLogic=api;
})(typeof window!=='undefined'?window:this);
