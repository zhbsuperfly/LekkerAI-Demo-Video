"""Render index.html to MP4 frame-by-frame.
Usage: .venv/bin/python render.py [--fps 30] [--stills 1,4.5,9] [--out lekker-visualiser.mp4]
"""
import argparse, pathlib, subprocess
import imageio_ffmpeg
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).parent
ap = argparse.ArgumentParser()
ap.add_argument("--fps", type=int, default=30)
ap.add_argument("--stills", default="")
ap.add_argument("--out", default="lekker-visualiser.mp4")
a = ap.parse_args()

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1920, "height": 1080})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto((ROOT / "index.html").as_uri() + "?render=1")
    pg.wait_for_load_state("networkidle")
    # wait until every photo/swatch (HTML <img> and SVG <image>) is fully decoded
    pg.evaluate("""async () => {
      await Promise.all([...document.images].map(i => i.decode().catch(() => {})));
      const hrefs = [...new Set([...document.querySelectorAll('image')].map(e => e.getAttribute('href')))];
      await Promise.all(hrefs.map(h => { const i = new Image(); i.src = h; return i.decode().catch(() => {}); }));
    }""")
    pg.wait_for_timeout(500)
    stage = pg.locator("#stage")
    if a.stills:
        d = ROOT / "stills"; d.mkdir(exist_ok=True)
        for t in a.stills.split(","):
            pg.evaluate(f"seek({float(t)})")
            stage.screenshot(path=str(d / f"t{float(t):05.2f}.png"))
    else:
        dur = pg.evaluate("DUR")
        n = int(dur * a.fps)
        cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(a.fps),
               "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", "-preset", "slow",
               "-movflags", "+faststart", str(ROOT / a.out)]
        ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for i in range(n):
            pg.evaluate(f"seek({i / a.fps})")
            ff.stdin.write(stage.screenshot(type="png"))
            if i % 60 == 0: print(f"frame {i}/{n}", flush=True)
        ff.stdin.close(); ff.wait()
    if errs: print("PAGE ERRORS:", errs)
    b.close()
print("ok")
