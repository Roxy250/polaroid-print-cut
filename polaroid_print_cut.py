"""
Polaroid (Instax-mini) PRINT & CUT sheet generator
--------------------------------------------------
White page, 9 cards per A4 sheet (3 x 3), cards touching so one straight
guillotine cut separates them, faint cut lines running edge to edge.

    python polaroid_print_cut.py                  # reads ./input -> output.pdf
    python polaroid_print_cut.py my_photos out.pdf

Requires: pip install pillow reportlab   (optional: pillow-heif for .heic)
PRINT AT 100% / "Actual size" (not "fit to page") or the cards will be resized.
"""
import re
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

# =====================================================
# SETTINGS
# =====================================================
INPUT_FOLDER = sys.argv[1] if len(sys.argv) > 1 else "input"
OUTPUT_PDF = sys.argv[2] if len(sys.argv) > 2 else "output.pdf"
RECURSIVE = True
EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".tif", ".tiff", ".bmp"}

# A4 portrait (3 x 3 real-size instax cards = 162 x 258 mm fits perfectly)
PAGE_W, PAGE_H = 210 * mm, 297 * mm
COLS, ROWS = 3, 3

# Card size. "fit" = grow the cards to fill the page (keeps Instax proportions),
# or a number: 1.0 = real Instax Mini size (54 x 86 mm), 1.1 = 10% bigger, etc.
CARD_SCALE = "fit"
PAGE_MARGIN_MM = 5                    # blank edge kept for "fit" (most printers need ~3-5 mm)
if CARD_SCALE == "fit":
    CARD_SCALE = min((210 - 2 * PAGE_MARGIN_MM) / (COLS * 54),
                     (297 - 2 * PAGE_MARGIN_MM) / (ROWS * 86))
CARD_MM = (54 * CARD_SCALE, 86 * CARD_SCALE)
WINDOW_MM = (46 * CARD_SCALE, 62 * CARD_SCALE)
TOP_BORDER_MM = 4.5 * CARD_SCALE      # bottom border (the thick chin) = the remainder

# Horizontal (landscape) photos:
#   "rotate" = turn them 90 deg so they fill the portrait card (head tilts sideways)
#   "crop"   = keep upright, centre-crop (loses the left/right sides)
#   "fit"    = keep upright, show the whole photo with white bars above/below
LANDSCAPE_MODE = "rotate"
ROTATE_ANGLE = 90                     # 90 = counter-clockwise, -90 = clockwise

PAPER_COLOR = (255, 255, 255)         # pure white card, saves ink
SHOW_PHOTO_EDGE = True                # hairline around the photo, like a real print

# Cut lines
CUT_STYLE = "plus"                    # "plus" = small + at intersections, "full" = lines across page, "marks" = ticks in margins, "none"
INNER_MARKS = True                    # False = + only around the outer edge (nothing printed between photos)
                                      # True  = + at every intersection (sits in the white card borders)
MARK_ARM = 3 * mm                     # length of each arm of the + (total + size = 2 x this)
CUT_COLOR = (0.40, 0.40, 0.40)        # grey: faint but easy to see (lower = darker)
CUT_WIDTH = 0.6                       # points
CUT_DASH = None                       # None = solid, or e.g. (3, 3) for dashed
MARK_LEN = 6 * mm                     # tick length when CUT_STYLE = "marks"

PX_PER_MM = 12                        # ~300 dpi
JPEG_QUALITY = 92
# =====================================================

