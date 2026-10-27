from px import *
def ildra():
    p=PX(32,32); G="#5aa05a"; P="#ff8fb8"
    for a in range(0,360,45):
        x=16+7*math.cos(math.radians(a)); y=9+6*math.sin(math.radians(a))
        p.ell(x,y,3.2,3,P if a%90==0 else light(P,.25))
    p.poly([(9,17),(23,17),(28,30),(4,30)],G)
    for i,(x1,x2) in enumerate([(8,10),(12,13),(16,16),(20,19),(24,22)]): p.line(x1,19,x2+ (i-2)*2,29,dark(G,.3))
    p.pts([(5,30),(8,30),(11,31),(15,30),(18,31),(22,30),(25,31),(27,30)],G)
    p.ell(16,10,4.6,4.4,"#e6f7b0"); p.ell(16,10,4.6,4.4,"#e6f7b0",False)
    p.rect(13,9,14,11,INK); p.rect(18,9,19,11,INK); p.set(13,9,"#ffffff"); p.set(18,9,"#ffffff")
    p.rect(14,13,17,13,"#c8506a")
    for x in (10,13,16,19,22): p.poly([(x-1.3,5),(x+1.3,5),(x,1)],"#ff6b6b")
    p.line(8,19,2,12,dark(G,.1)); p.line(24,19,30,12,dark(G,.1))
    for (x,y) in [(3,13),(5,15),(29,13),(27,15),(2,11),(30,11)]: p.poly([(x-1,y+1),(x+1,y+1),(x,y-1.5)],"#ff6b6b")
    p.outline(); return p
def skarra():
    p=PX(32,32); S="#e8c47a"; D=dark(S,.28)
    for sx in (-1,1):
        for i,y in enumerate((23,26,29)): p.line(16+sx*7,y-1,16+sx*(11+i*1),y+2,D)
    p.ell(16,21,9,5.5,S)
    for x in (11,16,21): p.line(x,17,x,25,D)
    p.ell(16,16,5,3.6,light(S,.1))
    for sx in (-1,1):
        p.line(16+sx*5,16,16+sx*10,11,D)
        p.ell(16+sx*12,8,4.3,3.6,S); p.poly([(16+sx*12,4),(16+sx*16,7),(16+sx*14,9)],dark(S,.05)); p.set(16+sx*15,6,None); p.set(16+sx*14,7,None); p.ell(16+sx*11,8.5,1.2,1.1,"#ff8fb8",False)
    p.pts([(13,16),(19,16)],"#ffffff"); p.pts([(13,17),(19,17)],INK); p.pts([(14,14)],"#ffd45e");p.pts([(15,13),(16,12),(17,13)],"#ffd45e")
    for (x,y,r) in [(18,13,2.2),(21,10,2.1),(21,6,2),(18,3,1.9)]: p.ell(x,y,r,r,S)
    p.poly([(16,2),(14,5),(18,5)],"#ff6b6b")
    p.outline(); return p
def kalthorn():
    p=PX(32,32); B="#bfe0ff"
    p.ell(21,27,5,3.4,dark(B,.05)); p.ell(12,24,6,4,B); p.ell(21,19,7.5,4.5,light(B,.05))
    for (x,y) in [(9,22),(14,22),(19,17),(24,17),(21,25)]: p.set(x,y,"#ffffff")
    p.ell(15,10,9,7.2,light(B,.1))
    p.ell(15,12.5,5.5,3.6,"#5a3a6a",False); p.poly([(11,10.5),(19,10.5),(15,14)],"#ffffff"); p.poly([(11,14.5),(19,14.5),(15,12)],"#ffffff")
    p.rect(9,7,10,8,INK); p.rect(20,7,21,8,INK); p.set(9,7,"#ffffff"); p.set(20,7,"#ffffff")
    for x in (8,12,16,20,23): p.poly([(x-1.4,4),(x+1.4,4),(x,0)],"#ffffff")
    p.outline(); return p
def ignarok():
    p=PX(32,32); C="#ff9f86"
    p.rect(9,26,13,30,dark(C,.3)); p.rect(19,26,23,30,dark(C,.3))
    p.ell(16,19,9.5,8,C)
    p.ell(5,21,4.2,4.2,light(C,.05)); p.ell(27,21,4.2,4.2,light(C,.05))
    p.ell(16,9,5.2,4.6,light(C,.08))
    for pts in [[(10,16),(13,19),(11,22),(14,25)],[(21,15),(19,18),(22,21),(20,24)],[(3,19),(5,22)],[(29,19),(27,22)]]:
        for a,b in zip(pts,pts[1:]): p.line(a[0],a[1],b[0],b[1],"#ffd45e")
    for (x,h) in [(12,5),(14,7),(16,8),(18,7),(20,5)]: p.poly([(x-1.4,5),(x+1.4,5),(x,5-h/1.6)],"#ffb04a" if x%4==0 else "#ffd45e")
    p.rect(13,8,14,9,"#fff7a8"); p.rect(18,8,19,9,"#fff7a8"); p.set(14,9,INK); p.set(19,9,INK)
    p.rect(13,12,19,12,"#ffd45e")
    p.outline(); return p
def reaper():
    p=PX(32,32); D="#2a1d3d"
    p.poly([(9,15),(23,15),(27,29),(5,29)],D)
    for x in (9,13,17,21): p.line(x,17,x+(x-16)//4,28,"#3a2a52")
    p.pts([(5,30),(8,30),(10,31),(13,30),(16,31),(19,30),(22,31),(25,30),(27,30)],D)
    p.ell(16,9,7.5,7.5,"#3a2a52"); p.ell(16,10,5,5,"#120a1c",False)
    p.rect(13,9,14,10,"#fff7a8"); p.rect(18,9,19,10,"#fff7a8")
    p.line(29,3,29,30,"#8a6a4a")
    p.poly([(29,2),(21,3),(18,7),(24,5),(29,5)],"#cfe8ff"); p.line(21,3,28,3,"#ffffff")
    p.ell(26,17,1.5,1.5,"#f5f0ff",False); p.ell(7,19,1.5,1.5,"#f5f0ff",False)
    p.line(8,19,12,17,D)
    p.outline(); return p
BOSSES=[("ildra","Ildra","Dornenkönigin",ildra,"forest"),("skarra","Skarra","Sandkönigin",skarra,"desert"),("kalthorn","Kalthorn","Eiswurm",kalthorn,"ice"),
        ("ignarok","Ignarok","Glutkoloss",ignarok,"lava"),("reaper","Der Schnitter","Endboss",reaper,"plaza")]
