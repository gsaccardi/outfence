"""Generate original vector brand assets and matching high-resolution PNG exports.
Requires Pillow for PNG export; uses system Arial or a supplied OUTFENCE_FONT_DIR.
No network requests or third-party artwork. Run from any directory.
"""
from pathlib import Path
import os
import html
import json
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'brand/assets'
OUT.mkdir(parents=True,exist_ok=True)
FONT=Path(os.environ.get('OUTFENCE_FONT_DIR','/System/Library/Fonts/Supplemental'))
INK='#102B2A'; MINT='#A6F0CD'; PAPER='#F7F5EF'; MUTED='#526563'; LINE='#D6DDD5'; GREEN='#17664D'; RED='#A43135'; AMBER='#865500'
SCALE=2
class Canvas:
 def __init__(self,w,h,bg=None):
  self.w=w;self.h=h;self.parts=[]
  self.im=Image.new('RGBA',(w*SCALE,h*SCALE),(0,0,0,0));self.d=ImageDraw.Draw(self.im)
  if bg:self.rect(0,0,w,h,bg)
 def rect(self,x,y,w,h,c,r=0):
  self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{c}"/>')
  self.d.rounded_rectangle((x*SCALE,y*SCALE,(x+w)*SCALE,(y+h)*SCALE),radius=r*SCALE,fill=c)
 def line(self,pts,c,width=8):
  self.parts.append(f'<polyline points="'+ ' '.join(f'{x},{y}' for x,y in pts)+f'" fill="none" stroke="{c}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>')
  p=[(int(x*SCALE),int(y*SCALE)) for x,y in pts]
  self.d.line(p,fill=c,width=round(width*SCALE),joint='curve')
  r=width*SCALE/2
  for x,y in p:self.d.ellipse((x-r,y-r,x+r,y+r),fill=c)
 def circle(self,x,y,r,c):
  self.parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{c}"/>')
  self.d.ellipse(((x-r)*SCALE,(y-r)*SCALE,(x+r)*SCALE,(y+r)*SCALE),fill=c)
 def text(self,x,y,t,size=24,c=INK,bold=False,mono=False):
  fn='Courier New.ttf' if mono else ('Arial Bold.ttf' if bold else 'Arial.ttf')
  f=ImageFont.truetype(str(FONT/fn),round(size*SCALE))
  family='Courier New, monospace' if mono else 'Arial, Helvetica, sans-serif'
  self.parts.append(f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{700 if bold else 400}" fill="{c}">{html.escape(t)}</text>')
  self.d.text((x*SCALE,y*SCALE),t,font=f,fill=c,anchor='ls')
 def mark(self,x,y,size,base=INK,accent=INK):
  def p(a,b):return (x+a*size/100,y+b*size/100)
  self.line([p(66,18),p(22,18),p(22,82),p(66,82)],base,size*.085)
  self.line([p(43,50),p(88,50)],accent,size*.085)
  self.circle(*p(43,50),size*.068,accent)
  self.line([p(77,39),p(88,50),p(77,61)],accent,size*.07)
 def save(self,name,title):
  title=html.escape(title)
  (OUT/f'{name}.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}" role="img" aria-labelledby="title"><title id="title">{title}</title>'+''.join(self.parts)+'</svg>')
  self.im.resize((self.w,self.h),Image.Resampling.LANCZOS).save(OUT/f'{name}.png')

for name,color in [('mark-ink',INK),('mark-white',PAPER)]:
 c=Canvas(256,256);c.mark(0,0,256,color,color);c.save(name,'Outfence boundary and outbound path symbol')
c=Canvas(512,512,INK);c.mark(72,72,368,MINT,MINT);c.save('avatar','Outfence avatar')
for name,bg,fg in [('wordmark-light',None,INK),('wordmark-dark',INK,PAPER)]:
 c=Canvas(760,180,bg);c.mark(8,20,140,fg,fg);c.text(180,123,'outfence',96,fg,True);c.save(name,'Outfence wordmark')
c=Canvas(1600,560,INK)
c.mark(64,42,88,MINT,MINT);c.text(168,104,'outfence',48,PAPER,True)
c.text(80,258,'Know where your',76,PAPER,True);c.text(80,347,'agents connect.',76,PAPER,True)
c.text(84,448,'Local policies. Reviewable evidence.',28,MINT)
c.text(84,511,'LOCAL PROXY ALPHA  /  0.1.0a1',16,'#ADC4BD',mono=True)
c.mark(1090,125,340,MINT,MINT);c.save('banner','Outfence — Know where your agents connect. Local proxy alpha.')
c=Canvas(1280,640,INK)
c.mark(64,48,82,MINT,MINT);c.text(160,108,'outfence',44,PAPER,True)
c.text(72,263,'Know where your',72,PAPER,True);c.text(72,347,'agents connect.',72,PAPER,True)
c.text(76,425,'Inspect connections. Set boundaries.',26,MINT)
c.text(76,585,'OPEN SOURCE  /  LOCAL PROXY ALPHA',16,'#ADC4BD',mono=True)
c.mark(932,349,240,MINT,MINT);c.save('social-preview','Outfence GitHub social preview — local proxy alpha')
c=Canvas(1600,1200,PAPER)
c.text(70,62,'OUTFENCE  /  IDENTITY PROPOSAL 01',16,MUTED,mono=True)
c.text(70,173,'A clear boundary.',76,INK,True);c.text(70,257,'An observable path.',76,INK,True)
c.text(74,311,'Know where your agents connect.',27,MUTED)
c.rect(70,361,930,377,INK,24);c.mark(120,399,148,MINT,MINT);c.text(294,508,'outfence',83,PAPER,True)
c.text(122,626,'Local policies.',35,PAPER);c.text(122,680,'Reviewable evidence.',35,MINT)
c.rect(1030,361,500,377,'#E8ECE4',24);c.mark(1101,391,255,INK,INK)
c.text(1078,701,'BOUNDARY + OUTBOUND PATH',16,MUTED,mono=True)
colors=[('INK',INK),('MINT',MINT),('PAPER',PAPER),('SLATE',MUTED),('PASS',GREEN),('BLOCK',RED)]
for i,(label,color) in enumerate(colors):
 x=70+i*246;c.rect(x,792,226,113,color,12)
 if label=='PAPER':c.line([(x,905),(x+226,905)],LINE,2)
 c.text(x,944,label,16,INK,True);c.text(x,975,color,18,MUTED,mono=True)
c.line([(70,1024),(1530,1024)],LINE,2)
c.text(70,1080,'Precise. Calm. Developer-first.',28,INK,True)
c.text(70,1131,'Editable SVG + PNG exports  /  Working name; availability not reserved.',20,MUTED)
c.save('brand-board','Outfence identity proposal with logo, palette and typography')
(ROOT/'brand/tokens.json').write_text(json.dumps({'name':'Outfence','status':'proposal','colors':{'ink':INK,'mint':MINT,'paper':PAPER,'slate':MUTED,'line':LINE,'success':GREEN,'warning':AMBER,'danger':RED},'typography':{'sans':'Arial, Helvetica, sans-serif','mono':'Courier New, monospace'},'spacing':[4,8,12,16,24,32,48,64,80]},indent=2)+'\n')
print('Exported 8 SVG/PNG asset pairs and tokens.json')
