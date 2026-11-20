"""Small, transparent photo-booth frame themes rendered as PNG on demand."""
from __future__ import annotations

from io import BytesIO
from functools import lru_cache
from math import cos, pi, sin

from PIL import Image, ImageDraw


THEMES = {
    "songkran": {"label": "สงกรานต์", "palette": ((17, 163, 197), (127, 234, 242), (244, 255, 255))},
    "loy-krathong": {"label": "ลอยกระทง", "palette": ((196, 124, 37), (255, 213, 112), (255, 246, 205))},
    "mothers-day": {"label": "วันแม่ · ดอกมะลิ", "palette": ((34, 112, 178), (138, 205, 255), (241, 250, 255))},
    "fathers-day": {"label": "วันพ่อ · โทนเหลือง", "palette": ((174, 118, 30), (255, 211, 92), (255, 247, 202))},
    "graduation": {"label": "รับปริญญา", "palette": ((49, 66, 112), (212, 174, 87), (255, 239, 181))},
    "halloween": {"label": "ฮาโลวีน", "palette": ((152, 46, 26), (255, 111, 35), (255, 222, 151))},
    "new-year": {"label": "คริสต์มาส · ปีใหม่", "palette": ((35, 126, 96), (226, 183, 82), (255, 245, 205))},
    "valentines": {"label": "วาเลนไทน์", "palette": ((175, 45, 78), (255, 129, 155), (255, 226, 232))},
    "birthday": {"label": "วันเกิด · ปาร์ตี้", "palette": ((107, 75, 168), (245, 147, 192), (255, 224, 143))},
}


def _draw_edge(draw: ImageDraw.ImageDraw, theme: str, width: int, height: int) -> None:
    short = min(width, height)
    unit = short / 1200
    primary, accent, light = THEMES[theme]["palette"]
    rgba = lambda color, alpha=255: (*color, alpha)

    # Delicate double rails stay near the edge, leaving most of the canvas clear.
    margin = round(short * .018)
    draw.rounded_rectangle((margin, margin, width - margin, height - margin), radius=round(short * .045), outline=rgba(primary, 220), width=max(3, round(short * .009)))
    inset = round(short * .037)
    draw.rounded_rectangle((inset, inset, width - inset, height - inset), radius=round(short * .04), outline=rgba(accent, 205), width=max(2, round(short * .003)))
    # Fine corner glints and small bead details give the transparent frame a finished edge.
    for x in (round(width * .06), round(width * .94)):
        for y in (round(height * .045), round(height * .955)):
            r = round(short * .024)
            draw.ellipse((x-r, y-r, x+r, y+r), fill=rgba(primary, 230), outline=rgba(light), width=max(2, round(2*unit)))
            draw.ellipse((x-r*.48, y-r*.48, x+r*.48, y+r*.48), fill=rgba(light, 245))
