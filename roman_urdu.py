"""Offline Urdu→Latin transliteration, with common Roman Urdu spelling overrides.

Not translation and not a separate Whisper language. Unknown words use uroman and
are flagged for review because unvowelled Urdu has ambiguous pronunciations.
"""
import copy, re, threading, unicodedata
_ENGINE=None
_LOCK=threading.Lock()
COMMON={}
for line in '''
میں=main
ہم=hum
تم=tum
آپ=aap
وہ=woh
یہ=yeh
اس=is
اُس=us
ان=un
اِن=in
ایک=ek
دو=do
تین=teen
چار=chaar
پانچ=paanch
ہے=hai
ہیں=hain
ہوں=hoon
ہو=ho
تھا=tha
تھی=thi
تھے=thay
ہوگا=hoga
ہوگی=hogi
ہوںگے=honge
ہوتا=hota
ہوتی=hoti
ہوتے=hote
ہونا=hona
ہونے=hone
ہوا=hua
ہوئی=hui
ہوئے=huay
کی=ki
کا=ka
کے=ke
کو=ko
سے=se
پر=par
اور=aur
یا=ya
تو=to
بھی=bhi
ہی=hi
نہیں=nahi
نہ=na
نا=na
ہاں=haan
جی=ji
کیا=kya
کیوں=kyun
کیسے=kaise
کون=kaun
کب=kab
کہاں=kahan
کہ=ke
کچھ=kuch
کوئی=koi
سب=sab
ہر=har
اب=ab
آج=aaj
کل=kal
پھر=phir
جب=jab
تب=tab
تک=tak
بس=bas
صرف=sirf
بہت=bohat
زیادہ=zyada
کم=kam
اگر=agar
لیکن=lekin
مگر=magar
کیونکہ=kyunke
لہذا=lehaza
چاہیے=chahiye
چاہئے=chahiye
چاہتا=chahta
چاہتی=chahti
چاہتے=chahte
چاہیں=chahein
چاہو=chaho
سکتا=sakta
سکتی=sakti
سکتے=sakte
سکیں=sakein
مجھ=mujh
مجھے=mujhe
تمہیں=tumhein
آپکو=aapko
اپنے=apne
اپنی=apni
اپنا=apna
میرا=mera
میری=meri
میرے=mere
ہمارا=hamara
ہماری=hamari
ہمارے=hamare
ہمارےلیے=hamare-liye
تمہارا=tumhara
تمہاری=tumhari
تمہارے=tumhare
خود=khud
ساتھ=saath
بغیر=baghair
لئے=liye
لیے=liye
لیکن=lekin
پہلے=pehle
بعد=baad
یہاں=yahan
وہاں=wahan
سامنے=samne
اندر=andar
باہر=bahar
اوپر=upar
نیچے=neeche
کر=kar
کرو=karo
کریں=karein
کرتا=karta
کرتی=karti
کرتے=karte
کرنا=karna
کرنے=karne
کرکے=karke
کیا=kya
کئے=kiye
کیے=kiye
کروگے=karoge
رہا=raha
رہی=rahi
رہے=rahe
رکھ=rakh
رکھو=rakho
رکھیں=rakhein
رکھنا=rakhna
رکھتا=rakhta
رکھتے=rakhte
گیا=gaya
گئی=gayi
گئے=gaye
جانا=jana
جانے=jane
جاؤ=jao
جائیں=jayein
جاتا=jata
جاتی=jati
جاتے=jate
آنا=aana
آنے=aane
آؤ=aao
آتا=aata
آتی=aati
آتے=aate
لیا=liya
لینا=lena
لینے=lene
لو=lo
دے=de
دینا=dena
دینے=dene
دیا=diya
دیں=dein
دیکھ=dekh
دیکھو=dekho
دیکھیں=dekhein
دیکھنا=dekhna
دیکھتے=dekhte
سن=sun
سنو=suno
سنیں=sunein
سننا=sunna
بولو=bolo
بولنا=bolna
کہو=kaho
کہتا=kehta
کہتے=kehte
کہنا=kehna
بتاؤ=batao
بتائیں=batayein
بتانا=batana
بن=bann
بنا=bana
بناؤ=banao
بنائیں=banayein
بنانا=banana
بنانے=banane
بنتا=banta
بنتی=banti
بناتے=banate
بنایا=banaya
مل=mil
ملا=mila
ملتا=milta
ملتی=milti
ملتے=milte
ملے=mile
پتا=pata
پتہ=pata
جانتے=jante
جانتا=janta
سمجھ=samajh
سمجھو=samjho
سمجھنا=samajhna
سیکھ=seekh
سیکھو=seekho
سیکھیں=seekhein
سیکھنا=seekhna
سوچ=soch
سوچو=socho
سوچنا=sochna
چلو=chalo
چلیں=chalein
اچھا=achha
اچھی=achhi
اچھے=achhe
برا=bura
بہتر=behtar
بہترین=behtareen
آسان=aasaan
مشکل=mushkil
ضروری=zaroori
اہم=aham
صحیح=sahi
غلط=ghalat
نیا=naya
نئی=nayi
نئے=naye
پرانا=purana
بڑا=bara
بڑی=bari
بڑے=bare
چھوٹا=chhota
چھوٹی=chhoti
چھوٹے=chhote
مفت=muft
مکمل=mukammal
تیار=tayyar
اصل=asal
بلکل=bilkul
بالکل=bilkul
ہمیشہ=hamesha
کبھی=kabhi
روز=roz
روزانہ=rozana
ابھی=abhi
فوراً=foran
دوبارہ=dobara
وقت=waqt
دن=din
رات=raat
صبح=subah
شام=shaam
سال=saal
مہینہ=maheena
گھنٹے=ghante
منٹ=minute
زندگی=zindagi
دنیا=duniya
لوگ=log
لوگوں=logon
انسان=insaan
دوست=dost
دوستو=dosto
دوستوں=doston
بھائی=bhai
بہن=behen
بچوں=bachon
بچہ=bachha
گھر=ghar
کام=kaam
بات=baat
باتیں=baatein
باتوں=baaton
نام=naam
دل=dil
خوش=khush
خوشی=khushi
محبت=mohabbat
محنت=mehnat
کامیابی=kamyabi
کامیاب=kamyab
خواب=khwab
پیسہ=paisa
پیسے=paise
کاروبار=karobar
قیمت=qeemat
فائدہ=faida
نقصان=nuqsan
مقصد=maqsad
موقع=mauqa
طریقہ=tareeqa
طریقے=tareeqe
چیز=cheez
چیزیں=cheezein
چیزوں=cheezon
سوال=sawal
جواب=jawab
مثال=misaal
مسئلہ=masla
حل=hal
وجہ=wajah
ضرورت=zaroorat
مدد=madad
شروع=shuru
آخر=aakhir
ختم=khatam
نتیجہ=nateeja
تبدیل=tabdeel
بدل=badal
بدلو=badlo
بدلنا=badalna
بنائیں=banayein
پاکستان=Pakistan
اردو=Urdu
انگریزی=English
احسن=Ahsan
اسلام=islam
السلام=assalam
علیکم=alaikum
ویڈیو=video
ویڈیوز=videos
کیپشن=caption
کیپشنز=captions
سٹائل=style
اسٹائل=style
فونٹ=font
ٹول=tool
فائل=file
سیو=save
اپلوڈ=upload
اپ=up
لوڈ=load
ڈاؤن=down
ڈاؤنلوڈ=download
ایڈیٹنگ=editing
ایڈٹ=edit
برانڈ=brand
بزنس=business
کانٹینٹ=content
سوشل=social
میڈیا=media
ریلز=reels
انسٹاگرام=Instagram
فری=free
کورس=course
آن=on
لائن=line
آنلائن=online
کلک=click
لنک=link
سائز=size
رنگ=rang
الفاظ=alfaaz
لفظ=lafz
کہانی=kahani
'''.strip().splitlines():
    source,target=line.split('=',1);COMMON[source]=target

