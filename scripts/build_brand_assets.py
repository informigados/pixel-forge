"""Convert the supplied transparent icon to Windows/web sizes without stretching."""
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]


def build_icons(image_dir=None):
    directory = Path(image_dir) if image_dir else ROOT / 'static' / 'images'
    with Image.open(directory / 'icon.png') as original:
        image = original.convert('RGBA')
        # Ignore nearly invisible pixels when calculating transparent margins.
        bounds = image.getchannel('A').point(lambda alpha: 255 if alpha > 16 else 0).getbbox()
        if not bounds:
            raise ValueError('The application icon is empty')
        image = image.crop(bounds)
        canvas = Image.new('RGBA', (512, 512))
        fitted = ImageOps.contain(image, (464, 464), Image.Resampling.LANCZOS)
        canvas.alpha_composite(fitted, ((512-fitted.width)//2, (512-fitted.height)//2))
        canvas.save(directory / 'app-icon.ico', sizes=[(16,16), (24,24), (32,32), (48,48), (64,64), (128,128), (256,256)])
        for size in [32, 192, 512]:
            canvas.resize((size, size), Image.Resampling.LANCZOS).save(directory / f'icon-{size}.png', optimize=True)
    return directory / 'app-icon.ico'


if __name__ == '__main__':
    print(build_icons())
