from PIL import Image,ImageDraw,ImageFont,ImageFilter,ImageEnhance
import sys
D='/tmp/claude-0/ice/imgs_user/Ice_Age_JPG/'
F='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
def outlined(d,xy,text,font,fill='#ffe14d',stroke=14):
    d.text(xy,text,font=font,fill='black',stroke_width=stroke,stroke_fill='black')
    d.text(xy,text,font=font,fill=fill,stroke_width=0)
def make(img,text,out,size=170,pos=(40,18),crop=None,fill='#ffe14d',arrow=None,text2=None):
    im=Image.open(D+img).convert('RGB')
    if crop: im=im.crop(crop)
    im=im.resize((1280,720),Image.LANCZOS)
    im=ImageEnhance.Contrast(im).enhance(1.12);im=ImageEnhance.Color(im).enhance(1.12)
    d=ImageDraw.Draw(im)
    f=ImageFont.truetype(F,size)
    # shrink to fit width
    while d.textlength(text,font=f)>1200-pos[0] and size>60:
        size-=6;f=ImageFont.truetype(F,size)
    outlined(d,pos,text,f,fill)
    if text2:
        f2=ImageFont.truetype(F,int(size*.62));outlined(d,(pos[0],pos[1]+size*1.05),text2,f2,'#ffffff',stroke=10)
    im.save(out,quality=92);return im
make('010.jpg','1 HOUR?','/tmp/claude-0/ice/thumbs/A.jpg',size=190)
make('001.jpg','SURVIVE?','/tmp/claude-0/ice/thumbs/B.jpg',size=190)
make('005.jpg','HOW LONG?','/tmp/claude-0/ice/thumbs/C.jpg',size=170)
make('002.jpg','1 DAY?','/tmp/claude-0/ice/thumbs/D.jpg',size=190)
# flipped hero variant: character on the right, text top-left over the glacier
im=Image.open(D+'010.jpg').convert('RGB').transpose(Image.FLIP_LEFT_RIGHT).resize((1280,720),Image.LANCZOS)
im=ImageEnhance.Contrast(im).enhance(1.12);im=ImageEnhance.Color(im).enhance(1.12)
d=ImageDraw.Draw(im);f=ImageFont.truetype(F,148)
outlined(d,(40,30),'1 HOUR?',f)
f2=ImageFont.truetype(F,92);outlined(d,(44,190),'ICE AGE',f2,'#ffffff',stroke=10)
im.save('/tmp/claude-0/ice/thumbs/E.jpg',quality=92)
