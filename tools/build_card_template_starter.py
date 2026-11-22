from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "local" / "frontend" / "assets"
WIDTH, HEIGHT = 600, 1800
EMU_WIDTH, EMU_HEIGHT = 3_657_600, 10_972_800  # 4 x 12 inch, portrait photo strip
INK = "33283F"
CREAM = "F7EBDD"
CORAL = "E98672"
GOLD = "D5B36A"
MUTED = "BCA9A0"


def font(size: int, *, serif: bool = False, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        [r"C:\Windows\Fonts\georgiab.ttf", r"C:\Windows\Fonts\Georgia.ttf"]
        if serif and bold
        else [r"C:\Windows\Fonts\georgia.ttf", r"C:\Windows\Fonts\Georgia.ttf"]
        if serif
        else [r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\Arial.ttf"]
        if bold
        else [r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\Arial.ttf"]
    )
    for candidate in candidates:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def center_text(draw: ImageDraw.ImageDraw, y: int, text: str, face: ImageFont.ImageFont, color: str) -> None:
    draw.text((WIDTH / 2, y), text, font=face, fill=f"#{color}", anchor="mm")


def photo_slots(photo_count: int) -> list[tuple[int, int, int, int]]:
    if photo_count == 4:
        normalized = [(0.12, 0.16 + index * 0.19, 0.76, 0.165) for index in range(4)]
    else:
        height, gap = {2: (0.27, 0.07), 3: (0.205, 0.05)}[photo_count]
        top = (1 - photo_count * height - (photo_count - 1) * gap) / 2
        normalized = [(0.12, top + index * (height + gap), 0.76, height) for index in range(photo_count)]
    return [(round(x * WIDTH), round(y * HEIGHT), round(w * WIDTH), round(h * HEIGHT)) for x, y, w, h in normalized]


def make_png(path: Path, photo_count: int = 4) -> None:
    image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((14, 14, 586, 1786), radius=34, outline=f"#{CREAM}", width=4)
    draw.rounded_rectangle((23, 23, 577, 1777), radius=29, outline=f"#{GOLD}", width=2)
    center_text(draw, 67, "YOUR STORY  ·  FESTIVAL EDITION", font(17, bold=True), GOLD)
    center_text(draw, 137, "FESTIVAL", font(64, serif=True, bold=True), CREAM)
    center_text(draw, 204, "PHOTO STRIP", font(25, bold=True), CORAL)
    draw.line((225, 248, 375, 248), fill=f"#{GOLD}", width=3)
    draw.ellipse((291, 241, 309, 259), fill=f"#{CORAL}")

    slots = photo_slots(photo_count)
    for index, (left, top, width, height) in enumerate(slots, 1):
        right, bottom = left + width, top + height
        draw.rounded_rectangle((left, top, right, bottom), radius=14, outline=f"#{CREAM}", width=5)
        draw.rounded_rectangle((left + 8, top + 8, right - 8, bottom - 8), radius=10, outline=f"#{GOLD}", width=2)
        cy = top + height // 2
        draw.ellipse((32, cy - 19, 70, cy + 19), fill=f"#{CORAL}")
        draw.text((51, cy), f"{index:02d}", font=font(15, bold=True), fill=f"#{INK}", anchor="mm")
        # Small registration marks sit outside the photo apertures and remain editable.
        for x, direction in ((left + 21, 1), (right - 21, -1)):
            draw.line((x, top + 24, x + direction * 24, top + 24), fill=f"#{GOLD}", width=3)
            draw.line((x, top + 24, x, top + 48), fill=f"#{GOLD}", width=3)

    for first, second in zip(slots, slots[1:]):
        cy = round((first[1] + first[3] + second[1]) / 2)
        draw.regular_polygon((300, cy, 10), n_sides=4, rotation=45, fill=f"#{GOLD}")
        draw.line((270, cy, 284, cy), fill=f"#{CORAL}", width=2)
        draw.line((316, cy, 330, cy), fill=f"#{CORAL}", width=2)

    draw.line((198, 1651, 402, 1651), fill=f"#{GOLD}", width=2)
    center_text(draw, 1688, "KEEP THIS LITTLE MOMENT", font(22, serif=True, bold=True), CREAM)
    center_text(draw, 1731, "CS.BXXM STUDIO   ·   2026", font(15, bold=True), CORAL)
    image.save(path, format="PNG", optimize=True)


def shape_xml(shape_id: int, name: str, kind: str, x: int, y: int, w: int, h: int, color: str, *, fill: bool = False, line_width: int = 18000, text: str = "", size: int = 1600, bold: bool = False, serif: bool = False) -> str:
    x1, y1 = round(x / WIDTH * EMU_WIDTH), round(y / HEIGHT * EMU_HEIGHT)
    cx, cy = round(w / WIDTH * EMU_WIDTH), round(h / HEIGHT * EMU_HEIGHT)
    geometry = {"rect": "rect", "round": "roundRect", "ellipse": "ellipse", "diamond": "diamond"}[kind]
    fill_xml = f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>' if fill else "<a:noFill/>"
    line_xml = "<a:ln><a:noFill/></a:ln>" if fill and line_width == 0 else f'<a:ln w="{line_width}"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill></a:ln>'
    text_xml = ""
    if text:
        face = "Georgia" if serif else "Arial"
        bold_xml = ' b="1"' if bold else ""
        text_xml = f'''<p:txBody><a:bodyPr wrap="square" anchor="ctr"/><a:lstStyle/><a:p><a:pPr algn="ctr"/><a:r><a:rPr lang="en-US" sz="{size}"{bold_xml}><a:solidFill><a:srgbClr val="{color}"/></a:solidFill><a:latin typeface="{face}"/><a:ea typeface="{face}"/></a:rPr><a:t>{escape(text)}</a:t></a:r><a:endParaRPr lang="en-US" sz="{size}"/></a:p></p:txBody>'''
    return f'''<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="{escape(name)}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{x1}" y="{y1}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="{geometry}"><a:avLst/></a:prstGeom>{fill_xml}{line_xml}</p:spPr>{text_xml}</p:sp>'''


def make_pptx(path: Path, photo_count: int = 4) -> None:
    shapes: list[str] = []
    sid = 2

    def add(name: str, kind: str, x: int, y: int, w: int, h: int, color: str, **kwargs) -> None:
        nonlocal sid
        shapes.append(shape_xml(sid, name, kind, x, y, w, h, color, **kwargs))
        sid += 1

    add("Outer rounded frame", "round", 14, 14, 572, 1772, CREAM, line_width=24000)
    add("Inner rounded accent", "round", 23, 23, 554, 1754, GOLD, line_width=12000)
    add("Edition label", "rect", 70, 42, 460, 48, GOLD, text="YOUR STORY  ·  FESTIVAL EDITION", size=1000, bold=True, line_width=0)
    add("Editable title", "rect", 80, 91, 440, 92, CREAM, text="FESTIVAL", size=3200, bold=True, serif=True, line_width=0)
    add("Editable subtitle", "rect", 100, 177, 400, 48, CORAL, text="PHOTO STRIP", size=1350, bold=True, line_width=0)
    add("Header rule", "rect", 225, 243, 150, 6, GOLD, fill=True, line_width=0)
    add("Header jewel", "diamond", 291, 238, 18, 18, CORAL, fill=True, line_width=0)

    slots = photo_slots(photo_count)
    for index, (left, top, width, height) in enumerate(slots, 1):
        add(f"Photo slot {index} transparent guide", "round", left, top, width, height, CREAM, line_width=30000)
        add(f"Photo slot {index} inner guide", "round", left + 8, top + 8, width - 16, height - 16, GOLD, line_width=12000)
        cy = top + height // 2
        add(f"Photo slot number {index}", "ellipse", 32, cy - 19, 38, 38, CORAL, fill=True, line_width=0)
        add(f"Photo slot number text {index}", "rect", 32, cy - 18, 38, 36, INK, text=f"{index:02d}", size=750, bold=True, line_width=0)
        add(f"Slot {index} upper-left registration", "rect", left + 21, top + 24, 24, 4, GOLD, fill=True, line_width=0)
        add(f"Slot {index} upper-left registration vertical", "rect", left + 21, top + 24, 4, 24, GOLD, fill=True, line_width=0)
        add(f"Slot {index} upper-right registration", "rect", left + width - 45, top + 24, 24, 4, GOLD, fill=True, line_width=0)
        add(f"Slot {index} upper-right registration vertical", "rect", left + width - 25, top + 24, 4, 24, GOLD, fill=True, line_width=0)

    for gap_index, (first, second) in enumerate(zip(slots, slots[1:]), 1):
        cy = round((first[1] + first[3] + second[1]) / 2)
        add(f"Divider jewel {gap_index}", "diamond", 291, cy - 9, 18, 18, GOLD, fill=True, line_width=0)
        add(f"Divider left accent {gap_index}", "rect", 270, cy, 14, 3, CORAL, fill=True, line_width=0)
        add(f"Divider right accent {gap_index}", "rect", 316, cy, 14, 3, CORAL, fill=True, line_width=0)

    add("Footer rule", "rect", 198, 1648, 204, 4, GOLD, fill=True, line_width=0)
    add("Editable footer message", "rect", 60, 1660, 480, 62, CREAM, text="KEEP THIS LITTLE MOMENT", size=1100, bold=True, serif=True, line_width=0)
    add("Editable studio credit", "rect", 80, 1711, 440, 42, CORAL, text="CS.BXXM STUDIO   ·   2026", size=750, bold=True, line_width=0)

    slide = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>{''.join(shapes)}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'''
    presentation = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst><p:sldIdLst><p:sldId id="256" r:id="rId2"/></p:sldIdLst><p:sldSz cx="{EMU_WIDTH}" cy="{EMU_HEIGHT}" type="custom"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>'''
    master = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld><p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/><p:sldLayoutIdLst><p:sldLayoutId id="1" r:id="rId1"/></p:sldLayoutIdLst><p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles></p:sldMaster>'''
    layout = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1"><p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>'''
    theme = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Festival Card"><a:themeElements><a:clrScheme name="Festival"><a:dk1><a:srgbClr val="33283F"/></a:dk1><a:lt1><a:srgbClr val="F7EBDD"/></a:lt1><a:dk2><a:srgbClr val="33283F"/></a:dk2><a:lt2><a:srgbClr val="F7EBDD"/></a:lt2><a:accent1><a:srgbClr val="E98672"/></a:accent1><a:accent2><a:srgbClr val="D5B36A"/></a:accent2><a:accent3><a:srgbClr val="BCA9A0"/></a:accent3><a:accent4><a:srgbClr val="70846A"/></a:accent4><a:accent5><a:srgbClr val="78658A"/></a:accent5><a:accent6><a:srgbClr val="FFFFFF"/></a:accent6><a:hlink><a:srgbClr val="0563C1"/></a:hlink><a:folHlink><a:srgbClr val="954F72"/></a:folHlink></a:clrScheme><a:fontScheme name="Festival"><a:majorFont><a:latin typeface="Georgia"/><a:ea typeface="Georgia"/><a:cs typeface="Georgia"/></a:majorFont><a:minorFont><a:latin typeface="Arial"/><a:ea typeface="Arial"/><a:cs typeface="Arial"/></a:minorFont></a:fontScheme><a:fmtScheme name="Festival"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="lt1"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme></a:themeElements></a:theme>'''
    parts = {
        "[Content_Types].xml": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/><Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/><Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/><Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/><Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/></Types>''',
        "_rels/.rels": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/></Relationships>''',
        "ppt/presentation.xml": presentation,
        "ppt/_rels/presentation.xml.rels": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/></Relationships>''',
        "ppt/slides/slide1.xml": slide,
        "ppt/slides/_rels/slide1.xml.rels": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/></Relationships>''',
        "ppt/slideMasters/slideMaster1.xml": master,
        "ppt/slideMasters/_rels/slideMaster1.xml.rels": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/></Relationships>''',
        "ppt/slideLayouts/slideLayout1.xml": layout,
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/></Relationships>''',
        "ppt/theme/theme1.xml": theme,
    }
    with ZipFile(path, "w", ZIP_DEFLATED) as package:
        for member, content in parts.items():
            package.writestr(member, content)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    make_png(OUT / "card-template-starter.png")
    make_pptx(OUT / "card-template-starter.pptx")
    for count in (2, 3, 4):
        make_png(OUT / f"photo-strip-festival-{count}.png", count)
        make_pptx(OUT / f"photo-strip-festival-{count}-canva.pptx", count)
    print(f"Created editable PPTX and transparent PNG under {OUT}")


if __name__ == "__main__":
    main()
