from PIL import Image,ImageDraw,ImageFont,ImageEnhance
D='/tmp/claude-0/ice/imgs_user/Ice_Age_JPG/'
O='/tmp/claude-0/ice/brand/'
F='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
# avatar (square 800x800)
a=Image.open(D+'010.jpg').convert('RGB').crop((150,0,620,470)).resize((800,800),Image.LANCZOS)
a.save(O+'avatar_800.jpg',quality=95)
# banner 2560x1440, safe area 1546x423 centred
im=Image.open(D+'009.jpg').convert('RGB').resize((2560,1440),Image.LANCZOS)
im=ImageEnhance.Brightness(im).enhance(.82)
d=ImageDraw.Draw(im)
def center(text,y,size,fill,stroke):
    f=ImageFont.truetype(F,size)
    while d.textlength(text,font=f)>1500 and size>40:
        size-=4;f=ImageFont.truetype(F,size)
    w=d.textlength(text,font=f);x=(2560-w)/2
    d.text((x,y),text,font=f,fill='black',stroke_width=stroke,stroke_fill='black');d.text((x,y),text,font=f,fill=fill)
center('PAST SURVIVOR',520,170,'#ffe14d',16)
center('YOU WAKE UP IN THE PAST. HOW LONG DO YOU LAST?',745,62,'#ffffff',9)
im.save(O+'banner_2560x1440.jpg',quality=92)
# preview with safe-area guide
pv=im.copy();dd=ImageDraw.Draw(pv);dd.rectangle([507,508,2053,931],outline='red',width=6);pv.resize((1280,720)).save(O+'banner_preview.jpg',quality=85)
print('ok')
