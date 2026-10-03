import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from App.services.exports import save_local_export


class ExportTests(unittest.TestCase):
    def test_exports_preserve_bytes_and_never_overwrite_or_escape_folder(self):
        with tempfile.TemporaryDirectory() as directory, patch('App.services.exports.app_data_dir', return_value=Path(directory)):
            first = Path(save_local_export('../Canvas.py', b'print(2 + 2)\n'))
            second = Path(save_local_export('Canvas.py', b'print(3 + 3)\n'))
            self.assertNotEqual(first, second)
            self.assertTrue(first.is_relative_to(Path(directory)/'exports'))
            self.assertEqual(first.name, 'Canvas.py')
            self.assertEqual(first.read_bytes(), b'print(2 + 2)\n')
            self.assertEqual(second.read_bytes(), b'print(3 + 3)\n')

    def test_failed_export_removes_its_partial_file(self):
        with tempfile.TemporaryDirectory() as directory, patch('App.services.exports.app_data_dir', return_value=Path(directory)):
            with self.assertRaises(TypeError):
                save_local_export('bad.txt', None)
            self.assertEqual(list((Path(directory)/'exports').iterdir()), [])

    def test_drawing_export_preserves_canvas_proportions(self):
        import io
        from PIL import Image
        from App.services.canvases import export_document
        _, data = export_document({'title':'drawing', 'kind':'drawing', 'drawing_size':[600,300],
            'strokes':[{'color':'#7657ff','width':3,'points':[[.1,.2],[.9,.8]]}]})
        with Image.open(io.BytesIO(data)) as image:
            self.assertEqual(image.size, (1200,600))
            self.assertEqual(image.getpixel((120,120)), (118,87,255))
