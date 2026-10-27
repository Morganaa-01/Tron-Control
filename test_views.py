import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import tron_control as c
from local_tools import gazebo_launch_candidates

class ViewTests(unittest.TestCase):
    def test_default_rviz_has_actual_frame_and_cloud(self):
        with tempfile.TemporaryDirectory() as d:
            app=c.App.__new__(c.App);app.rviz_config=Mock();app.rviz_config.get.return_value=''
            app.log_dir=Path(d);app.task=lambda fn:fn('10.192.1.3')
            app.master=Mock();app.remote=Mock(return_value=json.dumps({'frame':'camera_init'}));app.emit=Mock()
            with patch.object(c.subprocess,'check_output',return_value='[{"prefsrc":"10.192.1.214"}]'),patch.object(c.subprocess,'Popen') as launch:
                app.rviz()
                cmd=launch.call_args.args[0][-1]
                self.assertIn('rviz -d',cmd)
                config=(Path(d)/'live_mapping.rviz').read_text()
                self.assertIn('Fixed Frame: "camera_init"',config)
                self.assertIn('Topic: /cloud_registered',config)
    def test_rviz_no_cloud_opens_no_window(self):
        app=c.App.__new__(c.App);app.rviz_config=Mock();app.rviz_config.get.return_value=''
        app.task=lambda fn:fn('10.192.1.3');app.master=Mock();app.remote=Mock(side_effect=RuntimeError('timeout'))
        with patch.object(c.subprocess,'Popen') as launch:
            with self.assertRaises(RuntimeError):app.rviz()
            launch.assert_not_called()
    def test_discovery_offers_only_valid_launch_xml(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)/'src/tron1_gazebo/launch';folder.mkdir(parents=True)
            (folder/'robot.launch').write_text('<launch/>')
            (folder/'broken.launch').write_text('bad xml')
            self.assertEqual(gazebo_launch_candidates(d),[str((folder/'robot.launch').resolve())])
