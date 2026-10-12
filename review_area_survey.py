"""Build labelled QA contact sheets without altering native capture files."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent

def review(folder):
    folder = ROOT / folder
    data = json.loads((folder/'comparison.json').read_text())
    out = ROOT/'output/area-survey'/folder.name
    out.mkdir(parents=True, exist_ok=True)
    for page in range(0, len(data['pairs']), 4):
        pairs = data['pairs'][page:page+4]
        canvas = Image.new('RGB', (1280, len(pairs)*390+30), '#101722')
        draw = ImageDraw.Draw(canvas)
        draw.text((12,8), 'Original R5R (left) / Northstar port (right) — review thumbnails', fill='white')
        for row, pair in enumerate(pairs):
            y = row*390+30
            draw.text((12,y+5), pair['name'], fill='white')
            for column, engine in enumerate(('r5r','northstar')):
                record = pair[engine]
                path = folder/record['gallery_path']
                if hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
                    raise ValueError('Capture hash mismatch: '+str(path))
                with Image.open(path) as image:
                    if image.size != (record['width'],record['height']):
                        raise ValueError('Capture dimensions differ from metadata')
                    canvas.paste(image.convert('RGB').resize((640,360),Image.Resampling.LANCZOS), (column*640,y+30))
        path = out/f'contact-{page//4+1}.png'
        canvas.save(path)
        print(path)

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('comparison')
    review(p.parse_args().comparison)
