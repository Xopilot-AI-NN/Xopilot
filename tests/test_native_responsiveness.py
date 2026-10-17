"""
Файл: /tests/test_native_responsiveness.py
Разработчик: DenBroLiik
Версия: 2.0.10
Описание: Проверка отзывчивости Python при ожидании записи в SQLCipher. Исполнитель: Codex.
"""
import asyncio
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
import sys
from unittest.mock import Mock,patch

from App.services.db import advanced_xopilot
from App.services import db,platforms


class DatabaseCreationTests(unittest.IsolatedAsyncioTestCase):
    async def test_parallel_workers_create_only_one_connection(self):
        connection=Mock()
        def create(*args):time.sleep(.05);return connection
        factory=Mock(side_effect=create)
        with tempfile.TemporaryDirectory() as folder,patch.object(db,'_db',None), \
                patch.object(db,'_app_data_dir',return_value=folder), \
                patch.object(db,'advanced_xopilot',Mock(PyDatabase=factory)), \
                patch.object(platforms,'is_android',return_value=False):
            opened=await asyncio.gather(asyncio.to_thread(db.get_db),asyncio.to_thread(db.get_db))
            self.assertEqual(opened,[connection,connection])
            factory.assert_called_once()


@unittest.skipUnless(sys.platform.startswith('linux') and advanced_xopilot is not None and shutil.which('sqlcipher') and shutil.which('stdbuf'),
                     'Требуются нативная БД и Linux CLI SQLCipher/stdbuf')
class NativeResponsivenessTests(unittest.IsolatedAsyncioTestCase):
    async def test_database_lock_wait_releases_python_for_ui(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'qa.db';key='11'*32
            database=advanced_xopilot.PyDatabase(str(path),key=key)
            chat=database.create_chat('QA')
            holder=subprocess.Popen(['stdbuf','-oL','sqlcipher',str(path)],stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                holder.stdin.write("PRAGMA key='"+key+"';\nBEGIN IMMEDIATE;\n.print READY\n.shell sleep 0.8\nROLLBACK;\n.quit\n")
                holder.stdin.flush()
                # Readiness is from an external process, not a timer blocked by GIL.
                def ready():
                    for line in holder.stdout:
                        if line.strip()=='READY':return
                    raise AssertionError('SQLCipher holder did not start')
                await asyncio.wait_for(asyncio.to_thread(ready),3)
                ticks=[];running=True
                async def heartbeat():
                    while running:
                        ticks.append(time.monotonic())
                        await asyncio.sleep(.01)
                beat=asyncio.create_task(heartbeat())
                await asyncio.sleep(.03)
                try:await asyncio.to_thread(database.add_message,chat,'ai','QA')
                finally:
                    await asyncio.sleep(.03);running=False;await beat
                self.assertGreater(len(ticks),15)
                self.assertLess(max(b-a for a,b in zip(ticks,ticks[1:])),.35)
                self.assertEqual(len(database.get_messages(chat)),1)
            finally:
                if holder.poll() is None:holder.terminate()
                holder.communicate(timeout=3)
                database.close()
