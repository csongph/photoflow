"""Small, transparent photo-booth frame themes rendered as PNG on demand."""
from __future__ import annotations

from io import BytesIO
from functools import lru_cache
from math import cos, pi, sin

from PIL import Image, ImageDraw, ImageFont


THEMES = {
    "songkran": {"label": "สงกรานต์", "caption": "SONGKRAN FESTIVAL", "palette": ((17, 163, 197), (127, 234, 242), (244, 255, 255))},
    "loy-krathong": {"label": "ลอยกระทง", "caption": "LOY KRATHONG", "palette": ((196, 124, 37), (255, 213, 112), (255, 246, 205))},
    "mothers-day": {"label": "วันแม่ · ดอกมะลิ", "caption": "MOTHER'S DAY", "palette": ((34, 112, 178), (138, 205, 255), (241, 250, 255))},
    "fathers-day": {"label": "วันพ่อ · โทนเหลือง", "caption": "FATHER'S DAY", "palette": ((174, 118, 30), (255, 211, 92), (255, 247, 202))},
    "graduation": {"label": "รับปริญญา", "caption": "CONGRATULATIONS", "palette": ((49, 66, 112), (212, 174, 87), (255, 239, 181))},
    "halloween": {"label": "ฮาโลวีน", "caption": "HAPPY HALLOWEEN", "palette": ((152, 46, 26), (255, 111, 35), (255, 222, 151))},
    "new-year": {"label": "คริสต์มาส · ปีใหม่", "caption": "MERRY & BRIGHT", "palette": ((35, 126, 96), (226, 183, 82), (255, 245, 205))},
    "valentines": {"label": "วาเลนไทน์", "caption": "LOVE & CELEBRATE", "palette": ((175, 45, 78), (255, 129, 155), (255, 226, 232))},
    "birthday": {"label": "วันเกิด · ปาร์ตี้", "caption": "HAPPY BIRTHDAY", "palette": ((107, 75, 168), (245, 147, 192), (255, 224, 143))},
    "chinese-new-year": {"label": "ตรุษจีน · มงคล", "caption": "LUNAR NEW YEAR", "palette": ((166, 24, 37), (246, 190, 68), (255, 239, 174))},
    "wedding": {"label": "งานแต่ง · หมั้น", "caption": "OUR WEDDING", "palette": ((174, 125, 117), (218, 183, 142), (255, 248, 235))},
}


def _draw_edge(draw: ImageDraw.ImageDraw, theme: str, width: int, height: int) -> None:
    short = min(width, height)
    unit = short / 1200
    primary, accent, light = THEMES[theme]["palette"]
    rgba = lambda color, alpha=255: (*color, alpha)

    # Delicate double rails stay near the edge, leaving most of the canvas clear.
    margin = round(short * .012)
    draw.rounded_rectangle((margin, margin, width - margin, height - margin), radius=round(short * .045), outline=rgba(primary, 110), width=max(10, round(short * .032)))
    inset = round(short * .027)
    draw.rounded_rectangle((inset, inset, width - inset, height - inset), radius=round(short * .04), outline=rgba(accent, 245), width=max(3, round(short * .006)))
    fine = round(short * .041)
    draw.rounded_rectangle((fine, fine, width - fine, height - fine), radius=round(short * .032), outline=rgba(light, 220), width=max(2, round(short * .002)))
    # Fine corner glints and small bead details give the transparent frame a finished edge.
    for x in (round(width * .06), round(width * .94)):
        for y in (round(height * .045), round(height * .955)):
            r = round(short * .034)
            draw.ellipse((x-r*1.25, y-r*1.25, x+r*1.25, y+r*1.25), fill=rgba(primary, 225), outline=rgba(light), width=max(2, round(3*unit)))
            draw.ellipse((x-r*.75, y-r*.75, x+r*.75, y+r*.75), fill=rgba(accent, 245), outline=rgba(light, 230), width=max(2, round(2*unit)))
            draw.ellipse((x-r*.25, y-r*.25, x+r*.25, y+r*.25), fill=rgba(light, 255))
    # Short engraved ticks make the long side rails feel intentional rather than empty.
    for y in (.20,.32,.44,.56,.68,.80):
        for x, direction in ((width*.031,1),(width*.969,-1)):
            draw.line((x,y*height,x+direction*short*.018,y*height), fill=rgba(light,190), width=max(2,round(2*unit)))
