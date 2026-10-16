"""
Файл: /tests/test_app_package_layout.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Проверка импортов интерфейса в тестовом и упакованном режиме запуска.
"""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class AppPackageImportsTests(unittest.TestCase):
    def test_ui_modules_import_in_both_launch_modes(self):
        root=Path(__file__).resolve().parents[1]
        modules=sorted('.'.join(p.relative_to(root/'App').with_suffix('').parts)
                       for p in (root/'App/app').rglob('*.py')
                       if p.name!='__init__.py')
        for prefix,entry in [('App.',root),('',root/'App')]:
            with self.subTest(prefix=prefix):
                source='import importlib\n'+''.join(
                    f'importlib.import_module({prefix+module!r})\n' for module in modules)
                environment=dict(os.environ)
                environment['PYTHONPATH']=os.pathsep.join(
                    [str(entry),environment.get('PYTHONPATH','')])
                environment['PYTHONDONTWRITEBYTECODE']='1'
                result=subprocess.run([sys.executable,'-c',source],cwd=root,
                    env=environment,capture_output=True,text=True,timeout=30)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
