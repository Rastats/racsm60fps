#!/usr/bin/env python3
"""Side-by-side animated GIF of two capture runs (window captures f001.png...),
one captured frame per emulated render, played at half speed (GIF delays below
20 ms are clamped by viewers, so 59.94 Hz cannot be shown in real time).

Usage: python make_strip.py <left run> <right run> <out.gif> [--labels "G1" "G1+RI"] [--scale 0.5] [--crop x0 y0 x1 y1]
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('left'); ap.add_argument('right'); ap.add_argument('out')
    ap.add_argument('--labels', nargs=2, default=['G1 (pump 1 at 30 Hz)', 'G1 + render interpolation'])
    ap.add_argument('--scale', type=float, default=0.5)
    ap.add_argument('--frame-ms', type=int, default=33)
    ap.add_argument('--crop', type=int, nargs=4, metavar=('X0', 'Y0', 'X1', 'Y1'), help='crop box before scaling')
    a = ap.parse_args()
    lf = sorted(Path(a.left).glob('f*.png'))
    rf = sorted(Path(a.right).glob('f*.png'))
    n = min(len(lf), len(rf))
    frames = []
    for i in range(n):
        L, R = Image.open(lf[i]).convert('RGB'), Image.open(rf[i]).convert('RGB')
        if a.crop:
            L, R = L.crop(tuple(a.crop)), R.crop(tuple(a.crop))
        w, h = int(L.width * a.scale), int(L.height * a.scale)
        canvas = Image.new('RGB', (2 * w + 4, h + 18), (0, 0, 0))
        canvas.paste(L.resize((w, h)), (0, 18))
        canvas.paste(R.resize((w, h)), (w + 4, 18))
        dr = ImageDraw.Draw(canvas)
        dr.text((4, 3), '%s  #%02d' % (a.labels[0], i + 1), fill=(255, 255, 255))
        dr.text((w + 8, 3), '%s  (x1/%.0f speed)' % (a.labels[1], a.frame_ms / 16.68), fill=(255, 255, 255))
        frames.append(canvas)
    frames[0].save(a.out, save_all=True, append_images=frames[1:], duration=a.frame_ms, loop=0)
    print(a.out, n, 'frames')


if __name__ == '__main__':
    main()
