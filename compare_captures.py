"""Pixel-compare two harness capture sets of the same route (e.g. before/after a change).

Reports, per shot, the fraction of pixels whose colour changed by more than
THRESHOLD (0-255 max channel delta), ignoring the top 12% and bottom 22% of the
frame where the HUD, timer and weapon live. Writes a side-by-side diff sheet
for every shot above LIMIT.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

THRESHOLD = 24
LIMIT = .002


def shots(folder):
    return {re.sub(r'-[0-9a-f]{8}\.png$', '', p.name): p for p in Path(folder, 'screenshots').glob('*.png')}


def compare(before, after, out):
    a, b = shots(before), shots(after); out = Path(out); out.mkdir(parents=True, exist_ok=True); rows = {}
    for name in sorted(set(a) & set(b)):
        x = np.asarray(Image.open(a[name]).convert('RGB'), 'i2'); y = np.asarray(Image.open(b[name]).convert('RGB'), 'i2')
        h = x.shape[0]; top, bottom = int(h*.12), int(h*.78)
        diff = np.abs(x-y).max(2)[top:bottom]; frac = float((diff > THRESHOLD).mean())
        rows[name] = round(frac, 5)
        if frac > LIMIT:
            mask = np.zeros_like(x[:, :, 0], 'u1'); mask[top:bottom] = (diff > THRESHOLD)*255
            sheet = Image.new('RGB', (x.shape[1]*3//2, x.shape[0]//2))
            for i, im in enumerate((Image.open(a[name]), Image.open(b[name]), Image.fromarray(mask))):
                sheet.paste(im.convert('RGB').resize((x.shape[1]//2, x.shape[0]//2)), (i*x.shape[1]//2, 0))
            sheet.save(out/(name+'.png'))
    (out/'compare.json').write_text(json.dumps(rows, indent=2))
    return rows


if __name__ == '__main__':
    r = compare(*sys.argv[1:4])
    for k, v in sorted(r.items(), key=lambda kv: -kv[1]):
        print(f'{v:8.4f} {k}')
