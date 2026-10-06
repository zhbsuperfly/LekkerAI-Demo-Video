"""Build the photoreal asset layer from ./assets into ./assets/build.

- room-before.png is the locked master. Every design image = master pixels everywhere,
  with ONLY the wall region taken from the supplied variant (through a rebuilt wall mask),
  so furniture / floor / rug / lamp never drift between designs.
- wall-mask.png is rebuilt (supplied one covers the plant, sofa and vase branches and misses wall edges).
- plant.png is cut from the master (supplied room-foreground.png is a different composition).
"""
import json, cv2, numpy as np
from scipy import ndimage as nd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
A, OUT = ROOT / "assets", ROOT / "assets" / "build"
OUT.mkdir(exist_ok=True)
OW, OH = 2560, 1440                         # output plate size (headroom for 1.14x camera push)
rd = lambda n: cv2.imread(str(A / n)).astype(np.float32)
B = rd("room-before.png"); H, W = B.shape[:2]
L = B.mean(-1)
DESIGNS = ["botanical", "stripe", "arch", "grid", "chalk", "moss-trail"]
V = {d: rd(f"room-{d}.png") for d in DESIGNS}

# ---------- 1. wall mask ----------
def change(Vi):
    col = np.abs(cv2.blur(Vi, (7, 7)) - cv2.blur(B, (7, 7))).max(-1)
    a, b = L, Vi.mean(-1)
    ma, mb = cv2.blur(a, (7, 7)), cv2.blur(b, (7, 7))
    va = cv2.blur(a*a, (7, 7)) - ma*ma; vb = cv2.blur(b*b, (7, 7)) - mb*mb
    c = (cv2.blur(a*b, (7, 7)) - ma*mb) / np.sqrt(np.maximum(va, 1) * np.maximum(vb, 1))
    return np.maximum(col, np.clip((1 - c) * np.sqrt(np.maximum(va, vb)) / 4, 0, 60))

med = np.median(np.stack([change(V[d]) for d in ["botanical", "stripe", "arch", "grid", "moss-trail"]]), 0)
Lg = cv2.GaussianBlur(L, (0, 0), 1)
g = np.hypot(cv2.Sobel(Lg, cv2.CV_32F, 1, 0), cv2.Sobel(Lg, cv2.CV_32F, 0, 1))
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32); yn, xn = yy / H, xx / W
feats = lambda y, x: np.stack([np.ones_like(x), x, y, x*x, y*y, x*y, x**3, y**3, x*x*y, x*y*y], -1)
sure = (cv2.blur(med, (15, 15)) > 30) & (g < 48)
Mfit = np.linalg.lstsq(feats(yn[sure], xn[sure]), B[sure], rcond=None)[0]
err = np.abs(B - feats(yn, xn) @ Mfit).max(-1)        # deviation from smooth painted-wall model

gc = np.full((H, W), cv2.GC_PR_BGD, np.uint8)
gc[med > 18] = cv2.GC_PR_FGD
gc[med < 6] = cv2.GC_BGD
gc[(err < 10) & (med > 12)] = cv2.GC_FGD
gc[int(H*0.80):, :] = cv2.GC_BGD
cv2.grabCut(B.astype(np.uint8), gc, None, np.zeros((1, 65)), np.zeros((1, 65)), 6, cv2.GC_INIT_WITH_MASK)
w = (gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)
lab, n = nd.label(w); s = nd.sum(w, lab, range(1, n+1)); w = np.isin(lab, np.where(s > 2500)[0] + 1)
def fill_small(m, area):
    h = nd.binary_fill_holes(m) & ~m; hl, hn = nd.label(h)
    return m | np.isin(hl, np.where(nd.sum(h, hl, range(1, hn+1)) < area)[0] + 1)
w = nd.binary_opening(fill_small(w, 250), iterations=1)
cand = nd.binary_opening((err < 13) & (cv2.blur(g, (5, 5)) < 10) & (yy < H*0.74), iterations=1)
lab, _ = nd.label(cand | w); keep = np.unique(lab[w]); keep = keep[keep > 0]
wall = fill_small(np.isin(lab, keep) & (cand | w), 120)

