"""
Файл: /App/services/image_safety.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Выбор разрешённых растровых декодеров до разбора недоверенных данных.
"""
from .lazy_imports import OptionalModule

Image = OptionalModule('PIL.Image')
RASTER_FORMATS = ('PNG', 'JPEG', 'WEBP', 'BMP', 'GIF')
MAX_PIXELS = 20_000_000


def open_raster(source, *, formats=RASTER_FORMATS, max_pixels=MAX_PIXELS):
    """The caller owns/closes the image; no unrestricted decoder fallback."""
    if not Image:
        raise ValueError('Для обработки изображения нужна библиотека Pillow')
    # Checking .format after open() is too late for open-time parser bugs.
    image = Image.open(source, formats=formats)
    try:
        if max_pixels is not None and image.width * image.height > max_pixels:
            raise ValueError('Изображение слишком большое')
        return image
    except Exception:
        image.close()
        raise
