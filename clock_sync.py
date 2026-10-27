"""Interactive one-shot clock correction. Password is kept only in memory."""
import getpass
import ipaddress
from pathlib import Path
import subprocess
import sys
import time


def sync(ip):
    ipaddress.IPv4Address(ip)
    ssh=['ssh','-T','-i',str(Path.home()/'.ssh/tron_control_ed25519'),
         '-o','BatchMode=yes','-o','ConnectTimeout=8','guest@'+ip]
    # Refuse sensor/mapping/recording processes, including externally started ones.
    guard="if pgrep -f '[l]ivox_ros_driver|[f]astlio_mapping|[r]osbag record' >/dev/null; then echo 'Stop LiDAR, mapping and rosbag before clock sync.' >&2; exit 1; fi; "
    subprocess.run(ssh+[guard+'date -Iseconds'],check=True,timeout=20)
    print('Robot sudo password (not saved). / Robot sudo jelszo (nem taroljuk).')
    password=getpass.getpass('Password: ')
    try:
        # Timestamp is generated AFTER password entry, so typing time is excluded.
        epoch=time.time()
        command=guard+'sudo -S -p "" date -u -s @'+str(epoch)
        result=subprocess.run(ssh+[command],input=password+'\n',text=True,
                              capture_output=True,timeout=30)
    finally:
        password=None
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'Clock update failed')
    print(result.stdout.strip())
    before=time.time()
    remote=subprocess.check_output(ssh+['date +%s.%N'],text=True,timeout=15)
    after=time.time()
    delta=float(remote.strip())-(before+after)/2
    print('Measured offset / Mert elteres: %.3f s; round trip: %.3f s' % (delta,after-before))
    if abs(delta)+(after-before)/2>5:
        raise RuntimeError('Clock agreement within 5 s could not be confirmed. Retry.')
    print('OK: clocks checked. Start LiDAR again. / Ora ellenorizve; indithato a LiDAR.')
    print('One-shot correction; reboot persistence and ongoing NTP sync are not configured.')


if __name__=='__main__':
    try:
        sync(sys.argv[1])
        input('Enter to close / Enter a bezarashoz: ')
    except Exception as exc:
        print('ERROR / HIBA:',exc)
        input('Enter to close / Enter a bezarashoz: ')
        sys.exit(1)
