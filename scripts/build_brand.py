"""Generate Outfence identity 03: the Capitoline goose in mosaic tiles, IBM Plex type, PNG exports.

Requires Pillow, fontTools and the IBM Plex TTFs (SIL Open Font License) in OUTFENCE_FONT_DIR:
IBMPlexSans-Regular, IBMPlexSans-Medium, IBMPlexMono-Regular and IBMPlexMono-Medium. Tile art
lives in brand/mascot.json. SVG text is outlined, so the SVGs render the same without the fonts.
"""

import html
import json
import math
import os
import random
import re
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(os.environ.get('OUTFENCE_BRAND_ROOT', Path(__file__).resolve().parents[1]))
OUT = ROOT / 'brand/assets'
OUT.mkdir(parents=True, exist_ok=True)
FONTS = Path(os.environ.get('OUTFENCE_FONT_DIR', ROOT / 'fonts'))
ART = json.loads((ROOT / 'brand/mascot.json').read_text())
INK, PAPER, ACCENT, MUTED, LINE, MIST = '#171917', '#FAFAF7', '#D9F378', '#656B63', '#D9DDD3', '#C2C6BC'
TAGLINE = 'Know where your agents connect.'
SCALE = 3

# Mosaic tiles vary slightly in tone and angle, like hand-cut tesserae. The mark never does.
MOSAIC = {'k': ('#171917', '#23251F', '#1D1F1B'), 'w': ('#F4F4EE', '#EFF0E8', '#F7F7F2'),
          'a': ('#D9F378', '#CFEA6A', '#E1F68C'), 's': ('#E2E4DB', '#DCDED5')}
MOSAIC_DARK = {'k': ('#4A4E47', '#43473F'), 'w': ('#FAFAF7', '#F1F1EA', '#E8E9E2'),
               'a': MOSAIC['a'], 's': ('#262923', '#2A2D27')}


def unrle(text):
    return [re.sub(r'(\d*)(\D)', lambda m: m[2] * int(m[1] or 1), row) for row in text.split('|')]


MARK, POSES = unrle(ART['mark']), {name: unrle(rows) for name, rows in ART['poses'].items()}


class Font:
    def __init__(self, name):
        self.path = FONTS / f'{name}.ttf'
        tt = TTFont(self.path)
        self.glyphs, self.cmap, self.upm = tt.getGlyphSet(), tt.getBestCmap(), tt['head'].unitsPerEm

    def layout(self, text, size, tracking=0):
        x, out = 0, []
        for char in text:
            name = self.cmap[ord(char)]
            out.append((name, char, x))
            x += self.glyphs[name].width * size / self.upm + tracking
        return out, x - tracking


SANS, SANS_MEDIUM, MONO, MONO_MEDIUM = (Font(n) for n in (
    'IBMPlexSans-Regular', 'IBMPlexSans-Medium', 'IBMPlexMono-Regular', 'IBMPlexMono-Medium'))


class Canvas:
    def __init__(self, width, height, background=None):
        self.width, self.height, self.parts = width, height, []
        self.im = Image.new('RGBA', (width * SCALE, height * SCALE))
        self.draw = ImageDraw.Draw(self.im)
        if background:
            self.rect(0, 0, width, height, background)

    def rect(self, x, y, width, height, color):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" fill="{color}"/>')
        self.draw.rectangle((x*SCALE, y*SCALE, (x+width)*SCALE-1, (y+height)*SCALE-1), fill=color)

    def text(self, x, y, text, size, color=INK, tracking=0, font=SANS, align='left'):
        glyphs, width = font.layout(text, size, tracking)
        x -= width if align == 'right' else 0
        pil = ImageFont.truetype(str(font.path), round(size*SCALE))
        commands = []
        for name, char, dx in glyphs:
            pen = SVGPathPen(font.glyphs)
            font.glyphs[name].draw(TransformPen(pen, (size/font.upm, 0, 0, -size/font.upm, x+dx, y)))
            commands.append(pen.getCommands())
            self.draw.text(((x+dx)*SCALE, y*SCALE), char, font=pil, fill=color, anchor='ls')
        self.parts.append(f'<path d="{"".join(commands)}" fill="{color}"/>')

    def tiles(self, rows, x, y, tile, colors, gap=.2, seed=None):
        """Lay tile art row by row. A seed nudges and turns each tile slightly, as if laid by hand."""
        rnd, half, paths = random.Random(seed), tile*(1-gap)/2, {}
        for ty, row in enumerate(rows):
            for tx, key in enumerate(row):
                if key not in colors:
                    continue
                color = colors[key] if isinstance(colors[key], str) else rnd.choice(colors[key])
                cx, cy, turn = x+(tx+.5)*tile, y+(ty+.5)*tile, 0
                if seed is not None:
                    cx, cy = cx+rnd.uniform(-.07, .07)*tile, cy+rnd.uniform(-.07, .07)*tile
                    turn = math.radians(rnd.uniform(-5, 5))
                cos, sin = math.cos(turn), math.sin(turn)
                corners = [(cx+dx*cos-dy*sin, cy+dx*sin+dy*cos) for dx, dy in
                           ((-half, -half), (half, -half), (half, half), (-half, half))]
                paths.setdefault(color, []).append('M'+'L'.join(f'{px:.2f} {py:.2f}' for px, py in corners)+'Z')
                self.draw.polygon([(px*SCALE, py*SCALE) for px, py in corners], fill=color)
        self.parts.extend(f'<path d="{"".join(d)}" fill="{color}"/>' for color, d in paths.items())

    def mark(self, x, y, size, color=INK):
        # The goose head: crest, eye and acid beak on a 14-tile grid, aligned and evenly spaced.
        self.tiles(MARK, x, y, size/len(MARK), {'k': color, 'a': ACCENT}, gap=.16)

    def goose(self, pose, x, y, scale=1, dark=False, seed=390):
        self.tiles(POSES[pose], x, y, 6*scale, MOSAIC_DARK if dark else MOSAIC, seed=seed)

    def save(self, name, title):
        (OUT/f'{name}.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" viewBox="0 0 {self.width} {self.height}" role="img" aria-labelledby="title"><title id="title">{html.escape(title)}</title>'+''.join(self.parts)+'</svg>')
        self.im.resize((self.width, self.height), Image.Resampling.LANCZOS).save(OUT/f'{name}.png')