CARD_PX = (round(CARD_MM[0] * PX_PER_MM), round(CARD_MM[1] * PX_PER_MM))
WIN_PX = (round(WINDOW_MM[0] * PX_PER_MM), round(WINDOW_MM[1] * PX_PER_MM))
WIN_POS = ((CARD_PX[0] - WIN_PX[0]) // 2, round(TOP_BORDER_MM * PX_PER_MM))

CARD_W, CARD_H = CARD_MM[0] * mm, CARD_MM[1] * mm
GRID_W, GRID_H = COLS * CARD_W, ROWS * CARD_H
if GRID_W > PAGE_W or GRID_H > PAGE_H:
    sys.exit("Cards don't fit on the page: lower CARD_SCALE, COLS or ROWS.")
X0 = (PAGE_W - GRID_W) / 2            # grid is centred on the page
Y0 = (PAGE_H - GRID_H) / 2
PER_PAGE = COLS * ROWS


def natural_key(p: Path):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", p.name)]


def find_images(folder):
    it = Path(folder).rglob("*") if RECURSIVE else Path(folder).iterdir()
    return sorted((p for p in it if p.is_file() and p.suffix.lower() in EXTS), key=natural_key)


def make_card(path: Path) -> Image.Image:
    img = Image.open(path)
    img.draft("RGB", (WIN_PX[0] * 2, WIN_PX[1] * 2))
    img = ImageOps.exif_transpose(img).convert("RGB")

    if img.width > img.height:                     # horizontal photo
        if LANDSCAPE_MODE == "rotate":
            img = img.rotate(ROTATE_ANGLE, expand=True)
            photo = ImageOps.fit(img, WIN_PX, Image.Resampling.LANCZOS, centering=(0.5, 0.4))
        elif LANDSCAPE_MODE == "fit":              # whole photo visible, white bars top/bottom
            photo = Image.new("RGB", WIN_PX, PAPER_COLOR)
            img = ImageOps.contain(img, WIN_PX, Image.Resampling.LANCZOS)
            photo.paste(img, ((WIN_PX[0] - img.width) // 2, (WIN_PX[1] - img.height) // 2))
        else:                                      # "crop": centre crop, sides are lost
            photo = ImageOps.fit(img, WIN_PX, Image.Resampling.LANCZOS, centering=(0.5, 0.4))
    else:
        photo = ImageOps.fit(img, WIN_PX, Image.Resampling.LANCZOS, centering=(0.5, 0.4))

    card = Image.new("RGB", CARD_PX, PAPER_COLOR)
    card.paste(photo, WIN_POS)
    if SHOW_PHOTO_EDGE:
        ImageDraw.Draw(card).rectangle(
            [WIN_POS[0] - 1, WIN_POS[1] - 1, WIN_POS[0] + WIN_PX[0], WIN_POS[1] + WIN_PX[1]],
            outline=(225, 223, 218), width=1)
    return card


def draw_cut_lines(pdf):
    if CUT_STYLE == "none":
        return
    pdf.setStrokeColorRGB(*CUT_COLOR)
    pdf.setLineWidth(CUT_WIDTH)
    pdf.setDash(*CUT_DASH) if CUT_DASH else pdf.setDash()
    xs = [X0 + i * CARD_W for i in range(COLS + 1)]
    ys = [Y0 + j * CARD_H for j in range(ROWS + 1)]
    if CUT_STYLE == "plus":
        for i, x in enumerate(xs):
            for j, y in enumerate(ys):
                on_edge = i in (0, COLS) or j in (0, ROWS)
                if not (on_edge or INNER_MARKS):
                    continue
                pdf.line(x - MARK_ARM, y, x + MARK_ARM, y)
                pdf.line(x, y - MARK_ARM, x, y + MARK_ARM)
    elif CUT_STYLE == "full":
        for x in xs:
            pdf.line(x, 0, x, PAGE_H)
        for y in ys:
            pdf.line(0, y, PAGE_W, y)
    else:  # marks
        for x in xs:
            pdf.line(x, Y0 - MARK_LEN, x, Y0)
            pdf.line(x, Y0 + GRID_H, x, Y0 + GRID_H + MARK_LEN)
        for y in ys:
            pdf.line(X0 - MARK_LEN, y, X0, y)
            pdf.line(X0 + GRID_W, y, X0 + GRID_W + MARK_LEN, y)
    pdf.setDash()


images = find_images(INPUT_FOLDER)
if not images:
    sys.exit(f"No images found in '{INPUT_FOLDER}'.")
pages = -(-len(images) // PER_PAGE)
print(f"Found {len(images)} photos -> {pages} page(s)")

pdf = canvas.Canvas(OUTPUT_PDF, pagesize=(PAGE_W, PAGE_H))

for start in range(0, len(images), PER_PAGE):
    for idx, path in enumerate(images[start:start + PER_PAGE]):
        try:
            card = make_card(path)
        except Exception as e:
            print(f"  skipped {path.name}: {e}")
            continue
        row, col = divmod(idx, COLS)
        x = X0 + col * CARD_W
        y = Y0 + GRID_H - (row + 1) * CARD_H
        buf = BytesIO()
        card.save(buf, "JPEG", quality=JPEG_QUALITY, subsampling=0)
        buf.seek(0)
        pdf.drawImage(ImageReader(buf), x, y, width=CARD_W, height=CARD_H)

    draw_cut_lines(pdf)   # drawn last so the marks stay visible on top
    pdf.showPage()
    print(f"  page {start // PER_PAGE + 1} done")

pdf.save()
print(f"Done! -> {OUTPUT_PDF}")