def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKC',text).translate(str.maketrans({'ي':'ی','ى':'ی','ك':'ک'})) if unicodedata.category(c)!='Mn')
COMMON={normalize(k):v for k,v in COMMON.items()}
# Normalizing diacritics makes اِس/اُس ambiguous; use the common demonstrative spelling.
COMMON['اس']='is';COMMON['ان']='un'
COMMON.update({'بدلیں':'badlein','بدلتے':'badalte','بدلتا':'badalta','حاصل':'hasil','حقیقت':'haqeeqat','ہمت':'himmat','توجہ':'tawajjo','جیت':'jeet','ہار':'haar','رنگوں':'rangon','اہمیت':'ahmiyat','ضرور':'zaroor','چاہنے':'chahne','لفظوں':'lafzon','کامیابیوں':'kamyabiyon'})


# Common conversational vocabulary and English loanwords: keep readable spellings.
for pair in """
دی=di گا=ga گی=gi گے=ge بتایا=bataya کروا=karwa دستیاب=dastyab
ابھی=abhi جیسے=jaise ویسے=waise ایسا=aisa ایسی=aisi ایسے=aise بتا=bata بتایا=bataya بتاتی=batati بتاتے=batate
کروایا=karwaya کروائی=karwai کرواتی=karwati کرواتے=karwate کروانا=karwana دیتے=dete دیتی=deti دیتا=deta
والی=wali والا=wala والے=wale والے=wale ہمارا=hamara ہماری=hamari ہمارے=hamare دوبارہ=dobara ضرور=zaroor
بالکل=bilkul واقعی=waqai شاید=shayad ہمیشہ=hamesha کبھی=kabhi ابھی=abhi تقریبا=taqreeban تقریباً=taqreeban
مزید=mazeed موجود=maujood قریب=qareeb پیچھے=peechhe سامنے=samne بالکل=bilkul سیدھا=seedha سیدھے=seedhe
دائیں=dayein بائیں=bayein راستہ=rasta راستے=raste راستوں=raston جگہ=jagah جگہوں=jagahon شہر=shehar
کھانا=khana کھانے=khane کھائیں=khayein کھاتے=khate کھاتی=khati کھاتا=khata مزہ=maza مزے=maze
مزیدار=mazedar ذائقہ=zaiqa ذائقے=zaiqe لذیذ=lazeez تازہ=taza گرم=garam ٹھنڈا=thanda
بھوکا=bhooka بھوک=bhook پیاس=pyas پانی=pani چائے=chai روٹی=roti گوشت=gosht مرغی=murghi
چاول=chawal سبزی=sabzi دال=daal نمک=namak مرچ=mirch مصالحہ=masala مصالحے=masale
دوست=dost دوستوں=doston لوگ=log لوگوں=logon خاندان=khandan گھر=ghar دفتر=daftar بازار=bazaar
دکان=dukaan سڑک=sarak گاڑی=gaari موٹر=motor بائیک=bike کرایہ=kiraya ریسٹورنٹ=restaurant
لوکیشن=location لوکیشنز=locations لکیشن=location لوکیشَن=location برانچ=branch برانچز=branches
انٹروڈیوس=introduce انٹروڈیوز=introduce انٹروڈیوسڈ=introduced انٹروڈکشن=introduction
ڈش=dish ڈشز=dishes ڈشیز=dishes نیو=new نیوز=news ایزی=easy گائیڈ=guide گایڈ=guide
اوپن=open کلوز=close ٹائمنگ=timing ٹائم=time فائیو=five اسٹار=star سٹار=star
اوکے=okay اوکی=okay پلیز=please تھینک=thank تھینکس=thanks سوری=sorry ویلکم=welcome
آرڈر=order آرڈرز=orders ڈیلیوری=delivery ڈلیوری=delivery پارسل=parcel پرائس=price مینیو=menu
ڈسکاؤنٹ=discount آفر=offer آفرز=offers سپیشل=special اسپیشل=special چکن=chicken بیف=beef
مٹن=mutton باربی=barbecue باربیکیو=barbecue پیزا=pizza برگر=burger بریانی=biryani شوارما=shawarma
فیملی=family فرینڈز=friends پارکنگ=parking سروس=service سروسز=services کوالٹی=quality
ایڈریس=address نمبر=number رابطہ=rabta کال=call میسج=message واٹس=Whats ایپ=App
روڈ=road اسٹریٹ=street سٹریٹ=street بلاک=block مارکیٹ=market سینٹر=center سنٹر=center
پاس=paas والی=wali پہ=pe تک=tak میں=main مزید=mazeed کیونکہ=kyunke
""".split():
    if '=' in pair:
        source,target=pair.split('=',1)
        COMMON[normalize(source)]=target

