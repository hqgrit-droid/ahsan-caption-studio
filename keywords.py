"""Explainable, offline key-word selection. No external model or API required."""
import re
STOPWORDS = set('''a an the and or but so if then than of in on at to for from with by as is am are was were be been being do does did have has had will would can could should may might must this that these those it its i me my mine we us our ours you your yours he him his she her they them their what which who whom when where why how not no yes just very really also too more most some any all each every only even about into over under through up out off there here now get got getting make made let know think want need going go come take use one something thing things gonna like well actually
hai hain ho hoon hun tha thi thay the hoga hogi honge hota hoti hote hona hone hua hui huay yeh ye woh wo is iss us mein mai main men me hum ham humein tum tumhein aap ap apko apne apni apna mujhe mera meri mere hamara hamari hamare tumhara tumhari tumhare ka ki ke ko se par per aur or ya lekin magar agar to toh tu bhi hi he kyun kyu kyon kaisay kaise kya kia kaun kab kahan ab tab jab tak bas bohat bahut zyada kuch koi sab har aik ek kar karo karein karta karti karte karna karne kiya kiye liye liya lena lo de dena diya gaya gayi gaye ja raha rahi rahe han haan nahi nahin na mat phir sirf bilkul walay wala wali isi usi yahan wahan aisa aise aisi achha acha
ہے ہیں ہو ہوں تھا تھی تھے یہ وہ اس اُس میں ہم تم آپ کا کی کے کو سے پر اور یا لیکن اگر تو بھی ہی کیوں کیا کون کب کہاں اب تب جب تک بہت کچھ کوئی سب ہر ایک کر کرو کرنا لیے رہا رہی رہے نہیں'''.split())
IMPACT_WORDS=set('''success successful money profit growth grow change life dream dreams freedom free secret mistake mistakes powerful power important opportunity confidence story stories focus discipline business brand value trust time risk quality results result sell sales income million billion thousand love fear never always truth stop start win winning lose loss best worst unique simple easy impossible possible difference property home house real estate investment price worth learn skill skills creative creator content video captions word words count
kamiyabi kamyabi kamyab paisa paise mehnat zindagi khwab azadi muft raaz ghalti galti taqat zaroori mauqa yaqeen kahani tawajjo karobar qeemat waqt khatra nateeja natija faida nuqsan mohabbat darr sach shuru jeet haar behtareen asaan mushkil farq ghar taleem hunar
کامیابی پیسہ محنت زندگی خواب راز غلطی ضروری کہانی کاروبار قیمت وقت فائدہ نقصان سچ جیت گھر'''.split())

def clean_word(t):
    return re.sub(r'[^\w\u0600-\u06ff]','',t.lower(),flags=re.UNICODE)

def choose_keyword(cue):
    words=cue['text'].split()
    manual=cue.get('emphasisWord')
    if isinstance(manual,int) and -1<=manual<len(words):return manual
    candidates=[]
    timed=cue.get('words',[])
    for i,word in enumerate(words):
        token=clean_word(word)
        if not token or token in STOPWORDS:continue
        score=min(len(token),12)*.12
        if token in IMPACT_WORDS:score+=3
        if any(c.isdigit() for c in token):score+=2
        if word.endswith(('!','؟','?')):score+=.35
        if len(timed)==len(words):score+=min(max(timed[i]['end']-timed[i]['start'],0),1)*.5
        candidates.append((score,i))
    # Stable tie break: prefer the earlier content word. Function-word-only cues stay plain.
    return max(candidates,key=lambda x:(x[0],-x[1]))[1] if candidates else -1

def keyword_lines(count,index,max_words,own_line):
    groups=[]; current=[]
    for i in range(count):
        if own_line and i==index:
            if current:groups.append(current);current=[]
            groups.append([i])
        else:
            current.append(i)
            if len(current)>=max_words:groups.append(current);current=[]
    if current:groups.append(current)
    return groups
