"""Original industrial background layers; native parallax, never colliders."""
import skia

def add_industrial_layers(world):
    for z,spacing,rgb,width in ((1050.,900.,(36,49,59),22.),(650.,1250.,(25,36,45),32.)):
        x0,x1=world._span(z);top=world.level+650.;bottom=world.level-2100.
        def draw(c,x0=x0,x1=x1,top=top,bottom=bottom,spacing=spacing,rgb=rgb,width=width):
            base=skia.Paint(AntiAlias=True,Color=skia.ColorSetARGB(230,*rgb),StrokeWidth=width,StrokeCap=skia.Paint.kRound_Cap)
            edge=skia.Paint(AntiAlias=True,Color=skia.ColorSetARGB(135,68,89,102),StrokeWidth=3.)
            lamp=skia.Paint(AntiAlias=True,Color=skia.ColorSetARGB(155,124,180,190))
            x=x0
            while x<x1:
                c.drawLine(x,-bottom,x,-top,base)
                c.drawLine(x+width*.6,-bottom,x+width*.6,-top,edge)
                c.drawLine(x,-top,x+spacing,-top,base)
                c.drawLine(x,-(top-200),x+spacing*.36,-top,edge)
                c.drawCircle(x+spacing*.35,-(top-35),9.,lamp)
                x+=spacing
        world._rec(z,draw)