def _flower(draw: ImageDraw.ImageDraw, x: float, y: float, r: float, color, center) -> None:
    for index in range(10):
        angle = index * 2 * pi / 10
        px, py = x + cos(angle) * r * .57, y + sin(angle) * r * .57
        pr = r * .40
        draw.ellipse((px-pr+r*.05, py-pr+r*.08, px+pr+r*.05, py+pr+r*.08), fill=(20, 18, 24, 55))
        draw.ellipse((px-pr, py-pr, px+pr, py+pr), fill=(*color, 242), outline=(*center, 160), width=max(1, round(r*.035)))
    draw.ellipse((x-r*.31, y-r*.31, x+r*.31, y+r*.31), fill=(*center, 255), outline=(255,255,255,210), width=max(1, round(r*.045)))
    draw.ellipse((x-r*.12, y-r*.16, x-r*.01, y-r*.05), fill=(255,255,255,235))


def _leaf(draw: ImageDraw.ImageDraw, x: float, y: float, length: float, angle: float, color) -> None:
    dx, dy = cos(angle), sin(angle)
    px, py = -dy, dx
    points = []
    for index in range(13):
        t = index / 12
        width = sin(pi*t) * length * .25
        points.append((x + dx*length*t + px*width, y + dy*length*t + py*width))
    for index in range(12, -1, -1):
        t = index / 12
        width = sin(pi*t) * length * .25
        points.append((x + dx*length*t - px*width, y + dy*length*t - py*width))
    draw.polygon(points, fill=(*color, 232), outline=(255,255,255,75))
    draw.line((x,y,x+dx*length,y+dy*length), fill=(255,255,255,130), width=max(1, round(length*.018)))


def _sprig(draw: ImageDraw.ImageDraw, x: float, y: float, length: float, angle: float, color) -> None:
    dx, dy = cos(angle), sin(angle)
    end = (x+dx*length, y+dy*length)
    draw.line((x,y,*end), fill=(*color,215), width=max(2, round(length*.045)))
    for index in range(1, 7):
        t = index / 7
        bx, by = x+dx*length*t, y+dy*length*t
        side = -1 if index % 2 else 1
        leaf_angle = angle + side * .92
        _leaf(draw, bx, by, length*.28, leaf_angle, color)


def _water_drop(draw: ImageDraw.ImageDraw, x: float, y: float, size: float, color) -> None:
    points = [(x, y-size), (x-size*.5, y-size*.15), (x-size*.48, y+size*.48), (x, y+size*.72), (x+size*.48, y+size*.48), (x+size*.5, y-size*.15)]
    draw.polygon(points, fill=(*color,235), outline=(255,255,255,190))
    draw.ellipse((x-size*.18,y-size*.05,x-size*.02,y+size*.28),fill=(255,255,255,175))


def _lantern(draw: ImageDraw.ImageDraw, x: float, y: float, size: float, palette) -> None:
    primary, accent, light = palette
    w, h = size*.56, size*.78
    draw.arc((x-w*.38,y-h*.72,x+w*.38,y-h*.12),180,360,fill=(*light,230),width=max(2,round(size*.035)))
    draw.rounded_rectangle((x-w/2,y-h/2,x+w/2,y+h/2),radius=size*.14,fill=(*primary,220),outline=(*light,245),width=max(2,round(size*.045)))
    for dx in (-.24,0,.24):
        draw.line((x+dx*w,y-h*.42,x+dx*w,y+h*.42),fill=(*accent,225),width=max(2,round(size*.035)))
    draw.line((x-w*.53,y-h*.24,x+w*.53,y-h*.24),fill=(*light,220),width=max(2,round(size*.035)))
    draw.line((x-w*.53,y+h*.22,x+w*.53,y+h*.22),fill=(*light,220),width=max(2,round(size*.035)))
    draw.line((x,y+h*.5,x,y+h*.95),fill=(*accent,245),width=max(2,round(size*.035)))
    draw.ellipse((x-size*.07,y+h*.88,x+size*.07,y+h*1.02),fill=(*light,245))


