"""Run: python3 -m unittest discover -s TRON-Control -p 'test_*.py'."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('control',Path(__file__).with_name('tron_control.py'))
control=importlib.util.module_from_spec(spec); spec.loader.exec_module(control)

class ValidationTests(unittest.TestCase):
    def make_pcd(self,path,truncated=False):
        header=b'VERSION 0.7\nFIELDS x y z\nSIZE 4 4 4\nTYPE F F F\nCOUNT 1 1 1\nWIDTH 2\nHEIGHT 1\nPOINTS 2\nDATA binary\n'
        path.write_bytes(header+b'\x00'*(12 if truncated else 24))
    def validate(self,path):
        return subprocess.run(['bash','-c',control.pycmd(control.VALIDATE,path)],capture_output=True,text=True)
    def test_complete_binary(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'map with spaces.pcd'; self.make_pcd(p)
            r=self.validate(p); self.assertEqual(r.returncode,0,r.stderr); self.assertIn('"points": 2',r.stdout)
    def test_truncation_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'map.pcd'; self.make_pcd(p,True)
            self.assertNotEqual(self.validate(p).returncode,0)
    def test_shell_quote_no_injection(self):
        arg="some map ' ; echo WRONG"
        result=subprocess.check_output(['bash','-c',control.pycmd('import sys;print(repr(sys.argv[1]))',arg)],text=True)
        self.assertEqual(result.strip(),repr(arg))
    def test_remote_command_grouped_as_single_argument(self):
        app=control.App.__new__(control.App)
        args=app.ssh_args('10.192.1.3',control.environment('10.192.1.3')+'exec roscore',True)
        self.assertIn('-tt',args); self.assertIn('BatchMode=yes',args)
        self.assertEqual(args[-2],'guest@10.192.1.3')
        self.assertIn('http://10.192.1.3:11311',args[-1])
    def test_archive_existing_destination_protected(self):
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/'scans.pcd'; dst=Path(d)/'Jenna.pcd'
            src.write_bytes(b'new'); dst.write_bytes(b'old')
            code='import os,sys;os.link(sys.argv[1],sys.argv[2]);os.unlink(sys.argv[1])'
            r=subprocess.run(['bash','-c',control.pycmd(code,src,dst)],capture_output=True)
            self.assertNotEqual(r.returncode,0)
            self.assertEqual(dst.read_bytes(),b'old'); self.assertTrue(src.exists())

if __name__=='__main__': unittest.main()

class LanguageTests(unittest.TestCase):
    def tearDown(self): control.LANGUAGE='hu'
    def test_both_languages(self):
        control.LANGUAGE='en'
        self.assertEqual(control.tr('①  Kapcsolat ellenőrzése'),'①  Check connection')
        control.LANGUAGE='hu'
        self.assertEqual(control.tr('①  Check connection'),'①  Kapcsolat ellenőrzése')
    def test_all_phrases_roundtrip(self):
        for hu,en in control.TRANSLATIONS.items():
            self.assertEqual(control.translate_existing(hu,'en'),en,hu)
            self.assertEqual(control.translate_existing(en,'hu'),hu,en)
    def test_formatted_status_switch(self):
        self.assertEqual(control.translate_existing('○ leállt (0)','en'),'○ stopped (0)')
        self.assertEqual(control.translate_existing('○ stopped (0)','hu'),'○ leállt (0)')
    def test_raw_ros_log_kept(self):
        text='[INFO] [3845.252880608]: IMU Initial Done\n/cloud_registered 10Hz'
        self.assertEqual(control.translate_existing(text,'en'),text)
    def test_python38_compatible_syntax(self):
        import ast
        ast.parse(Path(control.__file__).read_text(),feature_version=(3,8))

class TerminalTests(unittest.TestCase):
    def test_each_component_has_its_own_terminal(self):
        from unittest.mock import patch
        app=control.App.__new__(control.App)
        app.process_logs={'core':Path('/tmp/core.log'),'lidar':Path('/tmp/lidar.log'),'mapping':Path('/tmp/mapping.log')}
        with patch.object(control.subprocess,'Popen') as popen:
            for key in app.process_logs: app.open_process_terminal(key)
            self.assertEqual(popen.call_count,3)
            for call,key in zip(popen.call_args_list,app.process_logs):
                args=call.args[0]
                self.assertIn('--window',args); self.assertIn('tail',args)
                self.assertEqual(args[-1],str(app.process_logs[key]))
    def test_interactive_terminal_allows_password_prompt(self):
        from unittest.mock import patch
        app=control.App.__new__(control.App)
        app.host=lambda:'10.192.1.3'; app.emit=lambda *args:None
        with patch.object(control.subprocess,'Popen') as popen:
            app.robot_terminal()
            args=popen.call_args.args[0]
            self.assertIn('BatchMode=no',args)
            self.assertNotIn('BatchMode=yes',args)
            self.assertIn('-tt',args)
            self.assertIn('exec bash -i',args[-1])

class ChunkTests(ValidationTests):
    def run_script(self,script,*args):
        return subprocess.run(['bash','-c',control.pycmd(script,*args)],capture_output=True,text=True)
    def test_prepare_preserves_configuration_and_refuses_leftovers(self):
        import xml.etree.ElementTree as ET
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'PCD').mkdir(); dest=root/'PCD/test'
            r=self.run_script(control.PREPARE_CHUNKS,root,dest)
            self.assertEqual(r.returncode,0,r.stderr)
            xml=ET.parse(dest/'recording.launch').getroot()
            self.assertEqual(xml[-1].attrib['value'],'-1')
            self.assertEqual(xml[0].tag,'include')
            (root/'PCD/scans_1.pcd').write_bytes(b'preserve')
            r=self.run_script(control.PREPARE_CHUNKS,root,root/'PCD/other')
            self.assertNotEqual(r.returncode,0)
            self.assertEqual((root/'PCD/scans_1.pcd').read_bytes(),b'preserve')
    def test_single_file_mode_finalize_and_list(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'PCD').mkdir(); dest=root/'PCD/test'
            r=self.run_script(control.PREPARE_CHUNKS,root,dest)
            self.assertEqual(r.returncode,0,r.stderr)
            self.make_pcd(root/'PCD/scans.pcd')
            r=self.run_script(control.FINALIZE_CHUNKS,root,dest,control.VALIDATE)
            self.assertEqual(r.returncode,0,r.stderr)
            manifest=json.loads(r.stdout)
            self.assertEqual(manifest['interval_frames'],-1)
            self.assertEqual(len(manifest['files']),1)
            self.assertEqual(Path(manifest['files'][0]['path']).name,'scans.pcd')
            r=self.run_script(control.LIST_RECORDING,dest,control.VALIDATE)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(len(json.loads(r.stdout)),1)
    def test_finalize_all_parts_and_tail_retry(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'PCD').mkdir(); dest=root/'PCD/test';dest.mkdir()
            for n in ['scans_1.pcd','scans_2.pcd','scans.pcd']: self.make_pcd(root/'PCD'/n)
            for _ in range(2):
                r=self.run_script(control.FINALIZE_CHUNKS,root,dest,control.VALIDATE)
                self.assertEqual(r.returncode,0,r.stderr)
                self.assertEqual(len(json.loads(r.stdout)['files']),3)
            r=self.run_script(control.LIST_RECORDING,dest,control.VALIDATE)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(len(json.loads(r.stdout)),3)
    def test_truncated_part_preserves_all_sources(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'PCD').mkdir(); dest=root/'PCD/test';dest.mkdir()
            self.make_pcd(root/'PCD/scans_1.pcd')
            self.make_pcd(root/'PCD/scans_2.pcd',True)
            r=self.run_script(control.FINALIZE_CHUNKS,root,dest,control.VALIDATE)
            self.assertNotEqual(r.returncode,0)
            self.assertTrue((root/'PCD/scans_1.pcd').exists())
            self.assertFalse((dest/'manifest.json').exists())

class LocalToolsTests(unittest.TestCase):
    def test_simulation_resets_robot_addresses(self):
        from local_tools import simulation_command
        with tempfile.TemporaryDirectory() as d:
            cmd=simulation_command(d)
            self.assertIn('127.0.0.1:11321',cmd)
            self.assertIn('GAZEBO_MASTER_URI=http://127.0.0.1:11355',cmd)
            self.assertNotIn('10.192.',cmd)
            self.assertIn('roslaunch -p 11321 gazebo_ros empty_world.launch',cmd)
    def test_missing_model_launch_rejected(self):
        from local_tools import simulation_command
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):simulation_command(d,d+'/missing.launch')
    def test_viewer_arguments_not_shell(self):
        from local_tools import viewer_command
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a; echo bad.pcd';p.touch()
            self.assertEqual(viewer_command([p]),['pcl_viewer',str(p)])
    def test_custom_world_quoted(self):
        from local_tools import simulation_command
        import shlex
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test world.world';p.touch()
            cmd=simulation_command(d,world=p)
            self.assertIn(shlex.quote('world_name:='+str(p)),cmd)

class BagTests(unittest.TestCase):
    def test_active_bag_rejected_before_rosbag_read(self):
        # Stub import so this failure path is testable without ROS.
        with tempfile.TemporaryDirectory() as d:
            Path(d,'rosbag.py').write_text('')
            Path(d,'raw.bag.active').touch()
            import os
            env=dict(os.environ,PYTHONPATH=d)
            r=subprocess.run(['python3','-c',control.VALIDATE_BAGS,d],env=env,capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0)
            self.assertIn('active or interrupted',r.stderr)
    def test_bag_requires_both_sensor_topics(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d,'rosbag.py').write_text('''
class Info:
    message_count=10
class Topics:
    topics={'/livox/lidar':Info()}
class Bag:
    def __init__(self,*a): pass
    def __enter__(self): return self
    def __exit__(self,*a): pass
    def get_type_and_topic_info(self): return Topics()
''')
            Path(d,'raw.bag').touch()
            import os
            r=subprocess.run(['python3','-c',control.VALIDATE_BAGS,d],env=dict(os.environ,PYTHONPATH=d),capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0)
            self.assertIn('Missing LiDAR or IMU',r.stderr)
            self.assertFalse(Path(d,'manifest.json').exists())

class CopyIntegrationTests(ValidationTests):
    def exercise(self,corrupt=False):
        from unittest.mock import patch
        import shutil,json
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'recording';source.mkdir();target=root/'copied'
            entries=[]
            for name in ['scans_1.pcd','scans_2.pcd','scans.pcd']:
                p=source/name;self.make_pcd(p);entries.append({'path':str(p),'bytes':p.stat().st_size})
            (source/'manifest.json').write_text(json.dumps({'files':entries}))
            app=control.App.__new__(control.App)
            class Var:
                def __init__(self,v):self.v=v
                def get(self):return self.v
            app.name=Var('test');app.destination=Var(str(target));app.saved=None
            events=[];app.emit=lambda *a:events.append(a)
            real_run=subprocess.run
            app.remote=lambda ip,cmd,**kw:subprocess.check_output(['bash','-c',cmd],text=True).strip()
            app.task=lambda fn:fn('127.0.0.1')
            def run(args,**kw):
                if args[0]=='scp':
                    shutil.copyfile(args[-2].split(':',1)[1],args[-1])
                    if corrupt:
                        q=Path(args[-1]);data=q.read_bytes();q.write_bytes(data[:-1]+bytes([data[-1]^1]))
                    return subprocess.CompletedProcess(args,0,stdout='',stderr='')
                return real_run(args,**kw)
            with patch.object(control.subprocess,'run',side_effect=run):
                if corrupt:
                    with self.assertRaises(RuntimeError):app.copy_map(str(source))
                    self.assertFalse((target/'recording').exists())
                    self.assertEqual(list(target.iterdir()),[])
                else:
                    app.copy_map(str(source))
                    for name in ['scans_1.pcd','scans_2.pcd','scans.pcd']:
                        self.assertEqual((target/'recording'/name).read_bytes(),(source/name).read_bytes())
                    self.assertEqual(events[-1],('status','copy',control.tr('● másolat ellenőrizve')))
    def test_all_parts_copied_and_verified(self):self.exercise()
    def test_bad_checksum_never_publishes_recording(self):self.exercise(True)
