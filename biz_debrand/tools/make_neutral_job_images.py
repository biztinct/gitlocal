# -*- coding: utf-8 -*-
"""Draw the neutral stand-ins for the stock careers-page photos.

The stock jobs pages ship photos of the vendor's own staff wearing its
badges. biz_debrand serves these drawings at the same addresses instead
(see models/static_swap.py). No text, no logo: flat people at work in calm,
brand-agnostic colours, sized like the photo each one replaces.

Run: python3 biz_debrand/tools/make_neutral_job_images.py
"""
import os
import random

from PIL import Image, ImageDraw, ImageFilter

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'static', 'img', 'website_hr_recruitment')

SIZES = {
    '1010054_10151543538268963_186969588_n.jpg': (640, 960),
    '1017407_10151536656083963_857938319_n.jpg': (960, 639),
    '1044326_10151536655788963_587131144_n.jpg': (960, 639),
    '882207_10151545507603963_1381082528_o.jpg': (2048, 1365),
    'job_image_1.jpg': (1040, 491), 'job_image_2.jpg': (667, 667),
    'job_image_3.jpg': (1040, 491), 'job_image_4.jpg': (667, 667),
    'job_image_5.jpg': (667, 667), 'job_image_6.jpg': (667, 667),
    'job_image_7.jpg': (989, 441), 'job_image_8.jpg': (709, 473),
    'job_image_9.jpg': (960, 640), 'job_image_10.jpg': (651, 651),
    'job_image_11.jpg': (768, 1152), 'job_image_12.jpg': (709, 743),
    'job_image_13.jpg': (975, 650),
}

# (wall top, wall bottom, floor/desk, accent) — muted, no house colour
PALETTES = [
    ((232, 238, 236), (214, 226, 222), (176, 150, 122), (63, 125, 110)),
    ((240, 234, 226), (226, 216, 202), (150, 120, 96), (196, 120, 82)),
    ((228, 234, 242), (210, 220, 234), (128, 136, 152), (74, 108, 160)),
    ((236, 240, 230), (218, 228, 210), (160, 142, 110), (112, 140, 84)),
    ((242, 236, 238), (228, 218, 222), (140, 124, 120), (160, 96, 112)),
]
SKIN = [(241, 205, 176), (224, 172, 138), (198, 140, 104), (150, 102, 72), (110, 74, 52)]
HAIR = [(40, 32, 30), (70, 50, 36), (120, 86, 52), (24, 24, 28), (150, 120, 90)]
CLOTH = [(74, 108, 160), (63, 125, 110), (196, 120, 82), (90, 90, 110), (160, 96, 112),
         (220, 186, 96), (112, 140, 84), (238, 238, 240)]


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def person(d, cx, base, s, rnd):
    """A seated, flat figure: torso, neck, head, hair. `base` = desk line."""
    cloth, skin, hair = rnd.choice(CLOTH), rnd.choice(SKIN), rnd.choice(HAIR)
    w, h = 0.95 * s, 1.15 * s
    d.rounded_rectangle([cx - w / 2, base - h, cx + w / 2, base + s * .2], radius=s * .42, fill=cloth)
    d.rectangle([cx - s * .09, base - h - s * .14, cx + s * .09, base - h + s * .08], fill=skin)
    r = s * .30
    hy = base - h - s * .38
    d.ellipse([cx - r, hy - r, cx + r, hy + r], fill=skin)
    style = rnd.randint(0, 2)
    if style == 0:      # short
        d.chord([cx - r * 1.05, hy - r * 1.1, cx + r * 1.05, hy + r * .5], 180, 360, fill=hair)
    elif style == 1:    # long
        d.rounded_rectangle([cx - r * 1.12, hy - r * 1.05, cx + r * 1.12, hy + r * 1.5], radius=r, fill=hair)
        d.ellipse([cx - r * .86, hy - r * .62, cx + r * .86, hy + r * .98], fill=skin)
    else:               # bun
        d.chord([cx - r * 1.05, hy - r * 1.1, cx + r * 1.05, hy + r * .4], 180, 360, fill=hair)
        d.ellipse([cx - r * .45, hy - r * 1.75, cx + r * .45, hy - r * .85], fill=hair)


def plant(d, x, base, s, accent):
    pot = (196, 160, 128)
    d.polygon([(x - s * .3, base - s * .55), (x + s * .3, base - s * .55), (x + s * .22, base), (x - s * .22, base)], fill=pot)
    leaf = lerp(accent, (60, 90, 60), .5)
    for ang, dx in ((-1, -.35), (0, 0), (1, .35)):
        d.ellipse([x + dx * s - s * .18, base - s * 1.45 + abs(ang) * s * .25, x + dx * s + s * .18, base - s * .5], fill=leaf)


def scene(name, size, idx):
    rnd = random.Random(name)
    W, H = size
    k = 2                                    # draw large, shrink: smooth edges
    img = Image.new('RGB', (W * k, H * k))
    d = ImageDraw.Draw(img)
    top, bot, desk, accent = PALETTES[idx % len(PALETTES)]
    for y in range(H * k):                   # the wall
        d.line([(0, y), (W * k, y)], fill=lerp(top, bot, y / (H * k)))
    # windows with soft daylight
    win = lerp(top, (255, 255, 255), .55)
    n = 3 if W >= H else 2
    ww = W * k / (n * 1.6)
    for i in range(n):
        x0 = (i + .3) * W * k / n
        d.rounded_rectangle([x0, H * k * .08, x0 + ww, H * k * .42], radius=10 * k, fill=win)
        d.line([(x0 + ww / 2, H * k * .08), (x0 + ww / 2, H * k * .42)], fill=bot, width=3 * k)
    # a shelf or a board on the wall
    d.rounded_rectangle([W * k * .06, H * k * .48, W * k * .3, H * k * .5], radius=4 * k, fill=lerp(desk, top, .3))
    for j in range(4):
        bx = W * k * (.07 + j * .05)
        d.rectangle([bx, H * k * .43, bx + W * k * .03, H * k * .48], fill=rnd.choice(CLOTH))
    # people round the desk
    base = H * k * .74
    s = min(W, H) * k * (.16 if W >= H else .13)
    count = max(2, min(5, int(W / H * 3)))
    xs = [W * k * (i + 1) / (count + 1) for i in range(count)]
    for x in xs:
        person(d, x + rnd.uniform(-s * .2, s * .2), base, s, rnd)
    # the desk, laptops and cups
    d.rounded_rectangle([-10, base, W * k + 10, H * k + 10], radius=0, fill=desk)
    d.rectangle([0, base, W * k, base + 6 * k], fill=lerp(desk, (255, 255, 255), .25))
    for x in xs[::2]:
        lw = s * .9
        d.polygon([(x - lw / 2, base), (x + lw / 2, base), (x + lw * .42, base - lw * .55), (x - lw * .42, base - lw * .55)],
                  fill=(205, 210, 216))
        d.ellipse([x - 5 * k, base - lw * .3, x + 5 * k, base - lw * .3 + 10 * k], fill=(235, 238, 242))
    for x in xs[1::2]:
        d.rounded_rectangle([x + s * .35, base - s * .32, x + s * .55, base], radius=3 * k, fill=accent)
    plant(d, W * k * .94, base, s * .9, accent)
    img = img.filter(ImageFilter.GaussianBlur(.6)).resize((W, H), Image.LANCZOS)
    img.save(os.path.join(OUT, name), quality=86, optimize=True)


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    for i, (n, sz) in enumerate(sorted(SIZES.items())):
        scene(n, sz, i)
    print('wrote', len(SIZES), 'pictures to', OUT)
