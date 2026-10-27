import unittest
import tron_control as c
from unittest.mock import Mock

class HealthTests(unittest.TestCase):
    def test_status_colors(self):
        self.assertEqual(c.status_color('! sensor lost'),'#c62828')
        self.assertEqual(c.status_color('● fresh data'),'#16803c')
        self.assertEqual(c.status_color('○ intentionally stopped'),'#666666')
    def test_lidar_stop_refuses_active_mapping(self):
        app=c.App.__new__(c.App)
        app.task=lambda fn:fn('10.192.1.3')
        app.node=Mock(return_value=True)
        app.remote=Mock()
        with self.assertRaises(RuntimeError):app.stop_lidar()
        app.remote.assert_not_called()
    def test_probe_is_read_only(self):
        compile(c.LIVE_HEALTH,'probe','exec')
        self.assertNotIn('rospy.Publisher',c.LIVE_HEALTH)
        self.assertNotIn('cmd_vel',c.LIVE_HEALTH)
