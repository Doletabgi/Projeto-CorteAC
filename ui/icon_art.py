"""Ícones desenhados em uma grade de 24 unidades, sem fontes ou rede.

Uma única geometria produz os PNGs distribuídos e os tamanhos usados pelo Tk.
Os traços são renderizados em 4x para manter legibilidade em telas HiDPI.
"""

from PIL import Image, ImageDraw

BLUE = "#2563eb"
TEAL = "#0f766e"
SLATE = "#334155"
RED = "#c24146"
AMBER = "#b45309"
PALE = "#eff6ff"
WHITE = "#ffffff"

ICON_NAMES = (
    "new", "open", "folder", "save", "save_all", "cut", "copy", "paste",
    "details", "layout", "shape", "materials", "production", "order",
    "session", "catalog", "print", "export", "import", "dual", "palette",
    "zoom", "zoom_in", "zoom_out", "fit", "move", "add", "remove", "grid",
    "left", "right", "up", "down", "play", "stop", "delete", "edit",
    "refresh", "undo", "settings", "auto", "user", "backup", "clock",
    "clean", "barcode", "check", "uncheck", "close", "minimize",
    "maximize", "restore", "fullscreen", "select", "hole", "lock",
    "unlock", "eye", "mirror_x", "mirror_y", "target", "info", "warning",
    "image", "company", "sort", "number", "ruler", "tip", "app",
)


