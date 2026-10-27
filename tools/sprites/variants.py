from px import *
import px
SKIN="#ffe0c8"
def outline_sel(p,k=.5):
    o=[row[:] for row in p.g]
    for y in range(p.h):
        for x in range(p.w):
            if p.g[y][x] is None:
                for dx,dy in((1,0),(-1,0),(0,1),(0,-1)):
                    nx,ny=x+dx,y+dy
                    if 0<=nx<p.w and 0<=ny<p.h and p.g[ny][nx] is not None:
                        o[y][x]=dark(p.g[ny][nx],k);break
    p.g=o
def A():
    return px.ranger()
def B():
    p=PX(16,24); S="#f3cfae"; ink="#3a2a3a"
    p.rect(5,15,6,21,"#8a6a4a"); p.rect(9,15,10,21,"#8a6a4a")
    p.rect(5,20,6,22,"#4a3a30"); p.rect(9,20,10,22,"#4a3a30")
    p.poly([(4,9),(12,9),(13,19),(3,19)],"#3f7a4a")
    p.rect(5,9,10,15,"#b0804f"); p.rect(5,14,10,14,"#6b4a32"); p.set(8,14,"#ffd45e")
    p.rect(3,10,4,14,"#b0804f"); p.set(3,15,S); p.set(4,15,S)
    p.rect(10,7,11,12,"#8a5a30"); p.set(10,6,"#ff8fb8"); p.set(11,6,"#ff8fb8")
    p.ell(8,4.2,4.4,3.7,"#4f9a5a"); p.ell(8,5.6,2.7,2.5,S)
    p.set(7,5,ink); p.set(9,5,ink)
    p.pts([(12,4),(13,5),(14,7),(14,10),(14,13),(14,16),(13,18),(12,19)],"#8a5a30")
    p.line(12,5,12,18,"#ffffff")
    p.outline(ink); p.set(7,5,ink); p.set(9,5,ink); return p
def C():
    p=PX(12,12); G="#6bbf59"
    p.pts([(3,11),(4,11),(8,11),(9,11)],dark(G,.35))
    p.ell(6,6.4,5,4.5,G); p.ell(6,8,3,1.8,"#a7de8f",False)
    p.poly([(6,0.6),(8.6,2.2),(6,3.4),(3.4,2.2)],"#3f8a3f"); p.pts([(9,1),(10,0)],"#ff8fb8")
    p.ell(4,5.6,1.6,1.8,"#ffffff",False); p.ell(8,5.6,1.6,1.8,"#ffffff",False)
    p.pts([(4,6),(8,6)],INK); p.pts([(3,8),(9,8)],"#ff9fc0")
    p.pts([(11,4),(11,5),(11,6),(11,7)],"#8a5a30")
    return p
def D():
    base=px.ranger(); p=PX(16,16)
    G=["#0f380f","#306230","#8bac0f","#9bbc0f"]; bayer=[[0,2],[3,1]]
    for y in range(16):
        for x in range(16):
            c=base.g[y][x]
            if c is None: continue
            if c==INK: p.g[y][x]=G[0]; continue
            r,g,b=hx(c); lum=(0.3*r+0.59*g+0.11*b)/255
            if (x+y)%2==0 and 0.50<lum<0.72: lum-=0.08
            i=3 if lum>0.80 else 2 if lum>0.58 else 1 if lum>0.30 else 0
            p.g[y][x]=G[max(i,1) if i==0 else i]
    return p
def E():
    p=PX(32,32); S="#ffe0c8"; ink=INK
    p.poly([(9,13),(23,13),(26,29),(6,29)],"#3f7a4a")
    for x in (11,16,21): p.line(x,15,x+(x-16)//4,28,dark("#3f7a4a",.25))
    p.rect(12,26,14,30,"#8a6a4a"); p.rect(18,26,20,30,"#8a6a4a"); p.rect(11,29,14,31,"#4a3a30"); p.rect(18,29,21,31,"#4a3a30")
    p.ell(16,19,5.2,6,"#b0804f"); p.rect(11,22,21,23,"#6b4a32"); p.rect(15,22,17,23,"#ffd45e")
    p.line(11,16,9,22,"#b0804f"); p.line(21,16,25,19,"#b0804f"); p.ell(9,23,1.5,1.5,S,False); p.ell(26,19,1.6,1.6,S,False)
    p.rect(21,9,23,18,"#8a5a30"); p.pts([(21,8),(23,8)],"#cfd8e8"); p.pts([(21,7),(23,7),(22,6)],"#ff8fb8")
    for (x,y) in [(26,8),(27,10),(28,13),(28,16),(28,19),(28,22),(27,25),(26,27)]: p.set(x,y,"#8a5a30"); p.set(x-1,y,"#8a5a30")
    p.line(25,8,25,27,"#ffffff")
    p.ell(16,9,8,7,"#6bbf59"); p.ell(16,11.2,5,4.4,S)
    p.rect(13,11,13,12,ink); p.rect(19,11,19,12,ink); p.set(13,11,"#ffffff"); p.set(19,11,"#ffffff")
    p.pts([(12,13),(20,13)],"#ff9fc0"); p.pts([(15,14),(16,14),(17,14)],"#d9806a")
    p.poly([(22,4),(24,2),(29,0),(26,4),(23,6)],"#ff8fb8"); p.line(22,5,28,1,"#ffc2d8")
    outline_sel(p,.5); return p
ALL=[("A","Kuschel-Chibi","Großer Kopf, 16 px",A),("B","Klassik-RPG","Echte Proportionen, 24 px",B),("C","Bohnen-Maskottchen","Minimal, ohne Rand, 12 px",C),
     ("D","Handheld-Raster","4 Töne mit Rasterung",D),("E","Detail-Illustration","32 px, weiche Konturen",E)]
