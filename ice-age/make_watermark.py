from PIL import Image,ImageDraw
src=Image.open('/tmp/claude-0/ice/brand/avatar_800.jpg').convert('RGB')
def make(size):
    S=size*4  # supersample for smooth edges
    im=src.resize((S,S),Image.LANCZOS).convert('RGBA')
    mask=Image.new('L',(S,S),0);ImageDraw.Draw(mask).ellipse([0,0,S-1,S-1],fill=255)
    out=Image.new('RGBA',(S,S),(0,0,0,0));out.paste(im,(0,0),mask)
    d=ImageDraw.Draw(out)
    r=int(S*.045)
    d.ellipse([r//2,r//2,S-1-r//2,S-1-r//2],outline='#ffe14d',width=r)
    d.ellipse([0,0,S-1,S-1],outline=(0,0,0,255),width=max(2,r//4))
    return out.resize((size,size),Image.LANCZOS)
make(300).save('/home/user/Dualview/ice-age/brand/watermark_300.png')
make(150).save('/home/user/Dualview/ice-age/brand/watermark_150.png')
print('ok')