def engine():
    global _ENGINE
    with _LOCK:
        if _ENGINE is None:
            try:from uroman import Uroman
            except ImportError:raise ValueError('Roman Urdu needs the local uroman package. Run .venv/bin/python -m pip install -r requirements.txt and restart.')
            _ENGINE=Uroman()
    return _ENGINE

def validate_spellings(raw):
    if not isinstance(raw,dict) or len(raw)>2000:
        raise ValueError('Use at most 2000 spelling entries.')
    clean={}
    for source,target in raw.items():
        if not isinstance(source,str) or not isinstance(target,str):
            raise ValueError('Spellings must be text.')
        source=normalize(source.strip());target=target.strip()
        if not source or len(source)>80 or len(target)>100 or not re.fullmatch(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*",target):
            raise ValueError('Each spelling needs one source word and a Roman spelling, e.g. لوکیشن=location.')
        if any(c.isspace() for c in source):raise ValueError('Use one source word per spelling entry.')
        clean[source]=target
    return clean

def romanize_token(token, spellings=None):
    unknown=[]
    def convert(match):
        text=normalize(match.group())
        if spellings and text in spellings:return spellings[text]
        if text in COMMON:return COMMON[text]
        # Offline fallback does not invent a translation or send data to a service.
        result=engine().romanize_string(text,lcode='urd')
        result='-'.join(result.split())
        if re.search(r'[\u0600-\u06ff]',result):raise ValueError('Unable to romanize a word; edit the Urdu caption before converting.')
        unknown.append(match.group());return result
    token=token.translate(str.maketrans({'،':',','۔':'.','؟':'?','؛':';','٪':'%'}))
    result=re.sub(r'[\u0620-\u065f\u0670-\u06d3\u06fa-\u06ff]+',convert,token)
    result=result.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩','01234567890123456789'))
    return result,unknown

def romanize_captions(rows, spellings=None):
    spellings=validate_spellings(spellings or {})
    result=copy.deepcopy(rows);review=set()
    for row in result:
        old=row['text'];source_tokens=old.split();converted=[]
        for token in source_tokens:
            text,unknown=romanize_token(token,spellings);converted.append(text);review.update(unknown)
        row['text']=' '.join(converted)
        if row.get('words'):
            for word,text in zip(row['words'],converted):word['text']=text
        if old!=row['text']:row['sourceText']=old
    return dict(captions=result,reviewWords=sorted(review),notice='Common words use readable Roman spellings. Listed words are approximate: add their correct spelling below. If the spoken words are wrong, generate again with Whisper small or medium.')
