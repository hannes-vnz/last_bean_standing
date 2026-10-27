from px import *
import variants
INKB="#4a3358"
def eyes(p,y=7,x1=5.7,x2=10.3):
    p.ell(x1,y,1.3,1.8,"#ffffff",False); p.ell(x2,y,1.3,1.8,"#ffffff",False)
    p.set(round(x1)+0,y+0,INKB); p.set(round(x1),y+1,INKB); p.set(round(x2)-0,y,INKB); p.set(round(x2),y+1,INKB)
def cheeks(p): p.set(3,9,"#ff9fc0"); p.set(12,9,"#ff9fc0")
def bean(p,c,belly=None):
    p.ell(8,8.2,6,5.4,c)
    p.ell(8,10.6,3.7,2.2,belly or light(c,.45),False)
def feet(p,c): p.rect(4,13,6,14,c); p.rect(9,13,11,14,c)
def fin(p,k=.5,eye=True):
    outline_sel(p,k)
def outline_sel(p,k=.5):
    variants.outline_sel(p,k)
def fenn():
    p=PX(16,16); G="#6bbf59"
    feet(p,"#8a5a30"); bean(p,G)
    p.ell(8,3.6,5.2,2.3,"#3f8a3f"); p.poly([(11,2),(14,0.5),(13.2,3)],"#ff8fb8")
    p.rect(2,3,3,6,"#8a5a30"); p.pts([(2,2),(3,2)],"#ff8fb8")
    p.rect(3,11,12,11,"#8a5a30"); p.rect(7,11,8,11,"#ffd45e")
    for (x,y) in [(13,6),(14,7),(14,8),(14,9),(14,10),(14,11),(13,12)]: p.set(x,y,"#8a5a30")
    p.line(13,6,13,12,"#ffffff")
    outline_sel(p); eyes(p); cheeks(p); p.set(8,9,INKB); return p
def mira():
    p=PX(16,16); C="#ff9f5a"
    feet(p,"#c66f2d"); bean(p,C,"#ffd9a0")
    p.poly([(8,0.5),(11,3.5),(5,3.5)],"#ff7a5a"); p.poly([(8,2),(9.6,3.6),(6.4,3.6)],"#ffd45e"); p.ell(8,4,4.6,1.6,"#ff7a5a")
    p.rect(3,11,12,11,"#ffd45e")
    p.ell(13.3,9,1.7,1.7,"#ff8f3a"); p.ell(13.3,9,0.9,0.9,"#fff7a8",False)
    outline_sel(p); eyes(p); cheeks(p); p.set(8,9,INKB); return p
def brun():
    p=PX(16,16); S="#9fb0cc"
    feet(p,"#5a6a8a"); bean(p,S,"#c9d3e6")
    p.ell(8,4.2,5.4,3,"#b9c2d4"); p.rect(4,5,11,8,"#5a6a8a"); p.poly([(8,0),(9.5,1.5),(6.5,1.5)],"#ff8fb8")
    p.rect(3,11,12,11,"#ffd45e")
    p.ell(2.6,10,2.2,3,"#ffd45e"); p.ell(2.6,10,1,1.5,"#ff8fb8",False)
    outline_sel(p)
    p.set(5,6,"#ffffff");p.set(6,6,"#ffffff");p.set(5,7,"#ffffff");p.set(6,7,INKB)
    p.set(10,6,"#ffffff");p.set(9,6,"#ffffff");p.set(10,7,"#ffffff");p.set(9,7,INKB); return p
def aya():
    p=PX(16,16); C="#d2c08e"
    feet(p,"#8a5a30"); bean(p,C,"#efe2bd")
    p.ell(8,3.2,7,1.2,"#f5d58a"); p.ell(8,3.6,4.2,2.4,"#f5d58a")
    p.rect(4,9,11,9,"#ff8fb8")
    p.line(1,11,14,10,"#6a6a7a"); p.rect(1,10,3,12,"#8a5a30"); p.set(9,9,"#7fd6ff")
    outline_sel(p); eyes(p,y=6); cheeks(p); p.set(8,8,INKB); return p
CAST=[("Fenn · Jäger",fenn),("Mira · Pyromantin",mira),("Brun · Wächter",brun),("Aya · Scharfschützin",aya)]