def _flower(draw: ImageDraw.ImageDraw, x: float, y: float, r: float, color, center) -> None:
    for index in range(8):
        angle = index * pi / 4
        px, py = x + cos(angle) * r * .62, y + sin(angle) * r * .62
        pr = r * .43
        draw.ellipse((px-pr, py-pr, px+pr, py+pr), fill=(*color, 225))
    draw.ellipse((x-r*.26, y-r*.26, x+r*.26, y+r*.26), fill=(*center, 255))


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

    # The main ornaments remain in the perimeter band; the center stays transparent.
    if theme in {"songkran", "mothers-day"}:
        for x, y in ((.08,.09),(.92,.09),(.08,.91),(.92,.91)):
            _flower(draw, width*x, height*y, short*.038, light, accent)
        for x in (.07,.93):
            for y in (.28,.50,.72):
                r=short*.012
                draw.ellipse((width*x-r, height*y-r*1.5, width*x+r, height*y+r*1.5), fill=(*accent,170))
                draw.ellipse((width*x-r*.35, height*y-r*.7, width*x+r*.35, height*y+r*.2), fill=(*light,230))
    elif theme == "loy-krathong":
        for x in (.075,.925):
            _lotus(draw,width*x,height*.10,short*.045,accent,light)
            _lotus(draw,width*x,height*.90,short*.045,accent,light)
            for y in (.32,.50,.68):
                r=short*.018
                draw.line((width*x,height*y+r*1.8,width*x,height*y-r),fill=(*light,230),width=max(2,round(3*s)))
                draw.ellipse((width*x-r*.45,height*y-r*1.9,width*x+r*.45,height*y-r*.5),fill=(*accent,240))
        for i in range(7):
            x=width*(.18+i*.107)
            y=height*.955
            draw.arc((x-short*.04,y-short*.025,x+short*.04,y+short*.025),180,360,fill=(*accent,220),width=max(2,round(3*s)))
    elif theme == "valentines":
        for x,y,r in ((.07,.08,.045),(.93,.08,.045),(.07,.92,.045),(.93,.92,.045),(.06,.5,.024),(.94,.5,.024)):
            _heart(draw,width*x,height*y,short*r,accent if y in (.08,.92) else light)
        for x in (.17,.83):
            for y in (.25,.75): _heart(draw,width*x,height*y,short*.014,primary)
    elif theme == "new-year":
        for x,y,r in ((.08,.09,.052),(.92,.09,.052),(.08,.91,.052),(.92,.91,.052),(.5,.045,.038),(.5,.955,.038)):
            _firework(draw,width*x,height*y,short*r,accent,light)
        for x in (.20,.80):
            for y in (.055,.945): _star(draw,width*x,height*y,short*.012,light)
    elif theme == "graduation":
        for x in (.08,.92):
            for y in (.09,.91):
                r=short*.044
                draw.polygon(((width*x-r,height*y),(width*x,height*y-r*.45),(width*x+r,height*y),(width*x,height*y+r*.45)),fill=(*primary,230),outline=(*light,245))
                draw.polygon(((width*x-r*.55,height*y+r*.28),(width*x+r*.55,height*y+r*.28),(width*x+r*.48,height*y+r*.55),(width*x-r*.48,height*y+r*.55)),fill=(*accent,225))
                draw.line((width*x+r*.5,height*y,width*x+r*.72,height*y+r*.58),fill=(*light,240),width=max(2,round(3*s)))
                draw.ellipse((width*x+r*.66,height*y+r*.52,width*x+r*.8,height*y+r*.66),fill=(*accent,245))
    elif theme == "fathers-day":
        for x,y in ((.08,.09),(.92,.09),(.08,.91),(.92,.91)):
            r=short*.04
            _star(draw,width*x,height*y,r,accent)
            draw.ellipse((width*x-r*.36,height*y-r*.36,width*x+r*.36,height*y+r*.36),fill=(*light,245))
            for angle in (-pi/3,0,pi/3):
                dx,dy=cos(angle)*r*1.35,sin(angle)*r*1.35
                draw.line((width*x-dx,height*y-dy,width*x+dx,height*y+dy),fill=(*primary,205),width=max(2,round(2*s)))
    elif theme == "halloween":
        for x,y in ((.075,.10),(.925,.10),(.075,.90),(.925,.90)):
            r=short*.04
            draw.ellipse((width*x-r,height*y-r*.8,width*x+r,height*y+r*.8),fill=(*accent,230),outline=(*light,235),width=max(2,round(2*s)))
            draw.ellipse((width*x-r*.48,height*y-r*.12,width*x-r*.16,height*y+r*.12),fill=(*primary,255))
            draw.ellipse((width*x+r*.16,height*y-r*.12,width*x+r*.48,height*y+r*.12),fill=(*primary,255))
            draw.polygon(((width*x-r*.45,height*y+r*.35),(width*x+r*.45,height*y+r*.35),(width*x,height*y+r*.65)),fill=(*primary,255))
        for i in range(6):
            x=width*(.23+i*.108)
            draw.ellipse((x-short*.006,height*.035,x+short*.006,height*.047),fill=(*light,220))
    else:  # birthday party
        colors=(primary,accent,light)
        for index in range(10):
            x=width*(.12+index*.084)
            for y in (.035,.965):
                color=colors[index%len(colors)]
                rr=short*(.008 if index%2 else .012)
                draw.ellipse((x-rr,y*height-rr,x+rr,y*height+rr),fill=(*color,235))
        for x,y in ((.08,.10),(.92,.10),(.08,.90),(.92,.90)):
            _star(draw,width*x,height*y,short*.036,accent)


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
