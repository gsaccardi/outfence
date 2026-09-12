"""Generate Outfence's vector-first identity and matching PNG exports.

Requires Pillow and Arial system fonts, or OUTFENCE_FONT_DIR. All symbol geometry
is original; no fonts or third-party artwork are bundled. SVG marks use true arcs.
"""

import html
import json
import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'brand/assets'
OUT.mkdir(parents=True, exist_ok=True)
FONT = Path(os.environ.get('OUTFENCE_FONT_DIR', '/System/Library/Fonts/Supplemental'))
INK, PAPER, ACCENT, MUTED = '#171917', '#FAFAF7', '#D9F378', '#656B63'
SCALE = 3


class Canvas:
    def __init__(self, width, height, background=None):
        self.width, self.height, self.parts = width, height, []
        self.im = Image.new('RGBA', (width * SCALE, height * SCALE))
        self.draw = ImageDraw.Draw(self.im)
        if background:
            self.rect(0, 0, width, height, background)

    def rect(self, x, y, width, height, color):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" fill="{color}"/>')
        self.draw.rectangle((x*SCALE, y*SCALE, (x+width)*SCALE, (y+height)*SCALE), fill=color)

    def text(self, x, y, text, size, color=INK, tracking=0):
        font = ImageFont.truetype(str(FONT/'Arial.ttf'), round(size*SCALE))
        self.parts.append(f'<text x="{x}" y="{y}" font-family="Arial, Helvetica, sans-serif" font-size="{size}" letter-spacing="{tracking}" fill="{color}">{html.escape(text)}</text>')
        cursor = x*SCALE
        for char in text:
            self.draw.text((cursor, y*SCALE), char, font=font, fill=color, anchor='ls')
            cursor += self.draw.textlength(char, font=font) + tracking*SCALE

    def mark(self, x, y, size, color=INK):
        # Two identical annular sectors, offset along the axis of their openings.
        # The silhouette is an O; the negative space is an intentional passage.
        radius, inner = size*.335, size*.205
        for start, end, dx, dy in [(53, 217, -.018, .018), (233, 397, .018, -.018)]:
            cx, cy = x+size*(.5+dx), y+size*(.5+dy)
            def point(r, degrees):
                radians = math.radians(degrees)
                return cx+r*math.cos(radians), cy+r*math.sin(radians)
            a, b, c, d = point(radius,start), point(radius,end), point(inner,end), point(inner,start)
            path = f'M {a[0]:.4f} {a[1]:.4f} A {radius:.4f} {radius:.4f} 0 0 1 {b[0]:.4f} {b[1]:.4f} L {c[0]:.4f} {c[1]:.4f} A {inner:.4f} {inner:.4f} 0 0 0 {d[0]:.4f} {d[1]:.4f} Z'
            self.parts.append(f'<path d="{path}" fill="{color}"/>')
            angles = [start+(end-start)*i/180 for i in range(181)]
            points = [point(radius,t) for t in angles] + [point(inner,t) for t in reversed(angles)]
            self.draw.polygon([(round(px*SCALE),round(py*SCALE)) for px,py in points],fill=color)

    def save(self, name, title):
        (OUT/f'{name}.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" viewBox="0 0 {self.width} {self.height}" role="img" aria-labelledby="title"><title id="title">{html.escape(title)}</title>'+''.join(self.parts)+'</svg>')
        self.im.resize((self.width,self.height),Image.Resampling.LANCZOS).save(OUT/f'{name}.png')


for name, color in [('mark-ink',INK),('mark-white',PAPER)]:
    c=Canvas(256,256);c.mark(0,0,256,color);c.save(name,'Outfence split-ring symbol')
c=Canvas(512,512,INK);c.mark(16,16,480,PAPER);c.save('avatar','Outfence avatar')
for name,background,color in [('wordmark-light',None,INK),('wordmark-dark',INK,PAPER)]:
    c=Canvas(760,180,background);c.mark(6,14,152,color);c.text(184,120,'outfence',94,color,-3);c.save(name,'Outfence wordmark')
c=Canvas(1600,560,PAPER)
c.mark(74,132,300);c.text(410,342,'outfence',150,INK,-5)
c.text(422,410,'Know where your agents connect.',27,MUTED,-.3)
c.rect(1454,62,74,6,ACCENT);c.text(80,507,'LOCAL POLICIES. REVIEWABLE EVIDENCE.',15,MUTED,1)
c.save('banner','Outfence — Know where your agents connect')
c=Canvas(1280,640,INK)
c.mark(66,148,318,PAPER);c.text(416,360,'outfence',126,PAPER,-4)
c.text(426,428,'Know where your agents connect.',24,'#C2C6BC',-.3)
c.rect(1122,60,86,6,ACCENT);c.text(78,578,'OPEN SOURCE',14,'#C2C6BC',2)
c.save('social-preview','Outfence — local policies, reviewable evidence')
c=Canvas(1600,1050,PAPER)
c.text(64,61,'OUTFENCE',15,INK,2);c.text(1210,61,'IDENTITY / 02',14,MUTED,1.5)
c.mark(92,160,314);c.text(450,373,'outfence',142,INK,-5)
c.text(457,438,'Know where your agents connect.',25,MUTED,-.2)
c.rect(0,578,800,390,INK);c.mark(245,630,290,PAPER)
c.rect(800,578,800,390,'#ECEEE7');c.mark(1060,644,258,INK)
c.rect(1460,880,60,6,ACCENT)
c.text(64,1018,'TWO FORMS. ONE OPENING.',13,MUTED,1.4)
c.text(1192,1018,'MONOCHROME FIRST',13,MUTED,1)
c.save('brand-board','Outfence minimal identity: split-ring mark and lowercase wordmark')
(ROOT/'brand/tokens.json').write_text(json.dumps({
    'name':'Outfence','identity_version':2,
    'colors':{'ink':INK,'paper':PAPER,'accent':ACCENT,'slate':MUTED,'line':'#D9DDD3','success':'#17664D','warning':'#865500','danger':'#A43135'},
    'typography':{'sans':'Arial, Helvetica, sans-serif','mono':'Courier New, monospace'},
    'spacing':[4,8,12,16,24,32,48,64,80]},indent=2)+'\n')
print('Exported 8 SVG/PNG pairs: identity 02.')