def _krathong(draw: ImageDraw.ImageDraw, x: float, y: float, size: float, palette) -> None:
    primary, accent, light = palette
    w, h = size, size*.34
    draw.polygon(((x-w*.55,y),(x-w*.38,y+h*.38),(x,y+h*.68),(x+w*.38,y+h*.38),(x+w*.55,y)), fill=(*primary,245), outline=(*light,245))
    for index in range(7):
        dx = (index-3)*w*.12
        draw.ellipse((x+dx-w*.09,y-h*.04,x+dx+w*.09,y+h*.08),fill=(*accent,245),outline=(*light,210),width=max(1,round(size*.012)))
    draw.line((x,y-h*.04,x,y-h*.55),fill=(*light,250),width=max(2,round(size*.035)))
    draw.ellipse((x-size*.045,y-h*.66,x+size*.045,y-h*.48),fill=(255,236,155,255))
    draw.arc((x-w*.7,y+h*.28,x+w*.7,y+h*.85),0,180,fill=(*light,195),width=max(2,round(size*.03)))


def _rose(draw: ImageDraw.ImageDraw, x: float, y: float, radius: float, palette) -> None:
    primary, accent, light = palette
    draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill=(*primary,245),outline=(*light,240),width=max(2,round(radius*.1)))
    for index in range(6):
        angle = 2*pi*index/6
        px, py = x+cos(angle)*radius*.42, y+sin(angle)*radius*.42
        rr=radius*.43
        draw.ellipse((px-rr,py-rr,px+rr,py+rr),fill=(*accent,235),outline=(*light,185),width=max(1,round(radius*.045)))
    draw.arc((x-radius*.42,y-radius*.35,x+radius*.44,y+radius*.44),25,320,fill=(*light,245),width=max(2,round(radius*.11)))
    draw.ellipse((x-radius*.1,y-radius*.12,x+radius*.1,y+radius*.08),fill=(*primary,255))


def _balloon(draw: ImageDraw.ImageDraw, x: float, y: float, size: float, color) -> None:
    rx, ry = size*.31, size*.4
    draw.ellipse((x-rx,y-ry,x+rx,y+ry),fill=(*color,235),outline=(255,255,255,230),width=max(2,round(size*.035)))
    draw.ellipse((x-rx*.55,y-ry*.66,x-rx*.2,y-ry*.18),fill=(255,255,255,170))
    draw.polygon(((x-size*.07,y+ry*.86),(x+size*.07,y+ry*.86),(x,y+ry*1.08)),fill=(*color,235))
    draw.line((x,y+ry*1.07,x+size*.09,y+size*.84),fill=(255,255,255,205),width=max(1,round(size*.015)))


def _pine(draw: ImageDraw.ImageDraw, x: float, y: float, size: float, color) -> None:
    draw.line((x,y,x+size*.72,y+size*.45),fill=(*color,245),width=max(3,round(size*.08)))
    for index in range(1,6):
        t=index/6
        px,py=x+size*.72*t,y+size*.45*t
        spread=size*(.27-.17*t)
        draw.line((px,py,px-spread,py-spread*.65),fill=(*color,235),width=max(3,round(size*.055)))
        draw.line((px,py,px+spread,py+spread*.65),fill=(*color,235),width=max(3,round(size*.055)))


def _coin(draw: ImageDraw.ImageDraw, x: float, y: float, radius: float, palette) -> None:
    primary, accent, light = palette
    draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill=(*primary,235),outline=(*light,255),width=max(2,round(radius*.13)))
    draw.ellipse((x-radius*.68,y-radius*.68,x+radius*.68,y+radius*.68),outline=(*accent,250),width=max(2,round(radius*.07)))
    hole=radius*.22
    draw.rounded_rectangle((x-hole,y-hole,x+hole,y+hole),radius=hole*.15,fill=(*primary,255),outline=(*light,250),width=max(2,round(radius*.07)))
    for angle in (0,pi/2,pi,3*pi/2):
        px,py=x+cos(angle)*radius*.82,y+sin(angle)*radius*.82
        draw.ellipse((px-radius*.06,py-radius*.06,px+radius*.06,py+radius*.06),fill=(*accent,255))


