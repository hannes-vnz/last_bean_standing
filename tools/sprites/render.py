import sys, json
from PIL import Image
sys.path.insert(0,'.')
import px
def draw(sheet, items, scale, cols, bg):
    cell=max(i["w"] for i in items)*scale+16; rows=(len(items)+cols-1)//cols
    ch=max(i["h"] for i in items)*scale+16
    im=Image.new("RGB",(cols*cell,rows*ch),bg)
    for n,i in enumerate(items):
        ox=(n%cols)*cell+8; oy=(n//cols)*ch+8
        for y,row in enumerate(i["rows"]):
            for x,c in enumerate(row):
                if c!=".":
                    col=px.hx(i["pal"][c])
                    for dy in range(scale):
                        for dx in range(scale): im.putpixel((ox+x*scale+dx,oy+y*scale+dy),col)
    im.save(sheet)
if __name__=="__main__":
    items=[f().export() for _,_,_,f in px.CHARS]
    draw("chars.png",items,8,5,(166,221,130))