for name, color in [('mark-ink', INK), ('mark-white', PAPER)]:
    c=Canvas(256,256);c.mark(16,16,224,color);c.save(name,'Outfence goose mark')
c=Canvas(512,512,INK);c.mark(74,74,364,PAPER);c.save('avatar','Outfence avatar')
for name, background, color in [('wordmark-light', None, INK), ('wordmark-dark', INK, PAPER)]:
    c=Canvas(760,180,background);c.mark(20,20,140,color);c.text(188,126,'outfence',112,color,-3.5,SANS_MEDIUM)
    c.save(name,'Outfence wordmark')
for i, pose in enumerate(POSES):
    c=Canvas(400,320);c.goose(pose,2,1,seed=390+i);c.save(f'goose-{pose}',f'Outfence goose, {pose}')
c=Canvas(1600,560,PAPER)
c.goose('alarm',40,110,1.1);c.text(520,318,'outfence',150,INK,-5,SANS_MEDIUM)
c.text(526,390,TAGLINE,30,MUTED,-.3);c.rect(1454,62,74,6,ACCENT)
c.text(80,512,'OPEN SOURCE · APACHE-2.0',15,MUTED,1.5,MONO)
c.save('banner','Outfence: '+TAGLINE)
c=Canvas(1280,640,INK)
c.goose('alarm',36,150,dark=True);c.text(452,350,'outfence',126,PAPER,-4,SANS_MEDIUM)
c.text(458,412,TAGLINE,24,MIST,-.3);c.rect(1122,60,86,6,ACCENT)
c.text(78,578,'OPEN SOURCE',14,MIST,2,MONO)
c.save('social-preview','Outfence: '+TAGLINE)
c=Canvas(1600,1050,PAPER)
c.text(64,61,'OUTFENCE',15,INK,2.5,MONO_MEDIUM);c.text(1536,61,'IDENTITY / 03',14,MUTED,1.5,MONO,'right')
c.mark(92,150,196);c.text(330,300,'outfence',142,INK,-5,SANS_MEDIUM)
c.text(336,362,TAGLINE,25,MUTED,-.2);c.goose('alarm',1124,112)
c.rect(0,560,800,400,INK);c.mark(288,648,224,PAPER)
c.rect(800,560,800,400,'#ECEEE7')
for i, pose in enumerate(('watching', 'blocking', 'approving', 'idle')):
    c.goose(pose,832+i*188,590,.42,seed=400+i);c.text(840+i*188,752,pose,12,MUTED,.5,MONO)
for i, (label, color) in enumerate([('ink',INK),('paper',PAPER),('acid',ACCENT),('slate',MUTED),('line',LINE),('danger','#A43135')]):
    c.rect(839+i*118,791,74,38,LINE);c.rect(840+i*118,792,72,36,color);c.text(840+i*118,850,label,12,MUTED,.5,MONO)
c.text(840,912,'IBM Plex Sans + IBM Plex Mono',20,INK,0,SANS_MEDIUM)
c.text(840,936,'SIL Open Font License',12,MUTED,.5,MONO)
c.text(64,1018,'THE GEESE OF THE CAPITOL',13,MUTED,1.4,MONO)
c.text(1536,1018,'MONOCHROME FIRST · ACID FOR THE ALARM',13,MUTED,1,MONO,'right')
c.save('brand-board','Outfence identity 03: mosaic goose mark, IBM Plex wordmark and goose poses')
(ROOT/'brand/tokens.json').write_text(json.dumps({
    'name':'Outfence','identity_version':3,
    'colors':{'ink':INK,'paper':PAPER,'accent':ACCENT,'slate':MUTED,'line':LINE,'mist':MIST,'success':'#17664D','warning':'#865500','danger':'#A43135'},
    'typography':{'sans':"'IBM Plex Sans', Arial, Helvetica, sans-serif",'mono':"'IBM Plex Mono', 'Courier New', monospace"},
    'tiles':{'mark_gap':0.16,'mosaic_gap':0.2,'mosaic_turn_degrees':5},
    'spacing':[4,8,12,16,24,32,48,64,80]},indent=2)+'\n')
print(f'Exported {8+len(POSES)} SVG/PNG pairs: identity 03.')
