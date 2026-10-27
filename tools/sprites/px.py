import math, json
INK="#4a3358"
def hx(c): c=c.lstrip("#"); return tuple(int(c[i:i+2],16) for i in (0,2,4))
def th(t): return "#%02x%02x%02x"%tuple(max(0,min(255,int(v))) for v in t)
def light(c,k=.28): r=hx(c); return th(tuple(v+(255-v)*k for v in r))
def dark(c,k=.22): r=hx(c); return th(tuple(v*(1-k) for v in r))
class PX:
    def __init__(s,w,h): s.w,s.h=w,h; s.g=[[None]*w for _ in range(h)]
    def set(s,x,y,c):
        x,y=int(round(x)),int(round(y))
        if 0<=x<s.w and 0<=y<s.h: s.g[y][x]=c
    def rect(s,x0,y0,x1,y1,c):
        for y in range(int(y0),int(y1)+1):
            for x in range(int(x0),int(x1)+1): s.set(x,y,c)
    def ell(s,cx,cy,rx,ry,c,shade=True):
        for y in range(s.h):
            for x in range(s.w):
                d=((x-cx)/rx)**2+((y-cy)/ry)**2
                if d<=1:
                    t=((x-cx)/rx+(y-cy)/ry)
                    col=c
                    if shade and t<-0.75: col=light(c)
                    elif shade and t>0.8: col=dark(c)
                    s.g[y][x]=col
    def line(s,x0,y0,x1,y1,c,w=1):
        n=int(max(abs(x1-x0),abs(y1-y0)))*2+1
        for i in range(n+1):
            t=i/n; x=x0+(x1-x0)*t; y=y0+(y1-y0)*t
            s.set(x,y,c)
            if w>1: s.set(x+1,y,c)
    def poly(s,pts,c):
        for y in range(s.h):
            for x in range(s.w):
                ins=False; n=len(pts)
                for i in range(n):
                    x1,y1=pts[i]; x2,y2=pts[(i+1)%n]
                    if (y1>y)!=(y2>y) and x<(x2-x1)*(y-y1)/(y2-y1)+x1: ins=not ins
                if ins: s.g[y][x]=c
    def pts(s,lst,c):
        for x,y in lst: s.set(x,y,c)
    def outline(s,ink=INK):
        o=[row[:] for row in s.g]
        for y in range(s.h):
            for x in range(s.w):
                if s.g[y][x] is None:
                    for dx,dy in((1,0),(-1,0),(0,1),(0,-1)):
                        nx,ny=x+dx,y+dy
                        if 0<=nx<s.w and 0<=ny<s.h and s.g[ny][nx] is not None and s.g[ny][nx]!=ink: o[y][x]=ink;break
        s.g=o
    def export(s):
        pal={};rows=[]
        letters="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        for row in s.g:
            r=""
            for c in row:
                if c is None: r+="."
                else:
                    if c not in pal: pal[c]=letters[len(pal)]
                    r+=pal[c]
            rows.append(r)
        return {"w":s.w,"h":s.h,"pal":{v:k for k,v in pal.items()},"rows":rows}
SK="#ffe0c8"
def base(p,skin=SK,body="#6ec6ff",legs=None,wide=0):
    legs=legs or dark(body,.25)
    p.rect(6,13,7,14,legs); p.rect(9,13,10,14,legs)
    p.ell(8,11.3,3.3+wide,2.6,body)
    p.ell(8,6.2,4,3.5,skin)
def eyes(p,y=6,dx=2):
    p.set(8-dx,y,INK); p.set(8+dx,y,INK)
    p.set(8-dx-1,y+1,"#ff9fc0"); p.set(8+dx+1,y+1,"#ff9fc0")

def ranger():
    p=PX(16,16); G="#6bbf59"
    base(p,body="#b07a4a")
    p.rect(5,11,11,11,dark("#b07a4a",.4))
    p.ell(8,4.6,5,3.6,G); p.ell(8,6.8,3.3,2.7,SK)
    p.pts([(12,1),(13,1),(13,2),(14,2),(14,3)],"#ff8fb8")
    eyes(p,7,1.8)
    for (x,y) in [(13,7),(14,8),(14,9),(14,10),(14,11),(13,12)]: p.set(x,y,"#8a5a30")
    p.line(13,7,13,12,"#ffffff")
    p.outline(); return p
def pyro():
    p=PX(16,16)
    base(p,body="#ff9f5a")
    p.rect(5,13,11,13,"#ffd45e")
    p.ell(8,4.5,4.6,3.4,"#ff7a5a")
    p.pts([(5,1),(6,0),(8,1),(10,0),(11,1)],"#ffb04a"); p.pts([(6,1),(8,2),(10,1)],"#ffd45e")
    p.ell(8,7,3.2,2.4,SK); eyes(p,7,1.8)
    p.ell(13,9,1.7,1.7,"#ff8f3a"); p.ell(13,9,0.9,0.9,"#fff7a8",False)
    p.outline(); return p
def rogue():
    p=PX(16,16); H="#7a5cc0"
    base(p,body="#6a52a8")
    p.ell(8,5.6,4.6,4,H)
    p.rect(5,5,11,6,SK); p.rect(5,7,11,8,"#4b3a7a")
    p.set(6,5,INK); p.set(10,5,INK)
    p.pts([(12,9),(13,10),(14,10),(14,11)],"#ff8fb8")
    p.rect(11,10,11,12,"#d0d8e8"); p.set(11,13,"#8a5a30")
    p.rect(2,9,2,12,"#d0d8e8"); p.set(2,13,"#8a5a30")
    p.outline(); return p