def _fan(draw: ImageDraw.ImageDraw, x: float, y: float, radius: float, palette) -> None:
    primary, accent, light = palette
    points=[(x,y)]
    for index in range(17):
        angle=pi+pi*index/16
        points.append((x+cos(angle)*radius,y+sin(angle)*radius))
    draw.polygon(points,fill=(*primary,225),outline=(*light,255))
    for index in range(9):
        angle=pi+pi*index/8
        draw.line((x,y,x+cos(angle)*radius,y+sin(angle)*radius),fill=(*accent,225),width=max(2,round(radius*.025)))
    draw.arc((x-radius,y-radius,x+radius,y+radius),180,360,fill=(*light,255),width=max(2,round(radius*.045)))
    draw.ellipse((x-radius*.11,y-radius*.11,x+radius*.11,y+radius*.11),fill=(*light,255))


def _wedding_rings(draw: ImageDraw.ImageDraw, x: float, y: float, radius: float, palette) -> None:
    _, accent, light = palette
    width=max(3,round(radius*.13))
    draw.ellipse((x-radius*1.05,y-radius*.7,x+radius*.35,y+radius*.7),outline=(*light,250),width=width)
    draw.ellipse((x-radius*.35,y-radius*.7,x+radius*1.05,y+radius*.7),outline=(*accent,255),width=width)
    diamond=radius*.23
    draw.polygon(((x,y-radius*.72-diamond),(x+diamond*.75,y-radius*.72),(x,y-radius*.72+diamond),(x-diamond*.75,y-radius*.72)),fill=(*light,255),outline=(*accent,255))


def _cloud_scroll(draw: ImageDraw.ImageDraw, x: float, y: float, size: float, color) -> None:
    """Fine-line ruyi cloud scroll for the lunar new year rails."""
    width=max(2,round(size*.035))
    for direction in (-1,1):
        cx=x+direction*size*.30
        draw.arc((cx-size*.27,y-size*.25,cx+size*.27,y+size*.25),190 if direction<0 else -10,350 if direction<0 else 170,fill=(*color,225),width=width)
        draw.arc((cx-size*.13,y-size*.13,cx+size*.13,y+size*.13),190 if direction<0 else -10,350 if direction<0 else 170,fill=(*color,190),width=width)
    draw.line((x-size*.55,y,x+size*.55,y),fill=(*color,210),width=width)


def _wedding_spray(draw: ImageDraw.ImageDraw, x: float, y: float, size: float, direction: float, palette) -> None:
    """Layered leaves and small blossoms arranged as a corner floral spray."""
    _, accent, light = palette
    dx,dy=cos(direction),sin(direction)
    draw.line((x,y,x+dx*size,y+dy*size),fill=(84,119,87,245),width=max(4,round(size*.035)))
    for index in range(1,8):
        t=index/8
        bx,by=x+dx*size*t,y+dy*size*t
        side=-1 if index%2 else 1
        angle=direction+side*.92
        _leaf(draw,bx,by,size*.29,angle,(91,135,97) if index%2 else (126,157,113))
        if index in (2,5,7):
            _flower(draw,bx+cos(angle)*size*.19,by+sin(angle)*size*.19,size*.047,light,accent)


