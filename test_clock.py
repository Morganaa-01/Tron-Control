import unittest
from unittest.mock import patch,Mock
import clock_sync

class ClockTests(unittest.TestCase):
    def test_password_is_stdin_and_time_checked(self):
        with patch.object(clock_sync.getpass,'getpass',return_value='test-secret'), patch.object(clock_sync.subprocess,'run',return_value=Mock(returncode=0,stdout='done',stderr='')) as run, patch.object(clock_sync.subprocess,'check_output',return_value='101.5'), patch.object(clock_sync.time,'time',side_effect=[100,101,102]):
            clock_sync.sync('10.192.1.3')
            args,kwargs=run.call_args
            self.assertNotIn('test-secret',' '.join(args[0]))
            self.assertEqual(kwargs['input'],'test-secret\n')
            self.assertIn('date -u -s @100',args[0][-1])
    def test_active_sensor_prevents_password_and_mutation(self):
        import subprocess
        with patch.object(clock_sync.subprocess,'run',side_effect=subprocess.CalledProcessError(1,'ssh')) as run, patch.object(clock_sync.getpass,'getpass') as password:
            with self.assertRaises(subprocess.CalledProcessError): clock_sync.sync('10.192.1.3')
            password.assert_not_called()
            self.assertEqual(run.call_count,1)
