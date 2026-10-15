"""
Файл: /tests/test_desktop_control.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Разрешения, независимые действия, упаковка и кадры управления Linux.
"""
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from App.services import desktop_control as desktop


class DesktopTests(unittest.TestCase):
    def test_denial_does_not_start_helper(self):
        session=desktop.ComputerSession()
        with patch.object(desktop,'Bridge') as bridge:
            with self.assertRaisesRegex(ValueError,'не разрешён'):session.start(threading.Event(),lambda _:False)
            bridge.assert_not_called()

    def test_input_requires_screen_and_approval(self):
        session=desktop.ComputerSession();cancelled=threading.Event()
        with self.assertRaisesRegex(ValueError,'computer_view'):session.input({'action':'click','target':'button'},cancelled,Mock())
        session.bridge=Mock();session.size=[100,100];session.observed=True;session.controls={'button':{'id':'button','role':'button','name':'QA'}}
        with self.assertRaisesRegex(ValueError,'не подтверждено'):session.input({'action':'click','target':'button'},cancelled,lambda _:False)
        session.bridge.call.assert_not_called()

    def test_raw_mouse_and_keyboard_are_rejected(self):
        for arguments in [{'action':'move','x':1,'y':1},{'action':'key','keys':['ctrl','a']},
                          {'action':'type','text':'hello'},{'action':'click','x':1,'y':1},
                          {'action':'set_text','target':'text','text':'a\x00'}]:
            with self.subTest(arguments=arguments),self.assertRaises(ValueError):desktop.validate_input(arguments)

    def test_input_returns_fresh_frame_and_cleanup_removes_copies(self):
        from PIL import Image
        session=desktop.ComputerSession();session.bridge=Mock();session.size=[100,80];session.observed=True;session.controls={'button':{'id':'button','role':'button','name':'QA'}}
        session.folder=tempfile.TemporaryDirectory()
        def call(method,args=None,cancelled=None):
            if method=='capture':Image.new('RGB',(100,80)).save(args['path']);return {}
            if method=='inspect':return [{'id':'button','role':'button','name':'QA'}]
            return {'performed':True}
        session.bridge.call.side_effect=call
        result,files=session.input({'action':'click','target':'button'},threading.Event(),lambda _:True)
        self.assertTrue(result['performed']);self.assertEqual(result['image_size'],[100,80])
        path=Path(files[0][1]);self.assertTrue(path.exists());helper=session.bridge
        session.close();helper.close.assert_called_once();self.assertFalse(path.exists())

    def test_application_launch_requires_catalog_entry_and_confirmation(self):
        cancelled=threading.Event()
        with patch.object(desktop,'apps',return_value=[{'package':'org.example.desktop','name':'Example'}]),patch.object(desktop,'Bridge') as bridge:
            with self.assertRaises(ValueError):desktop.launch('/bin/sh',cancelled,lambda _:True)
            with self.assertRaises(ValueError):desktop.launch('org.example.desktop',cancelled,lambda _:False)
            bridge.assert_not_called()
            desktop.launch('org.example.desktop',cancelled,lambda _:True)
            bridge.return_value.call.assert_called_once_with('launch',{'package':'org.example.desktop'},cancelled)
            bridge.return_value.close.assert_called_once()

    def test_unseen_target_is_rejected_before_confirmation(self):
        session=desktop.ComputerSession();session.bridge=Mock();session.observed=True;session.size=[100,100]
        approve=Mock(return_value=True)
        with self.assertRaisesRegex(ValueError,'последнего computer_view'):
            session.input({'action':'click','target':'unseen'},threading.Event(),approve)
        approve.assert_not_called();session.bridge.call.assert_not_called()

    @unittest.skipUnless(Path('/usr/bin/python3').is_file(),'Linux system Python path required')
    def test_packaged_helpers_work_without_python_source_modules(self):
        import shutil
        with tempfile.TemporaryDirectory() as directory:
            app=Path(directory)/'App';(app/'services').mkdir(parents=True)
            source=Path(__file__).resolve().parents[1]/'App/assets/linux_desktop'
            shutil.copytree(source,app/'assets/linux_desktop')
            with patch.object(desktop,'__file__',str(app/'services/desktop_control.pyc')),patch.object(desktop,'supported',return_value=True),patch.object(desktop.subprocess,'Popen') as process:
                process.return_value.poll.return_value=0
                helper=desktop.Bridge()
                command=process.call_args.args[0];script=Path(command[1])
                self.assertTrue(script.is_file());self.assertTrue(script.with_name('linux_accessibility.py').is_file())
                self.assertFalse((app/'services/linux_desktop_bridge.py').exists())
                helper.close();self.assertFalse(script.exists())

    def test_agent_closes_session_when_model_fails(self):
        from App.services import agent
        with patch.object(desktop,'ComputerSession') as computer,patch.object(agent,'_run_agent',side_effect=RuntimeError('model failed')):
            with self.assertRaises(RuntimeError):agent.run_agent('test')
            computer.return_value.close.assert_called_once()

    def test_model_click_case_is_normalized_but_missing_arguments_are_repaired_before_execution(self):
        from App.services.agent import parse_response
        import json
        value=parse_response(json.dumps({'tool':'computer_input','arguments':{'action':'Click','target':'fresh','name':'Click'}}))
        self.assertEqual(value['arguments']['action'],'click')
        for value in [{}, {'action':'Click'}, {'action':'move','target':'fresh'}]:
            parsed=parse_response(json.dumps({'tool':'computer_input','arguments':value}))
            self.assertIn('error',parsed)
        self.assertIn('error',parse_response('{"tool":"computer_input"}'))

    def test_model_catalog_matches_phone_and_attached_folder(self):
        from App.services import agent,platforms
        with patch.object(platforms,'is_android',return_value=True):
            catalog=agent.available_tools({'enabled':True,'root':'/project'})
        self.assertNotIn('computer_start',catalog);self.assertNotIn('run_project_command',catalog)
        self.assertIn('control_media',catalog);self.assertIn('read_chat',catalog)
        with patch.object(platforms,'is_android',return_value=False),patch.object(desktop,'supported',return_value=True):
            catalog=agent.available_tools({'enabled':False})
            self.assertNotIn('run_project_command',catalog);self.assertIn('computer_start',catalog)
            self.assertIn('run_project_command',agent.available_tools({'enabled':True,'root':'/project'}))