def _theme_font(size: int):
    for filename in (r"C:\Windows\Fonts\arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(filename, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_title(draw: ImageDraw.ImageDraw, theme: str, width: int, height: int, short: int) -> None:
    _, _, light = THEMES[theme]["palette"]
    caption = THEMES[theme]["caption"]
    font = _theme_font(max(20, round(short*.027)))
    while draw.textbbox((0,0), caption, font=font)[2] > width*.44 and getattr(font,"size",20) > 18:
        font = _theme_font(font.size-2)
    draw.text((width*.5,height*.039),caption,font=font,fill=(*light,255),anchor="mm",stroke_width=max(1,round(short*.0015)),stroke_fill=(22,20,27,150))
    subfont = _theme_font(max(12,round(short*.011)))
    draw.text((width*.5,height*.96),"CS.BXXM STUDIO  ·  PHOTO BOOTH",font=subfont,fill=(*light,245),anchor="mm",stroke_width=1,stroke_fill=(22,20,27,135))


def _heart(draw: ImageDraw.ImageDraw, x: float, y: float, r: float, color) -> None:
    points = []
    for index in range(80):
        t = 2 * pi * index / 80
        px = 16 * sin(t) ** 3 / 32
        py = -(13*cos(t) - 5*cos(2*t) - 2*cos(3*t) - cos(4*t)) / 32
        points.append((x + px * r, y + py * r))
    draw.polygon(points, fill=(*color, 210))


def _star(draw: ImageDraw.ImageDraw, x: float, y: float, r: float, color) -> None:
    points = []
    for index in range(10):
        angle = -pi / 2 + index * pi / 5
        radius = r if index % 2 == 0 else r * .38
        points.append((x + cos(angle) * radius, y + sin(angle) * radius))
    draw.polygon(points, fill=(*color, 230))


def _lotus(draw: ImageDraw.ImageDraw, x: float, y: float, r: float, accent, light) -> None:
    for index in range(5):
        dx = (index - 2) * r * .24
        draw.ellipse((x + dx-r*.15, y-r*.85, x + dx+r*.15, y+r*.22), fill=(*light, 220), outline=(*accent, 240), width=max(1, round(r*.035)))
    draw.ellipse((x-r*.75, y+r*.05, x+r*.75, y+r*.42), fill=(*accent, 220))


def _firework(draw: ImageDraw.ImageDraw, x: float, y: float, r: float, color, light) -> None:
    draw.ellipse((x-r*.09, y-r*.09, x+r*.09, y+r*.09), fill=(*light, 255))
    for index in range(12):
        angle = 2*pi*index/12
        inner, outer = r*.24, r*(.78 if index%2 == 0 else .58)
        draw.line((x+cos(angle)*inner, y+sin(angle)*inner, x+cos(angle)*outer, y+sin(angle)*outer), fill=(*color, 225), width=max(2, round(r*.035)))
        tx, ty = x+cos(angle)*outer, y+sin(angle)*outer
        rr = r*.055
        draw.ellipse((tx-rr, ty-rr, tx+rr, ty+rr), fill=(*light, 230))


def _decorate(image: Image.Image, theme: str) -> None:
    draw = ImageDraw.Draw(image, "RGBA")
    width, height = image.size
    short = min(width, height)
    primary, accent, light = THEMES[theme]["palette"]
    s = short / 1200
    _draw_edge(draw, theme, width, height)
    band_h = short * .055
    for y0, y1 in ((height*.012, height*.012+band_h), (height*.988-band_h, height*.988)):
        draw.rounded_rectangle((width*.18,y0,width*.82,y1),radius=band_h*.36,fill=(*primary,175),outline=(*light,235),width=max(2,round(3*s)))
        draw.line((width*.265,(y0+y1)/2,width*.31,(y0+y1)/2),fill=(*accent,190),width=max(2,round(2*s)))
        draw.line((width*.69,(y0+y1)/2,width*.735,(y0+y1)/2),fill=(*accent,190),width=max(2,round(2*s)))
        for x in (.22,.78):
            _star(draw,width*x,(y0+y1)/2,short*.012,light)
    _draw_title(draw,theme,width,height,short)

    corners = ((.08,.10),(.92,.10),(.08,.90),(.92,.90))
    sides = ((.055,.28),(.945,.28),(.055,.50),(.945,.50),(.055,.72),(.945,.72))
    # Theme-specific illustrations stay on the rails and corners so faces stay clear.
    if theme == "songkran":
        for x,y in corners:
            _flower(draw,width*x,height*y,short*.047,light,accent)
            side = 1 if x < .5 else -1
            _sprig(draw,width*x,height*y+short*.035,short*.10,side*.95,primary)
        for x,y in sides:
            _water_drop(draw,width*x,height*y,short*.025,accent)
    elif theme == "loy-krathong":
        for x,y in ((.08,.10),(.92,.10),(.08,.90),(.92,.90)):
            _lotus(draw,width*x,height*y,short*.048,accent,light)
        for x,y in ((.055,.34),(.945,.34),(.055,.65),(.945,.65)):
            _lantern(draw,width*x,height*y,short*.105,THEMES[theme]["palette"])
        _krathong(draw,width*.34,height*.895,short*.16,THEMES[theme]["palette"])
        _krathong(draw,width*.66,height*.895,short*.16,THEMES[theme]["palette"])
        for x in (.20,.50,.80):
            draw.arc((width*x-short*.07,height*.88,width*x+short*.07,height*.928),180,360,fill=(*light,205),width=max(2,round(3*s)))
    elif theme == "mothers-day":
        for x,y in corners:
            _flower(draw,width*x,height*y,short*.05,(255,255,255),accent)
            side = 1 if x < .5 else -1
            _sprig(draw,width*x,height*y+short*.04,short*.11,side*.8,(55,139,82))
        for x,y in sides:
            _flower(draw,width*x,height*y,short*.022,(245,251,255),accent)
    elif theme == "fathers-day":
        for x,y in corners:
            _star(draw,width*x,height*y,short*.05,accent)
            draw.ellipse((width*x-short*.02,height*y-short*.02,width*x+short*.02,height*y+short*.02),fill=(*light,255),outline=(*primary,245),width=max(2,round(3*s)))
        for x,y in sides:
            r=short*.018
            draw.ellipse((width*x-r,height*y-r,width*x+r,height*y+r),fill=(*accent,225),outline=(*light,245),width=max(2,round(2*s)))
            draw.line((width*x-r*1.8,height*y,width*x+r*1.8,height*y),fill=(*light,230),width=max(2,round(2*s)))
    elif theme == "graduation":
        for x,y in corners:
            r=short*.052
            draw.polygon(((width*x-r,height*y),(width*x,height*y-r*.48),(width*x+r,height*y),(width*x,height*y+r*.48)),fill=(*primary,245),outline=(*light,255))
            draw.polygon(((width*x-r*.58,height*y+r*.28),(width*x+r*.58,height*y+r*.28),(width*x+r*.46,height*y+r*.62),(width*x-r*.46,height*y+r*.62)),fill=(*accent,245),outline=(*light,220))
            draw.line((width*x+r*.45,height*y,width*x+r*.78,height*y+r*.7),fill=(*light,250),width=max(3,round(4*s)))
            draw.ellipse((width*x+r*.72,height*y+r*.62,width*x+r*.88,height*y+r*.78),fill=(*accent,255))
        for x,y in sides:
            _star(draw,width*x,height*y,short*.015,light)
        _sprig(draw,width*.055,height*.23,short*.16,pi/2,accent)
        _sprig(draw,width*.945,height*.77,short*.16,-pi/2,accent)
    elif theme == "new-year":
        for x,y in corners:
            _pine(draw,width*x,height*y,short*.16,primary)
            draw.ellipse((width*x-short*.022,height*y-short*.022,width*x+short*.022,height*y+short*.022),fill=(*accent,255),outline=(*light,245),width=max(2,round(3*s)))
        for x,y in ((.05,.35),(.95,.65)):
            _firework(draw,width*x,height*y,short*.04,accent,light)
        for x in (.26,.74):
            _star(draw,width*x,height*.045,short*.018,light)
            _star(draw,width*x,height*.955,short*.018,light)
    elif theme == "valentines":
        for x,y in corners:
            _rose(draw,width*x,height*y,short*.052,THEMES[theme]["palette"])
            _heart(draw,width*x+short*(.045 if x<.5 else -.045),height*y,short*.025,accent)
        for x,y in sides:
            _heart(draw,width*x,height*y,short*.021,accent if x<.5 else light)
        _sprig(draw,width*.05,height*.32,short*.13,pi/2,(61,129,82))
        _sprig(draw,width*.95,height*.68,short*.13,-pi/2,(61,129,82))
    elif theme == "chinese-new-year":
        palette=THEMES[theme]["palette"]
        # Fan medallions frame the title without covering it; plum branches anchor
        # the lower corners and make the theme read clearly at thumbnail size.
        for x,y,flip in ((.105,.115,1),(.895,.115,-1)):
            _fan(draw,width*x,height*y,short*.072,palette)
            _flower(draw,width*x,height*y,short*.023,light,accent)
            _sprig(draw,width*x,height*y+short*.045,short*.15,pi/2*flip,accent)
        for x,y in ((.052,.31),(.948,.69)):
            _lantern(draw,width*x,height*y,short*.145,palette)
        for x,y in ((.052,.69),(.948,.31)):
            _coin(draw,width*x,height*y,short*.033,palette)
            _cloud_scroll(draw,width*x,height*y+short*.07,short*.07,accent)
        for x,y in ((.10,.87),(.90,.87)):
            _sprig(draw,width*x,height*y,short*.20,-pi/3 if x<.5 else -2*pi/3,(91,133,79))
            _flower(draw,width*x,height*y,short*.027,light,accent)
            for dx,dy in ((.035,-.035),(.055,.005),(-.018,-.055)):
                _flower(draw,width*(x+dx if x<.5 else x-dx),height*(y+dy),short*.014,light,accent)
        for x in (.25,.75):
            _star(draw,width*x,height*.045,short*.015,light)
        _cloud_scroll(draw,width*.065,height*.92,short*.075,accent)
        _cloud_scroll(draw,width*.935,height*.92,short*.075,accent)
    elif theme == "wedding":
        palette=THEMES[theme]["palette"]
        # Airy botanical corner sprays, a fine arch, and a small central ring
        # emblem create a finished invitation-like frame while preserving space.
        draw.arc((width*.035,height*.008,width*.965,height*.32),190,350,fill=(*accent,205),width=max(4,round(short*.004)))
        draw.arc((width*.045,height*.018,width*.955,height*.305),190,350,fill=(*light,225),width=max(2,round(short*.0018)))
        draw.arc((width*.035,height*.68,width*.965,height*.99),10,170,fill=(*accent,185),width=max(4,round(short*.004)))
        for x,y,direction in ((.075,.11,.05),(.925,.11,pi-.05),(.075,.89,-.05),(.925,.89,pi+.05)):
            _wedding_spray(draw,width*x,height*y,short*.21,direction,palette)
            _rose(draw,width*x,height*y,short*.049,palette)
        _wedding_rings(draw,width*.5,height*.105,short*.035,palette)
        for x,y in ((.05,.37),(.95,.63)):
            _wedding_rings(draw,width*x,height*y,short*.052,palette)
        for x in (.25,.75):
            _flower(draw,width*x,height*.035,short*.018,light,accent)
    elif theme == "halloween":
        for x,y in corners:
            r=short*.045
            draw.ellipse((width*x-r,height*y-r*.82,width*x+r,height*y+r*.82),fill=(*accent,245),outline=(*light,255),width=max(2,round(3*s)))
            draw.ellipse((width*x-r*.48,height*y-r*.12,width*x-r*.16,height*y+r*.12),fill=(*primary,255))
            draw.ellipse((width*x+r*.16,height*y-r*.12,width*x+r*.48,height*y+r*.12),fill=(*primary,255))
            draw.polygon(((width*x-r*.45,height*y+r*.35),(width*x+r*.45,height*y+r*.35),(width*x,height*y+r*.65)),fill=(*primary,255))
        for x,y in sides:
            _star(draw,width*x,height*y,short*.014,light)
    else:  # birthday party
        colors=(primary,accent,light)
        for x,y in ((.07,.08),(.16,.13),(.93,.08),(.84,.13),(.07,.92),(.16,.87),(.93,.92),(.84,.87)):
            _balloon(draw,width*x,height*y,short*.085,colors[int(x*100)%len(colors)])
        for x,y in sides:
            _star(draw,width*x,height*y,short*.018,light)
        for index in range(8):
            x=width*(.07 if index%2==0 else .93)
            y=height*(.20+index*.085)
            _star(draw,x,y,short*(.009 if index%2==0 else .012),colors[index%len(colors)])


@lru_cache(maxsize=24)
def make_frame_png(theme: str, orientation: str) -> bytes:
    if theme not in THEMES:
        raise KeyError(theme)
    if orientation not in {"portrait", "landscape"}:
        raise ValueError("invalid frame orientation")
    width, height = (1200, 1800) if orientation == "portrait" else (1800, 1200)
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    _decorate(image, theme)
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()