# ---------- 2. foreground plant (bottom-right) ----------
b_, g_, r_ = B[..., 0], B[..., 1], B[..., 2]
leaf = (g_ >= r_ - 12) & (b_ < g_ - 12) & (L < 170)
roi = np.zeros((H, W), bool); roi[470:, 1150:] = True
lab, _ = nd.label(leaf); cc = np.unique(lab[880:, 1500:]); cc = cc[cc > 0]
seed = np.isin(lab, cc) & roi
gp = np.full((H, W), cv2.GC_BGD, np.uint8); gp[roi] = cv2.GC_PR_BGD
gp[nd.binary_dilation(seed, iterations=6) & roi] = cv2.GC_PR_FGD
gp[nd.binary_erosion(seed, iterations=2)] = cv2.GC_FGD
gp[wall & roi] = cv2.GC_BGD
cv2.grabCut(B.astype(np.uint8), gp, None, np.zeros((1, 65)), np.zeros((1, 65)), 6, cv2.GC_INIT_WITH_MASK)
plant = (gp == 1) | (gp == 3)
lab, n = nd.label(plant); s = nd.sum(plant, lab, range(1, n+1))
plant = nd.binary_fill_holes(np.isin(lab, np.where(s > 400)[0] + 1))
wall &= ~plant

# ---------- 3. write plates ----------
up = lambda img, interp=cv2.INTER_LANCZOS4: cv2.resize(img, (OW, OH), interpolation=interp)
def sharpen(img):
    bl = cv2.GaussianBlur(img, (0, 0), 1.2); return np.clip(img * 1.35 - bl * 0.35, 0, 255)
soft = cv2.GaussianBlur(cv2.erode(wall.astype(np.float32), np.ones((3, 3))), (0, 0), 0.9)[..., None]
jpg = lambda p, img: cv2.imwrite(str(OUT / p), img.astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 93])
jpg("room-before.jpg", sharpen(up(B)))
comps = {}
for d in DESIGNS:
    comps[d] = B * (1 - soft) + V[d] * soft          # master everywhere except the wall
    jpg(f"room-{d}.jpg", sharpen(up(comps[d])))
mask8 = (up(soft[..., 0], cv2.INTER_LINEAR) * 255).clip(0, 255).astype(np.uint8)
cv2.imwrite(str(OUT / "wall-mask.png"), mask8)
cv2.imwrite(str(OUT / "wall-alpha.png"), np.dstack([np.full_like(mask8, 255)] * 3 + [mask8]))

pa = cv2.GaussianBlur(plant.astype(np.float32), (0, 0), 0.8)
cv2.imwrite(str(OUT / "plant.png"), np.dstack([sharpen(up(B)), up(pa) * 255]).clip(0, 255).astype(np.uint8))
# clean plate behind the plant (final shot is on the botanical design) so parallax never reveals a double
hole = nd.binary_dilation(plant, iterations=10).astype(np.uint8) * 255
plate = cv2.inpaint(comps["botanical"].astype(np.uint8), hole, 9, cv2.INPAINT_TELEA).astype(np.float32)
pla = cv2.GaussianBlur(hole.astype(np.float32) / 255, (0, 0), 3)
cv2.imwrite(str(OUT / "plate-botanical.png"), np.dstack([sharpen(up(plate)), up(pla) * 255]).clip(0, 255).astype(np.uint8))

# ---------- 4. selection outline + handles (in 1920x1080 stage units) ----------
sm = cv2.morphologyEx(wall.astype(np.uint8), cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31)))
sm = cv2.morphologyEx(sm, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
cs, _ = cv2.findContours(sm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
c = max(cs, key=cv2.contourArea)
c = cv2.approxPolyDP(c, 3.0, True)[:, 0, :].astype(float) * (1920 / W)
pts = np.clip(c, 4, [1916, 1076])
d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + " Z"
x, y = pts[:, 0], pts[:, 1]
handles = [pts[np.argmin(x + y)], pts[np.argmax(x - y)], pts[np.argmax(x + y)], pts[np.argmax(y - x)]]
wall_js = {"path": d, "handles": [[round(a, 1), round(b, 1)] for a, b in handles]}
(OUT / "wall.js").write_text("// generated by tools/build_assets.py\nwindow.WALL = " + json.dumps(wall_js) + ";\n")
print("wall %.3f  plant px %d  outline pts %d" % (wall.mean(), plant.sum(), len(pts)))

# ---------- 5. swatches (downsized for fast compositing) ----------
for s in ["botanical", "stripe", "arch", "grid", "plain", "moss-trail"]:
    im = cv2.imread(str(A / f"swatch-{s}.png"))
    cv2.imwrite(str(OUT / f"swatch-{s}.jpg"), cv2.resize(im, (720, 720), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 92])
thumb = cv2.resize(B, (336, 189), interpolation=cv2.INTER_AREA)
cv2.imwrite(str(OUT / "thumb-before.jpg"), thumb, [cv2.IMWRITE_JPEG_QUALITY, 92])