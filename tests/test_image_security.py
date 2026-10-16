"""
Файл: /tests/test_image_security.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Codex проверяет выбор декодера до разбора вложений и аватарок без запуска опасных парсеров.
"""
import base64
import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from PIL import Image
from App.services import attachments, image_safety, material_preview, profile
from App.app.materials import material


class ImageBoundaryTests(unittest.TestCase):
    def test_disallowed_magic_never_selects_parser_in_any_input_boundary(self):
        Image.init()
        signatures = (
            ('EPS', b'%!PS-Adobe-3.0 EPSF-3.0\n'),
            ('EPS', bytes.fromhex('c5d0d3c6')),
            ('JPEG2000', bytes.fromhex('ff4fff51')),
            ('JPEG2000', bytes.fromhex('0000000c6a5020200d0a870a')),
            ('MCIDAS', bytes.fromhex('0000000000000004')),
        )
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'renamed.png'
            for codec, magic in signatures:
                with self.subTest(codec=codec, magic=magic.hex()):
                    raw = magic + b'\0' * 256
                    path.write_bytes(raw)
                    factory, accept = Image.OPEN[codec]
                    self.assertTrue(accept(raw[:16]))
                    # Strong substitute: a marker replaces the parser body.
                    # If selected, it fails immediately rather than hanging or
                    # exercising an unsafe native decoder on the test machine.
                    marker = Mock(side_effect=RuntimeError('FORBIDDEN_PARSER_SELECTED'))
                    with patch.dict(Image.OPEN, {codec: (marker, accept)}):
                        material._image_preview.cache_clear()
                        self.assertEqual(material.image_preview(str(path)), b'')
                        with self.assertRaises((ValueError, OSError)):
                            profile.normalize_avatar(raw)
                        with self.assertRaises((ValueError, OSError)):
                            profile.validate({'name': 'User', 'avatar': base64.b64encode(raw).decode()})
                        with patch.object(material_preview, 'resolve', return_value=path):
                            with self.assertRaises((ValueError, OSError)):
                                material_preview.preview(path, 'renamed.png')
                        notes, images = attachments.build_attachment_message_parts([('renamed.png', str(path))])
                        self.assertEqual(images, [])
                        self.assertIn('Ошибка чтения', notes[0])
                    marker.assert_not_called()

    def test_normal_rasters_keep_preview_avatar_and_model_workflows(self):
        with TemporaryDirectory() as directory:
            for codec in image_safety.RASTER_FORMATS:
                with self.subTest(codec=codec):
                    source = io.BytesIO()
                    Image.new('RGB', (320, 256), '#336699').save(source, codec)
                    raw = source.getvalue()
                    path = Path(directory) / 'photo.png'
                    path.write_bytes(raw)
                    material._image_preview.cache_clear()
                    self.assertTrue(material.image_preview(str(path)).startswith(b'\xff\xd8'))
                    notes, images = attachments.build_attachment_message_parts([('photo.png', str(path))])
                    self.assertEqual(notes, [])
                    with Image.open(io.BytesIO(images[0])) as image:
                        self.assertEqual(image.format, 'JPEG')
                    with patch.object(material_preview, 'resolve', return_value=path):
                        self.assertTrue(material_preview.preview(path, 'photo.png')['image'].startswith('data:image/jpeg;'))
                    avatar = profile.normalize_avatar(raw)
                    self.assertEqual(profile.validate({'name': 'User', 'avatar': avatar})['avatar'], avatar)

    def test_synced_avatar_only_accepts_normalized_jpeg(self):
        source = io.BytesIO()
        Image.new('RGB', (256, 256)).save(source, 'PNG')
        with self.assertRaises((ValueError, OSError)):
            profile.validate({'name': 'User', 'avatar': base64.b64encode(source.getvalue()).decode()})

    def test_corrupt_or_unavailable_decoder_never_forwards_original_bytes(self):
        with self.assertRaises((ValueError, OSError)):
            attachments._downscale_image_bytes(b'not an image')
        with patch.object(image_safety, 'Image', False):
            with self.assertRaises(ValueError):
                attachments._downscale_image_bytes(b'not an image')

    def test_pixel_limit_closes_image_before_pixels_are_loaded(self):
        image = Mock(width=5000, height=5000)
        decoder = Mock(open=Mock(return_value=image))
        with patch.object(image_safety, 'Image', decoder):
            with self.assertRaisesRegex(ValueError, 'слишком большое'):
                image_safety.open_raster(io.BytesIO(b'input'))
        image.close.assert_called_once()
        image.load.assert_not_called()
        self.assertEqual(decoder.open.call_args.kwargs['formats'], image_safety.RASTER_FORMATS)


if __name__ == '__main__':
    unittest.main()