def guardian():
    p=PX(16,16)
    p.rect(6,13,7,14,"#7d8cac"); p.rect(9,13,10,14,"#7d8cac")
    p.ell(8,11.2,4.6,2.8,"#9fb0cc")
    p.rect(7,11,9,12,"#ffd45e")
    p.ell(8,5.6,4.6,4,"#b9c2d4")
    p.rect(5,5,11,6,"#5a6a8a"); p.set(6,6,"#ffffff"); p.set(10,6,"#ffffff")
    p.pts([(8,0),(8,1),(7,1),(9,1)],"#ff8fb8")
    p.ell(3.2,10.5,2.3,3.2,"#ffd45e"); p.ell(3.2,10.5,1,1.6,"#ff8fb8",False)
    p.outline(); return p
def cryo():
    p=PX(16,16)
    base(p,body="#8ec5ff")
    p.pts([(8,10),(7,11),(9,11),(8,12),(8,11)],"#ffffff")
    p.ell(8,5.2,5,4,"#bfe0ff"); p.ell(8,6.9,3.3,2.7,SK); eyes(p,7,1.8)
    p.poly([(8,0.5),(9.8,2.4),(8,4),(6.2,2.4)],"#7fd6ff"); p.set(7,2,"#ffffff")
    p.line(13,6,13,14,"#cfe8ff"); p.poly([(13,3),(14.5,4.6),(13,6.2),(11.5,4.6)],"#7fd6ff")
    p.outline(); return p
def summoner():
    p=PX(16,16)
    base(p,body="#3d7f6e")
    p.pts([(8,9),(7,10),(9,10)],"#b9ffcf")
    p.ell(8,5.2,5,4,"#4aa088"); p.ell(8,6.9,3.3,2.7,SK); eyes(p,7,1.8)
    p.ell(13,10.5,1.6,2.1,"#eafff6"); p.set(12,10,INK); p.set(14,10,INK); p.set(12,12,None); p.set(14,13,"#eafff6")
    p.outline(); return p
def storm():
    p=PX(16,16)
    base(p,body="#6a8cff")
    p.pts([(8,10),(7,11),(8,11),(7,12)],"#ffe45c")
    p.ell(8,4.6,4.8,3.4,"#ffe45c")
    p.pts([(4,2),(6,1),(8,0),(10,1),(12,2)],"#ffd45e")
    p.ell(8,6.9,3.3,2.7,SK); eyes(p,7,1.8)
    p.pts([(14,8),(13,9),(12,10),(13,10),(14,10),(13,11),(12,12)],"#fff7a8")
    p.outline(); return p
def bomber():
    p=PX(16,16)
    base(p,body="#ff9f5a")
    p.line(5,9,11,13,dark("#ff9f5a",.5))
    p.ell(8,4.6,4.9,3.5,"#c9894f"); p.ell(8,6.9,3.3,2.7,SK)
    p.rect(5,5,11,6,"#ffd45e"); p.pts([(6,5),(10,5)],"#7fd6ff")
    p.set(5,8,"#ff9fc0"); p.set(11,8,"#ff9fc0")
    p.ell(12.8,11,1.8,1.8,"#3b2c4f"); p.set(12,10,"#8a7aa8")
    p.pts([(13,8),(14,7)],"#ff8f3a"); p.set(14,6,"#fff7a8")
    p.outline(); return p
def venom():
    p=PX(16,16)
    base(p,body="#b57ae8")
    p.rect(5,13,11,13,"#ff9fc0")
    p.ell(8,4.2,4.6,3.3,"#7ed957"); p.ell(8,1.9,1.8,1.5,"#7ed957")
    p.ell(8,6.9,3.3,2.7,SK); eyes(p,7,1.8)
    p.rect(13,8,13,9,"#cfe8ff"); p.ell(13,11.2,1.6,2,"#7ed957"); p.set(13,6,"#c8ffb0"); p.set(14,5,"#c8ffb0")
    p.outline(); return p
def sniper():
    p=PX(16,16)
    base(p,body="#c8b88a")
    p.pts([(6,11),(9,12),(10,10)],"#a89868")
    p.rect(5,9,11,9,"#ff8fb8")
    p.ell(8,3.6,5.8,1.3,"#f5d58a"); p.ell(8,4.3,3.6,2.5,"#f5d58a")
    p.ell(8,6.9,3.2,2.5,SK); eyes(p,7,1.8)
    p.line(2,11,14,10,"#6a6a7a"); p.rect(1,10,3,12,"#8a5a30"); p.set(9,9,"#7fd6ff")
    p.outline(); return p
CHARS=[("ranger","Fenn","Jäger",ranger),("pyro","Mira","Pyromantin",pyro),("rogue","Kaz","Schurke",rogue),("guardian","Brun","Wächter",guardian),
       ("cryo","Ysa","Frostmagierin",cryo),("summoner","Thorn","Beschwörer",summoner),("storm","Vex","Sturmrufer",storm),
       ("bomber","Orm","Sprengmeister",bomber),("venom","Lilu","Giftmischerin",venom),("sniper","Aya","Scharfschützin",sniper)]