def render_icon(name, size=24):
    """Retorna RGBA transparente; erro explícito evita ícones trocados."""
    if name not in ICON_NAMES:
        raise KeyError(name)
    scale = size * 4 / 24
    image = Image.new("RGBA", (size * 4, size * 4))
    d = ImageDraw.Draw(image)

    def pts(values):
        return [tuple(v * scale for v in pair) for pair in values]

    def line(values, color=SLATE, width=1.8):
        points = pts(values)
        w = max(1, round(width * scale))
        d.line(points, fill=color, width=w, joint="curve")
        r = w / 2
        for x, y in (points[0], points[-1]):
            d.ellipse((x-r, y-r, x+r, y+r), fill=color)

    def rect(box, color=BLUE, fill=None, radius=1.6, width=1.7):
        d.rounded_rectangle(tuple(v * scale for v in box), radius=radius*scale,
                            fill=fill, outline=color, width=max(1, round(width*scale)))

    def circle(box, color=BLUE, fill=None, width=1.8):
        d.ellipse(tuple(v * scale for v in box), fill=fill, outline=color,
                  width=max(1, round(width*scale)))

    def polygon(values, color=BLUE, fill=PALE):
        d.polygon(pts(values), fill=fill)
        line(values + [values[0]], color)

    def arrow(direction, color=BLUE):
        paths = {
            "right": [(5,12),(19,12)], "left": [(19,12),(5,12)],
            "up": [(12,19),(12,5)], "down": [(12,5),(12,19)],
        }
        heads = {
            "right": [(14,7),(19,12),(14,17)], "left": [(10,7),(5,12),(10,17)],
            "up": [(7,10),(12,5),(17,10)], "down": [(7,14),(12,19),(17,14)],
        }
        line(paths[direction], color); line(heads[direction], color)

    if name in ("new", "details", "session", "order", "copy", "paste", "save_all"):
        if name in ("copy", "save_all"):
            rect((3,3,16,17), SLATE, WHITE)
        if name == "paste":
            rect((4,5,20,21), SLATE, PALE)
            rect((8,2,16,7), BLUE, WHITE)
        else:
            rect((7 if name in ("copy", "save_all") else 5, 6 if name in ("copy", "save_all") else 3, 20,21), BLUE, PALE)
        if name == "new":
            line([(9,12),(16,12)],BLUE); line([(12.5,8.5),(12.5,15.5)],BLUE)
        else:
            for y in (10,14,18):
                line([(10,y),(16,y)],TEAL if name == "session" else BLUE,1.4)
    elif name in ("folder", "open"):
        polygon([(3,7),(3,5),(10,5),(12,7),(21,7),(21,20),(3,20)], AMBER, "#fff7df")
        if name == "open":
            polygon([(3,11),(22,11),(19,20),(3,20)],AMBER,"#fef3c7")
    elif name == "save":
        polygon([(4,3),(17,3),(21,7),(21,21),(3,21),(3,3)],BLUE,PALE)
        rect((7,3,15,10),BLUE,WHITE,.5)
        rect((7,14,17,21),BLUE,WHITE,.5)
    elif name == "cut":
        circle((3,14,9,20),BLUE); circle((15,14,21,20),BLUE)
        line([(7,15),(19,3)]); line([(17,15),(5,3)])
        circle((10.5,10.5,13.5,13.5),SLATE,WHITE,1)
    elif name in ("layout", "app"):
        if name == "app":
            rect((1,1,23,23), BLUE, BLUE,5)
        rect((4,4,20,20), WHITE if name == "app" else SLATE, WHITE,2)
        polygon([(7,7),(13,7),(11,12),(7,11)],BLUE,"#dbeafe")
        polygon([(15,7),(18,7),(18,15),(13,14)],TEAL,"#ccfbf1")
        polygon([(7,14),(10,15),(12,18),(7,18)],AMBER,"#fef3c7")
        line([(15,18),(18,18)],BLUE)
    elif name in ("shape", "select"):
        if name == "select":
            polygon([(5,3),(19,13),(12,14),(9,21)],BLUE,PALE)
        else:
            polygon([(4,17),(6,9),(12,4),(19,7),(21,15),(15,19)],TEAL,"#ccfbf1")
            for x,y in ((6,9),(12,4),(21,15)):
                rect((x-1.3,y-1.3,x+1.3,y+1.3),TEAL,WHITE,.2,1)
    elif name == "materials":
        for y in (15,10,5):
            polygon([(3,y+2),(12,y-2),(21,y+2),(12,y+6)],TEAL,"#ccfbf1")
    elif name == "production":
        rect((3,3,21,16),SLATE,PALE,2)
        line([(9,20),(15,20)]); line([(12,16),(12,20)])
        for x,h in ((7,3),(11,6),(15,8)):
            rect((x,13-h,x+2,13),BLUE,BLUE,.4,1)
    elif name in ("catalog", "grid"):
        for x in (4,13):
            for y in (4,13):
                rect((x,y,x+7,y+7),TEAL if x==13 and y==4 else BLUE,PALE,1)
    elif name == "print":
        rect((6,3,18,10),SLATE,WHITE,1)
        rect((3,8,21,18),BLUE,PALE,2)
        rect((6,14,18,21),SLATE,WHITE,1)
        circle((17,10,19,12),TEAL,TEAL,1)
        line([(9,17),(15,17)],BLUE,1.2)
    elif name in ("export", "import"):
        line([(4,13),(4,20),(20,20),(20,13)],TEAL)
        if name == "export":
            line([(12,15),(12,3)],BLUE); line([(7,8),(12,3),(17,8)],BLUE)
        else:
            line([(12,3),(12,15)],BLUE); line([(7,10),(12,15),(17,10)],BLUE)
    elif name == "dual":
        line([(12,20),(12,12),(5,12),(5,4)],TEAL)
        line([(12,12),(19,12),(19,4)],BLUE)
        line([(2,7),(5,4),(8,7)],TEAL); line([(16,7),(19,4),(22,7)],BLUE)
    elif name == "palette":
        circle((3,3,21,21),SLATE,WHITE)
        for box,c in (((6,6,10,10),BLUE),((13,6,17,10),TEAL),((6,13,10,17),AMBER)):
            circle(box,c,c,1)
        circle((14,14,19,19),SLATE,PALE)
    elif name in ("zoom", "zoom_in", "zoom_out"):
        circle((3,3,16,16),BLUE,PALE)
        line([(15,15),(21,21)],SLATE,2.4)
        if name != "zoom":
            line([(6,9.5),(13,9.5)],BLUE,1.6)
        if name == "zoom_in":
            line([(9.5,6),(9.5,13)],BLUE,1.6)
    elif name in ("fit", "fullscreen", "target"):
        for values in ([(3,9),(3,3),(9,3)],[(15,3),(21,3),(21,9)],[(21,15),(21,21),(15,21)],[(9,21),(3,21),(3,15)]):
            line(values,BLUE)
        if name == "target":
            circle((8,8,16,16),TEAL); line([(12,6),(12,18)],TEAL,1.2); line([(6,12),(18,12)],TEAL,1.2)
        elif name == "fit":
            rect((8,8,16,16),TEAL,"#ccfbf1",1)
    elif name in ("left", "right", "up", "down"):
        arrow(name)
    elif name == "move":
        line([(3,12),(21,12)],BLUE); line([(12,3),(12,21)],BLUE)
        for values in ([(6,9),(3,12),(6,15)],[(18,9),(21,12),(18,15)],[(9,6),(12,3),(15,6)],[(9,18),(12,21),(15,18)]):
            line(values,BLUE,1.5)
    elif name in ("add", "remove"):
        line([(5,12),(19,12)],TEAL,2.2)
        if name == "add": line([(12,5),(12,19)],TEAL,2.2)
    elif name == "play":
        polygon([(7,4),(20,12),(7,20)],TEAL,"#ccfbf1")
    elif name == "stop":
        rect((5,5,19,19),RED,"#fee2e2",2)
    elif name in ("delete", "clean"):
        if name == "delete":
            line([(7,7),(8,21),(17,21),(18,7)],RED)
            line([(4,6),(21,6)],RED); line([(9,3),(16,3)],RED)
            line([(11,10),(11,17)],RED,1.3); line([(15,10),(15,17)],RED,1.3)
        else:
            line([(11,13),(20,3)],TEAL,2.5)
            polygon([(9,11),(15,16),(10,21),(3,18)],TEAL,"#ccfbf1")
            line([(6,17),(9,14)],TEAL,1.2)
    elif name == "edit":
        polygon([(4,16),(16,4),(20,8),(8,20),(3,21)],BLUE,PALE)
        line([(13,7),(17,11)],BLUE)
    elif name in ("refresh", "undo"):
        d.arc(tuple(v*scale for v in (4,4,20,20)),35,305,fill=BLUE,width=max(1,round(1.8*scale)))
        line([(3,3),(3,10),(10,10)],BLUE)
        if name == "undo": line([(9,15),(14,15),(14,18)],TEAL)
    elif name == "settings":
        circle((6,6,18,18),SLATE,PALE)
        for a in range(0,360,45):
            import math
            c,s=math.cos(math.radians(a)),math.sin(math.radians(a))
            line([(12+7*c,12+7*s),(12+9*c,12+9*s)],SLATE,2.6)
        circle((9,9,15,15),BLUE,WHITE)
    elif name == "auto":
        polygon([(13,2),(5,13),(11,13),(10,22),(20,9),(13,9)],AMBER,"#fef3c7")
    elif name == "user":
        circle((8,3,16,11),BLUE,PALE)
        d.arc(tuple(v*scale for v in (4,13,20,27)),180,360,fill=BLUE,width=max(1,round(1.8*scale)))
        line([(4,21),(20,21)],BLUE)
    elif name == "backup":
        polygon([(3,7),(12,3),(21,7),(21,18),(12,22),(3,18)],TEAL,"#ccfbf1")
        line([(3,7),(12,11),(21,7)],TEAL); line([(12,11),(12,22)],TEAL)
        line([(8,5),(17,9)],TEAL)
    elif name == "clock":
        circle((3,3,21,21),BLUE,PALE)
        line([(12,6),(12,12),(16,14)],BLUE)
    elif name == "barcode":
        for x,w in ((4,1),(7,2),(11,1),(14,3),(20,1)):
            rect((x,5,x+w,19),SLATE,SLATE,0,1)
    elif name in ("check", "uncheck"):
        rect((3,3,21,21),TEAL if name=="check" else SLATE,"#f0fdfa" if name=="check" else WHITE,3)
        if name == "check": line([(7,12),(10,15),(17,8)],TEAL,2)
    elif name == "close":
        line([(6,6),(18,18)],RED); line([(6,18),(18,6)],RED)
    elif name == "minimize":
        line([(5,17),(19,17)],SLATE)
    elif name in ("maximize", "restore"):
        if name=="restore": rect((8,3,21,16),SLATE,PALE,1)
        rect((3,8 if name=="restore" else 4,17 if name=="restore" else 21,21),SLATE,WHITE,1)
    elif name == "hole":
        circle((4,4,20,20),TEAL,"#ccfbf1"); circle((9,9,15,15),TEAL,WHITE)
    elif name in ("lock", "unlock"):
        d.arc(tuple(v*scale for v in (7,3,17,17)),180,360 if name=="lock" else 300,fill=SLATE,width=max(1,round(1.8*scale)))
        rect((5,10,19,21),BLUE,PALE,2); line([(12,14),(12,17)],BLUE)
    elif name == "eye":
        polygon([(2,12),(7,6),(12,4),(17,6),(22,12),(17,18),(12,20),(7,18)],SLATE,WHITE)
        circle((8,8,16,16),BLUE,PALE)
    elif name in ("mirror_x", "mirror_y"):
        if name=="mirror_x":
            line([(12,3),(12,21)],SLATE,1.2)
            polygon([(3,18),(8,6),(8,18)],BLUE,PALE); polygon([(21,18),(16,6),(16,18)],TEAL,"#ccfbf1")
        else:
            line([(3,12),(21,12)],SLATE,1.2)
            polygon([(6,3),(18,8),(6,8)],BLUE,PALE); polygon([(6,21),(18,16),(6,16)],TEAL,"#ccfbf1")
    elif name in ("info", "warning", "tip"):
        color=AMBER if name in ("warning","tip") else BLUE
        if name=="warning": polygon([(12,3),(22,21),(2,21)],color,"#fffbeb")
        else: circle((3,3,21,21),color,PALE if name=="info" else "#fffbeb")
        line([(12,10),(12,15)],color,2)
        circle((11,6 if name=="info" else 17,13,8 if name=="info" else 19),color,color,1)
    elif name == "image":
        rect((3,4,21,20),BLUE,PALE,2); circle((6,7,10,11),AMBER,AMBER,1)
        line([(4,18),(10,12),(14,16),(17,12),(20,16)],TEAL)
    elif name == "company":
        rect((5,3,19,21),SLATE,PALE,1)
        for x in (8,14):
            for y in (6,11): rect((x,y,x+2,y+2),BLUE,BLUE,.2,1)
        rect((10,17,14,21),BLUE,WHITE,.3,1)
    elif name == "sort":
        for y,x in ((5,13),(10,10),(15,7)): line([(3,y),(x,y)],SLATE)
        line([(18,3),(18,20)],BLUE); line([(14,16),(18,20),(22,16)],BLUE)
    elif name == "number":
        line([(9,3),(6,21)],BLUE); line([(17,3),(14,21)],BLUE)
        line([(4,9),(21,9)],BLUE); line([(3,15),(20,15)],BLUE)
    elif name == "ruler":
        rect((3,6,21,18),TEAL,"#ccfbf1",1)
        for x in (7,11,15,19): line([(x,7),(x,11 if x%2 else 13)],TEAL,1.2)
    return image.resize((size,size),Image.Resampling.LANCZOS)
