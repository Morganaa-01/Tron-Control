"""TRON Control — Ubuntu 20.04 / Python 3.8+, standard library only."""
import base64
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import queue
import re
import shlex
import subprocess
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
APP_VERSION = '1.4.9'
RELEASE_DATE = '2026-10-27'

def status_color(text):
    if text.startswith('!'): return '#c62828'
    if text.startswith('●'): return '#16803c'
    if text.startswith('…'): return '#946200'
    return '#666666'

def version_banner():
    return 'TRON Control ' + APP_VERSION + ' • ' + RELEASE_DATE

ROOT = '/home/guest/catkin_ws/src/fast-lio-mapping_and_localization-sc-qn/third_party/FAST_LIO'
SETUP = '/home/guest/catkin_ws/devel_isolated/setup.bash'
CONFIG = Path.home() / '.config/tron-control/settings.json'
VALIDATE = "\nimport os, json, sys\np=sys.argv[1]\nwith open(p,'rb') as f:\n    h={}\n    for i in range(64):\n        line=f.readline(4096)\n        if not line or len(line)>=4096: raise RuntimeError('Hibas PCD fejlec')\n        s=line.decode('ascii').strip()\n        if not s or s.startswith('#'): continue\n        key, *values=s.split(); h[key]=values\n        if key=='DATA': break\n    else: raise RuntimeError('Nincs DATA sor')\n    offset=f.tell()\nif h.get('DATA')!=['binary']: raise RuntimeError('Csak binary PCD ellenorizheto')\nn=int(h['POINTS'][0]); sizes=list(map(int,h['SIZE']))\ncounts=list(map(int,h.get('COUNT',['1']*len(sizes))))\nif len(sizes)!=len(counts): raise RuntimeError('Hibas mezok')\nexpected=offset+n*sum(a*b for a,b in zip(sizes,counts))\nif n<=0 or os.path.getsize(p)!=expected: raise RuntimeError('Hianyos PCD fajl / hibas meret')\nprint(json.dumps({'bytes':expected,'points':n,'path':p}))\n"


# Remote scripts are encoded by pycmd; user names never become shell code.

# Measures arrival of new messages, not potentially unsynchronized header stamps.
LIVE_HEALTH = r"""
import json,time,math,threading
import rospy,rosgraph
from livox_ros_driver2.msg import CustomMsg
from sensor_msgs.msg import Imu,PointCloud2
rospy.init_node('tron_health_probe',anonymous=True,disable_signals=True)
counts={'lidar':0,'imu':0,'cloud':0}; nearest=[None]; lock=threading.Lock()
def lidar(m):
    ranges=[math.sqrt(p.x*p.x+p.y*p.y+p.z*p.z) for p in m.points if all(math.isfinite(v) for v in (p.x,p.y,p.z)) and p.x*p.x+p.y*p.y+p.z*p.z>=0.25]
    with lock:
        counts['lidar']+=1
        if ranges: nearest[0]=min(ranges) if nearest[0] is None else min(nearest[0],min(ranges))
def count(k):
    def callback(m):
        with lock: counts[k]+=1
    return callback
subs=[rospy.Subscriber('/livox/lidar',CustomMsg,lidar,queue_size=1),rospy.Subscriber('/livox/imu',Imu,count('imu'),queue_size=10),rospy.Subscriber('/cloud_registered',PointCloud2,count('cloud'),queue_size=1)]
time.sleep(2.5)
state=rosgraph.Master('/tron_health_probe').getSystemState()
nodes=sorted(set(n for group in state for topic, names in group for n in names))
with lock: print(json.dumps({'counts':counts,'nearest':nearest[0],'nodes':nodes}))
"""

PREFLIGHT = r"""
import os,sys,time,json,shutil
memory={}
with open('/proc/meminfo') as f:
    for line in f:
        k,v=line.split(':',1); memory[k]=int(v.split()[0])*1024
usage=shutil.disk_usage(sys.argv[1])
print(json.dumps({'epoch':time.time(),'disk_free_GiB':round(usage.free/2**30,2),'memory_available_GiB':round(memory['MemAvailable']/2**30,2)}))
"""
VALIDATE_BAGS = r"""
import os,sys,glob,json,rosbag
folder=sys.argv[1]
if glob.glob(folder+'/*.active'): raise RuntimeError('Recording still active or interrupted: preserve .active files')
files=sorted(glob.glob(folder+'/*.bag'))
if not files: raise RuntimeError('No closed bag files')
entries=[];counts={}
for p in files:
    with rosbag.Bag(p,'r') as b:
        topics=b.get_type_and_topic_info().topics
        for topic,info in topics.items(): counts[topic]=counts.get(topic,0)+info.message_count
        if not topics: raise RuntimeError('Empty bag: '+p)
    entries.append({'path':p,'bytes':os.path.getsize(p)})
if any(counts.get(t,0)==0 for t in ['/livox/lidar','/livox/imu']): raise RuntimeError('Missing LiDAR or IMU messages')
result={'format':'tron-bag-1','files':entries,'topic_messages':counts}
with open(folder+'/manifest.json.tmp','w') as f: json.dump(result,f,indent=2)
os.replace(folder+'/manifest.json.tmp',folder+'/manifest.json')
print(json.dumps(result))
"""

PREPARE_CHUNKS = r"""
import os,sys,glob,json
from xml.sax.saxutils import escape
root,dest=sys.argv[1:3]
if glob.glob(root+'/PCD/scans*.pcd'): raise RuntimeError('Unarchived scans*.pcd exists; preserve it before starting.')
if os.path.lexists(dest): raise RuntimeError('Recording folder already exists')
os.mkdir(dest)
launch=dest+'/recording.launch'
xml='<launch><include file="'+escape(root+'/launch/mapping_mid360.launch')+'"><arg name="rviz" value="false"/></include><param name="/pcd_save/pcd_save_en" type="bool" value="true"/><param name="/pcd_save/interval" type="int" value="-1"/></launch>'
with open(launch,'x') as f: f.write(xml)
print(launch)
"""

FINALIZE_CHUNKS = r"""
import os,sys,glob,json,subprocess
root,dest,validator=sys.argv[1:4]
files=glob.glob(root+'/PCD/scans_*.pcd')
files.sort(key=lambda p:int(os.path.basename(p)[6:-4]))
indices=[int(os.path.basename(p)[6:-4]) for p in files]+[int(os.path.basename(p)[6:-4]) for p in glob.glob(dest+'/scans_*.pcd')]
if indices and sorted(set(indices))!=list(range(1,max(indices)+1)): raise RuntimeError('Missing numbered PCD part; preserve recording')
if os.path.exists(root+'/PCD/scans.pcd'): files.append(root+'/PCD/scans.pcd')
# Include files already archived by an interrupted finalize operation.
archived=glob.glob(dest+'/scans*.pcd')
if not files and not archived: raise RuntimeError('No saved PCD files found')
for p in files+archived:
    subprocess.check_output([sys.executable,'-c',validator,p])
for p in files:
    target=dest+'/'+os.path.basename(p)
    if os.path.exists(target):
        if not os.path.samefile(p,target): raise RuntimeError('Archive collision')
    else: os.link(p,target)
    os.unlink(p)
entries=[]
for p in sorted(glob.glob(dest+'/scans*.pcd')):
    entries.append(json.loads(subprocess.check_output([sys.executable,'-c',validator,p])))
# Read the mode saved with this run; older recordings remain supported.
interval=100
launch=dest+'/recording.launch'
if os.path.isfile(launch):
    import xml.etree.ElementTree as ET
    for param in ET.parse(launch).getroot().findall('param'):
        if param.get('name')=='/pcd_save/interval': interval=int(param.get('value'))
manifest={'format':'tron-recording-1','interval_frames':interval,'files':entries}
with open(dest+'/manifest.json.tmp','w') as f: json.dump(manifest,f,indent=2)
os.replace(dest+'/manifest.json.tmp',dest+'/manifest.json')
print(json.dumps(manifest))
"""

LIST_RECORDING = r"""
import os,sys,json,subprocess
p,validator=sys.argv[1:3]
if os.path.isdir(p):
    with open(p+'/manifest.json') as f: m=json.load(f)
    names=[os.path.basename(x['path']) for x in m['files']]
    if not names or len(names)!=len(set(names)): raise RuntimeError('Invalid manifest')
    if any(not __import__('re').fullmatch(r'scans(?:_[0-9]+)?\.pcd',n) for n in names): raise RuntimeError('Invalid PCD name')
    paths=[p+'/'+n for n in names]
else: paths=[p]
print(json.dumps([json.loads(subprocess.check_output([sys.executable,'-c',validator,x])) for x in paths]))
"""

def pycmd(script, *args):
    encoded = base64.b64encode(script.encode()).decode()
    code = 'import base64;exec(base64.b64decode(%r))' % encoded
    return 'python3 -c ' + shlex.quote(code) + ''.join((' ' + shlex.quote(str(a)) for a in args))

def environment(ip):
    return 'source ' + shlex.quote(SETUP) + ' && export ROS_MASTER_URI=' + shlex.quote('http://' + ip + ':11311') + ' ROS_IP=' + shlex.quote(ip) + ' && unset ROS_HOSTNAME && '


LANGUAGE = 'en'
TRANSLATIONS = {'TRON Control • Jenna': 'TRON Control • Jenna', 'Kapcsolódás → LiDAR → térképezés → mentés → másolás': 'Connect → LiDAR → mapping → save → copy', '⚿  SSH beállítása': '⚿  Set up SSH', '↻  Állapot frissítése': '↻  Refresh status', '▤  Térképmappa': '▤  Map folder', 'Robot IP:': 'Robot IP:', '①  Kapcsolat ellenőrzése': '①  Check connection', 'SSH és robotóra ellenőrzése.': 'Check SSH and the robot clock.', '②  ROS központ indítása': '②  Start ROS master', 'A LiDAR külön ROS központja: 10.192.1.3:11311.': 'Separate LiDAR ROS master on the selected robot IP.', '③  LiDAR indítása': '③  Start LiDAR', 'Livox MID-360 • pontfelhő és IMU.': 'Livox MID-360 • point cloud and IMU.', '④  Térképezés indítása': '④  Start mapping', 'FAST-LIO • minden felvétel külön mappába kerül.': 'FAST-LIO • each new recording gets a separate file.', '⑤  Élő térkép megnyitása': '⑤  Open live map', 'RViz a Dell gépen; a mentett beállítás kiválasztható.': 'RViz on the Dell; choose a saved configuration.', '⑥  Leállítás és mentés': '⑥  Stop and save', 'Csak az itt indított FAST-LIO-t állítja le szabályosan.': 'Gracefully stops only FAST-LIO started here.', '⑦  Mentett térkép másolása': '⑦  Copy saved map', 'Ellenőrzött másolat a Dellre, SHA-256 összehasonlítással.': 'Copy to the Dell with SHA-256 verification.', '— nincs ellenőrizve': '— not checked', 'Új térkép neve:': 'New map name:', 'Másolás célja:': 'Copy destination:', 'Tallózás…': 'Browse…', 'RViz-beállítás…': 'RViz configuration…', 'Mentés: egy PCD a leállításkor; addig RAM-ban gyűlik. Először rövid próba.': 'Saving: recorded points stay in memory until mapping stops. Start with a short test.', 'Napló • a zöld állapotot a ROS ellenőrzése igazolja, nem pusztán a gombnyomás.': 'Log • ROS checks confirm the running status; clicking a button alone does not.', 'Első használat: SSH beállítása, majd Kapcsolat ellenőrzése. A jelszót nem tároljuk.\nA már meglévő Jenna_test_map.pcd másolásához a 7. gombot válaszd.\n': 'First use: Set up SSH, then Check connection. Your password is not stored.\nTo copy the existing Jenna_test_map.pcd, use button 7.\n', 'HIBA: ': 'ERROR: ', 'Folyamatban': 'In progress', 'Várd meg az aktuális művelet végét.': 'Wait for the current operation to finish.', 'IP-cím': 'IP address', 'Érvényes IPv4-címet adj meg.': 'Enter a valid IPv4 address.', 'SSH-parancs sikertelen': 'SSH command failed', '… ellenőrzés': '… checking', 'A ROS workspace nem található.': 'ROS workspace was not found.', 'Robot elérhető. Robotóra: ': 'Robot reachable. Robot clock: ', '● SSH elérhető': '● SSH reachable', '● ROS központ elérhető': '● ROS master reachable', '○ nem elérhető': '○ unreachable', '● node válaszol': '● node responding', '○ nem fut': '○ not running', ': üzenet érkezik.\n': ': messages received.\n', ': 5 másodperc alatt nincs üzenet.\n': ': no messages within 5 seconds.\n', 'Térképnév': 'Map name', 'Angol betűk, számok, kötőjel és aláhúzás; legfeljebb 80 karakter.': 'Use English letters, digits, hyphens or underscores; up to 80 characters.', '● már fut': '● already running', '● már fut (külső)': '● running externally', 'Előbb indítsd el a LiDAR-t.': 'Start LiDAR first.', '… indul': '… starting', 'A folyamat kilépett; részletek a naplóban.': 'The process exited; see the log for details.', '● működik (itt indult)': '● running (started here)', 'Az indulás még nincs igazolva. Használd az Állapot frissítése gombot.': 'Startup has not been confirmed yet. Click Refresh status.', '○ leállt (%s)': '○ stopped (%s)', 'Térképezés': 'Mapping', 'Csak az ebből az ablakból indított térképezést tudom leállítani. A korábbi mentés másolásához használd a 7. gombot.': 'Only mapping started from this window can be stopped here. Use button 7 to copy an existing map.', '… leállítás / írás': '… stopping / writing', 'A leállítás még tart. Nem küldtem kényszerleállítást. Nézd meg a naplót; ne zárd be az ablakot.': 'Shutdown is still in progress. No forced stop was sent. Check the log and keep this window open.', 'Az SSH/roslaunch hibával lépett ki; a scans.pcd-t külön ellenőrizni kell.': 'SSH/roslaunch exited with an error; scans.pcd needs a separate check.', '● méret ellenőrizve': '● file size verified', 'Mentve saját néven: ': 'Saved with a unique name: ', '\nPCD-ellenőrzés: ': '\nPCD verification: ', 'Meglévő térkép': 'Existing map', 'Roboton lévő felvételmappa vagy régi fájl neve (.pcd nélkül):': 'File name on robot (without .pcd):', 'Név': 'Name', 'Csak angol betű, szám, kötőjel és aláhúzás.': 'Use only English letters, digits, hyphens and underscores.', 'Már létezik a célfájl: ': 'Destination already exists: ', '… másolás; várj': '… copying; please wait', 'Másolás indul: %.2f GB. Maradj a robot Wi-Fi-jén.\n': 'Copying %.2f GB. Stay connected to the robot Wi-Fi.\n', 'Másolási hiba': 'Copy failed', 'Eltérő fájlméret': 'File size mismatch', '… SHA-256 ellenőrzés': '… checking SHA-256', 'Eltérő SHA-256 ellenőrzőösszeg': 'SHA-256 checksum mismatch', '● másolat ellenőrizve': '● copy verified', 'Kész, azonos SHA-256: ': 'Done, matching SHA-256: ', 'RViz beállítás': 'RViz configuration', '↗ megnyitás kérve': '↗ launch requested', 'Még futnak folyamatok': 'Processes are still running', 'Az ablakot nyitva tartom. Előbb mentsd a térképet. A ROS/LiDAR folyamatok leállításához használd a lenti lehetőséget.': 'This window will stay open. Save the map first. Use the next option to stop ROS/LiDAR processes.', 'Munkamenet vége': 'End session', 'Leállítsam az itt indított LiDAR-t és ROS központot? A külső folyamatokhoz nem nyúlok.': 'Stop LiDAR and ROS master started here? External processes will be left running.', 'Az itt indított folyamatok leálltak. Most bezárhatod az ablakot.\n': 'Processes started here have stopped. You can close this window now.\n', 'Nyelv / Language:': 'Nyelv / Language:'}
TRANSLATIONS.update({'▣  Robot terminál': '▣  Robot terminal', '▣ Napló': '▣ Log', 'Jelszó: az SSH beállítása gomb termináljában. Gépeléskor nem látszanak karakterek.': 'Password: enter it in the Set up SSH terminal. Typed characters are not displayed.', 'A ROS, LiDAR és FAST-LIO egyszerre fut. A külön naplóterminálok bezárása nem állítja le őket.': 'ROS, LiDAR and FAST-LIO run concurrently. Closing their log terminals does not stop them.', 'Ehhez a folyamathoz még nincs saját napló. Ha külső terminálban fut, ott követhető.': 'No managed log yet. If started externally, follow it in its original terminal.', 'Naplóterminál nem nyitható meg: ': 'Could not open log terminal: ', 'NAPLÓABLAK — csak megfigyelés. A leállítást és mentést a vezérlőablakban végezd.\n': 'LOG WINDOW — viewing only. Stop and save from the control window.\n', 'Robot terminál: a kézi parancsok nem kerülnek az alkalmazás folyamatkezelésébe.\n': 'Robot terminal: manual commands are not managed by the application.\n', 'Folyamat kilépési kódja: ': 'Process exit code: '})
REVERSE = {v:k for k,v in TRANSLATIONS.items()}
TRANSLATIONS.update({
'Mentés: egy PCD a leállításkor; addig RAM-ban gyűlik. Először rövid próba.': 'Saving: one PCD when mapping stops; points accumulate in RAM. Start with a short test.',
'FAST-LIO • minden felvétel külön mappába kerül.': 'FAST-LIO • each recording gets a separate folder.',
'Roboton lévő felvételmappa vagy régi fájl neve (.pcd nélkül):': 'Recording folder or legacy file name on robot (without .pcd):',
'Előbb fejezd be az előző felvétel mentését.': 'Finish saving the previous recording first.'})

REVERSE = {v:k for k,v in TRANSLATIONS.items()}

TRANSLATIONS.update({'Robot • térképezés': 'Robot • mapping', 'Adatok • ellenőrzés': 'Data • checks', 'Szimuláció • Gazebo': 'Simulation • Gazebo', 'Adatok és indulási ellenőrzés': 'Data and preflight checks', '▣ Mentett pontfelhő megnyitása': '▣ Open saved point cloud', '✓ Indulási ellenőrzés': '✓ Preflight checks', '● Nyers rögzítés indítása': '● Start raw recording', '■ Nyers rögzítés lezárása': '■ Stop raw recording', '⇩ Nyers felvétel másolása': '⇩ Copy raw recording', 'Nyers adatok: LiDAR + IMU, opcionálisan TF és Odometry. 1 GiB-os részek.\nA térképezés és a nyers rögzítés külön indul és külön áll le.\nA műveletek eredménye a Robot fül naplójában látható.': 'Raw data: LiDAR + IMU, plus TF and Odometry when available. 1 GiB parts.\nMapping and raw recording start and stop separately.\nResults appear in the Robot tab log.', 'SZIMULÁCIÓ • csak a Dell gépen': 'SIMULATION • on the Dell only', 'Külön ROS: 127.0.0.1:11321 • Gazebo: 11355\nAz üres világ robot nélkül is használható. A TRON1 modellhez válaszd ki a már telepített Gazebo launch fájlt.': 'Separate ROS: 127.0.0.1:11321 • Gazebo: 11355\nUse an empty world without the robot. For the TRON1 model, select its installed Gazebo launch file.', 'Helyi workspace:': 'Local workspace:', 'TRON1 Gazebo indítófájl:': 'TRON1 Gazebo launch file:', 'Indítófájl kiválasztása': 'Choose launch file', '▷ Üres vagy kiválasztott világ': '▷ Empty or selected world', '▣ TRON1 szimuláció indítása': '▣ Start TRON1 simulation', '▤ Világfájl kiválasztása': '▤ Choose world file', '■ Szimuláció leállítása': '■ Stop simulation', 'Indulási ellenőrzés: ': 'Preflight checks: ', 'A robot és a laptop órája több mint 5 másodperccel eltér.': 'Robot and laptop clocks differ by more than 5 seconds.', 'Az óra és az erőforrásadatok ellenőrizve. A részleteket nézd meg a naplóban.\n': 'Clock and resource data checked. See the log for details.\n', 'A pontfelhőnéző hiányzik. A Dell termináljában: sudo apt install pcl-tools': 'Point cloud viewer is missing. In the Dell terminal: sudo apt install pcl-tools', 'A szimuláció már fut.': 'Simulation is already running.', 'Szimuláció indítása kérve; külön helyi ROS: 11321. Ellenőrizd a Gazebo ablakát.\n': 'Simulation launch requested; separate local ROS: 11321. Check the Gazebo window.\n', 'Szimuláció leállítása kérve.\n': 'Simulation stop requested.\n', 'Előbb zárd le az előző nyers felvételt.': 'Close the previous raw recording first.', 'Már fut nyers adatrögzítő.': 'A raw recorder is already running.', 'A nyers rögzítő hibával lépett ki; őrizd meg a fájlokat.': 'Raw recorder exited with an error; preserve the files.', 'Nyers felvétel lezárva: ': 'Raw recording closed: ', 'A roboton lévő nyers felvételmappa neve:': 'Raw recording folder name on robot:', 'Kevés szabad tárhely vagy memória. Futtasd az indulási ellenőrzést.': 'Low free disk space or memory. Run preflight checks.', 'Előbb állítsd le a szimulációt a Gazebo fülön.': 'Stop simulation in the Gazebo tab first.'})
REVERSE = {v:k for k,v in TRANSLATIONS.items()}

TRANSLATIONS['▦ Akadályos tesztvilág']='▦ Obstacle test world'
REVERSE = {v:k for k,v in TRANSLATIONS.items()}

def tr(text):
    canonical = REVERSE.get(text, text)
    return TRANSLATIONS.get(canonical, canonical) if LANGUAGE == 'en' else canonical

def translate_existing(text, language):
    # Single-pass replacement avoids re-translating overlapping phrases.
    table = TRANSLATIONS if language == 'en' else REVERSE
    table = {k:v for k,v in table.items() if k != v}
    # The formatted process status includes a numeric exit code.
    table.update({'○ leállt (':'○ stopped ('} if language == 'en' else {'○ stopped (':'○ leállt ('})
    pattern = re.compile('|'.join(re.escape(k) for k in sorted(table, key=len, reverse=True)))
    return pattern.sub(lambda m:table[m.group(0)], text)

TRANSLATIONS.update({
    'Óra szinkronizálása':'Sync robot clock',
    'Előbb állítsd le a LiDAR-t, térképezést és nyers rögzítést.':'Stop LiDAR, mapping and raw recording first.',
    'Az órák egyezése nem igazolható; próbáld újra.':'Clock agreement could not be confirmed; retry.',
    'Óra ellenőrizve. A LiDAR újraindítható.\n':'Clock checked. LiDAR can be restarted.\n',
})
REVERSE = {v:k for k,v in TRANSLATIONS.items()}

TRANSLATIONS.update({'LiDAR leállítása': 'Stop LiDAR', 'Élő közelségfigyelő': 'Live proximity monitor', 'CSAK JELZÉS – nem állítja meg a robotot': 'INDICATION ONLY – does not stop the robot', 'Élő figyelés indítása': 'Start live monitoring', '● friss adat érkezik': '● fresh data received', '○ szándékosan leállítva': '○ intentionally stopped', '! nincs friss adat / leállt': '! no fresh data / stopped', '! ellenőrzés sikertelen / állapot ismeretlen': '! check failed / state unknown', '! Nincs érvényes LiDAR-mérés': '! No valid LiDAR measurement', 'Legközelebbi mért felület: %.2f m (szenzorközépponttól)': 'Nearest measured surface: %.2f m (from sensor center)', '… leállítás': '… stopping', 'leállt (%s)': 'stopped (%s)', 'Előbb állítsd le a térképezést és a nyers rögzítést.': 'Stop mapping and raw recording first.', 'A LiDAR leállása nem igazolható.': 'LiDAR shutdown could not be confirmed.', 'LiDAR-középponttól mért távolság, minden irányban. A padló és a robot teste is mérés lehet. A 0,5 méternél közelebbi pontokat kihagyja.': 'Distance from LiDAR center in all directions. Floor and robot body may appear. Points closer than 0.5 m are excluded.', 'Ez még nem akadálymentességi igazolás. Irány, talajszűrés, robotméret és fékút kalibrálása szükséges.': 'This does not establish a clear path. Direction, ground filtering, robot dimensions and stopping distance need calibration.'})
REVERSE = {v:k for k,v in TRANSLATIONS.items()}

TRANSLATIONS.update({'■ Minden folyamat leállítása és mentés':'■ Stop all processes and save'})
REVERSE = {v:k for k,v in TRANSLATIONS.items()}

TRANSLATIONS.update({'▷ Világ indítása ROBOT NÉLKÜL': '▷ Start world WITHOUT ROBOT', '▦ Akadályos világ ROBOT NÉLKÜL': '▦ Obstacle world WITHOUT ROBOT', 'Telepített Gazebo-indítók keresése': 'Find installed Gazebo launches', 'Nem találtam Gazebo launch fájlt. Ellenőrizd a workspace útvonalát.': 'No Gazebo launch found. Check the workspace path.', 'Válaszd ki a TRON1 indítójának sorszámát:': 'Select the number of the TRON1 launch:', 'RViz alapnézet visszaállítása': 'Reset RViz live view', 'A következő RViz indítás a TRON1 élő pontfelhőnézetét használja.\n': 'Next RViz launch will use the TRON1 live point cloud view.\n', 'Nincs friss térképpontfelhő. Ellenőrizd a kapcsolatot, majd indítsd el a LiDAR-t és a térképezést.': 'No fresh mapped cloud. Check connection, then start LiDAR and mapping.', 'A TRON1 modellhez a TRON1 szimuláció indítása gombot használd. A modell saját launch fájlja határozza meg a világát.': 'Use Start TRON1 simulation for the model. Its launch file determines the world.'})
REVERSE={v:k for k,v in TRANSLATIONS.items()}

class App:

    def __init__(self, root):
        self.root = root
        root.title(version_banner() + ' • Jenna • HU / EN')
        root.geometry('1200x800')
        root.minsize(1120, 740)
        self.events = queue.Queue()
        self.processes = {}
        self.process_logs = {}
        self.terminal_language = 'hu'
        self.busy = False
        self.stopping = False
        self.expected_stops = set()
        self.monitor_enabled = False
        self.monitor_busy = False
        self.seen_live = set()
        self.saved = None
        self.pending = None
        self.bag_pending = None
        self.bag_saved = None
        self.sim_process = None
        self.status = {}
        self.buttons = {}
        data = {}
        try:
            data = json.loads(CONFIG.read_text())
        except (OSError, ValueError):
            pass
        global LANGUAGE
        LANGUAGE = data.get('language', 'en')
        if LANGUAGE not in ('hu', 'en'): LANGUAGE = 'en'
        self.language = tk.StringVar(value='Magyar' if LANGUAGE == 'hu' else 'English')
        self.ip = tk.StringVar(value=data.get('ip', '10.192.1.3'))
        self.name = tk.StringVar(value='Jenna_test_' + time.strftime('%Y%m%d_%H%M%S'))
        self.destination = tk.StringVar(value=data.get('destination', str(Path.home() / 'Documents/TRON_maps')))
        self.sim_workspace = tk.StringVar(value=data.get('sim_workspace', str(Path.home()/'limx_ws')))
        self.sim_launch = tk.StringVar(value=data.get('sim_launch',''))
        self.sim_world = tk.StringVar(value='')
        self.rviz_config = tk.StringVar(value=data.get('rviz', ''))
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background='#eef3f8')
        style.configure('TLabel', background='#eef3f8', font=('DejaVu Sans', 10))
        style.configure('TButton', font=('DejaVu Sans', 10), padding=8)
        style.configure('Title.TLabel', font=('DejaVu Sans', 23, 'bold'), foreground='#173b66')
        style.configure('Sub.TLabel', foreground='#4b6278')
        ttk.Label(root, text=version_banner(), font=('DejaVu Sans', 11, 'bold'), padding=(16, 8)).pack(anchor='w')
        tabs=ttk.Notebook(root)
        tabs.pack(fill='both',expand=True)
        outer = ttk.Frame(tabs, padding=16)
        tools = ttk.Frame(tabs,padding=20)
        simulation = ttk.Frame(tabs,padding=20)
        tabs.add(outer,text=tr('Robot • térképezés'))
        tabs.add(tools,text=tr('Adatok • ellenőrzés'))
        tabs.add(simulation,text=tr('Szimuláció • Gazebo'))
        self.tabs=tabs
        self.tab_labels=['Robot • térképezés','Adatok • ellenőrzés','Szimuláció • Gazebo']
        ttk.Label(outer, text='◉  TRON Control', style='Title.TLabel').pack(anchor='w')
        ttk.Label(outer, text=tr('Kapcsolódás → LiDAR → térképezés → mentés → másolás'), style='Sub.TLabel').pack(anchor='w', pady=(0, 12))
        settings = ttk.Frame(outer)
        settings.pack(fill='x')
        language_row = ttk.Frame(outer)
        language_row.pack(fill='x', pady=(6, 0))
        ttk.Button(language_row, text=tr('Óra szinkronizálása'), command=self.sync_clock).pack(side='right')
        stopbar=ttk.Frame(outer);stopbar.pack(fill='x',pady=5)
        ttk.Button(stopbar,text=tr('■ Minden folyamat leállítása és mentés'),command=self.stop_all).pack(side='left')
        ttk.Label(language_row, text='Nyelv / Language:').pack(side='left')
        picker = ttk.Combobox(language_row, textvariable=self.language, values=['Magyar', 'English'], state='readonly', width=12)
        picker.pack(side='left', padx=8)
        picker.bind('<<ComboboxSelected>>', self.change_language)
        ttk.Label(settings, text='Robot IP:').pack(side='left')
        ttk.Entry(settings, textvariable=self.ip, width=16).pack(side='left', padx=8)
        ttk.Button(settings, text=tr('⚿  SSH beállítása'), command=self.setup_ssh).pack(side='left')
        ttk.Button(settings, text=tr('↻  Állapot frissítése'), command=self.refresh).pack(side='left', padx=8)
        ttk.Button(settings, text=tr('▣  Robot terminál'), command=self.robot_terminal).pack(side='left', padx=4)
        ttk.Button(language_row,text=tr('LiDAR leállítása'),command=self.stop_lidar).pack(side='right',padx=8)
        ttk.Button(settings, text=tr('▤  Térképmappa'), command=self.open_folder).pack(side='right')
        ttk.Label(outer, text=tr('Jelszó: az SSH beállítása gomb termináljában. Gépeléskor nem látszanak karakterek.'), style='Sub.TLabel').pack(anchor='w', pady=(8,0))
        ttk.Label(outer, text=tr('A ROS, LiDAR és FAST-LIO egyszerre fut. A külön naplóterminálok bezárása nem állítja le őket.'), style='Sub.TLabel').pack(anchor='w')
        grid = ttk.Frame(outer)
        grid.pack(fill='x', pady=12)
        rows = [('connection', tr('①  Kapcsolat ellenőrzése'), tr('SSH és robotóra ellenőrzése.'), self.check), ('core', tr('②  ROS központ indítása'), tr('A LiDAR külön ROS központja: 10.192.1.3:11311.'), lambda: self.start('core')), ('lidar', tr('③  LiDAR indítása'), tr('Livox MID-360 • pontfelhő és IMU.'), lambda: self.start('lidar')), ('mapping', tr('④  Térképezés indítása'), tr('FAST-LIO • minden felvétel külön mappába kerül.'), lambda: self.start('mapping')), ('rviz', tr('⑤  Élő térkép megnyitása'), tr('RViz a Dell gépen; a mentett beállítás kiválasztható.'), self.rviz), ('save', tr('⑥  Leállítás és mentés'), tr('Csak az itt indított FAST-LIO-t állítja le szabályosan.'), self.stop_mapping), ('copy', tr('⑦  Mentett térkép másolása'), tr('Ellenőrzött másolat a Dellre, SHA-256 összehasonlítással.'), self.copy_map)]
        for i, (key, title, desc, action) in enumerate(rows):
            btn = ttk.Button(grid, text=title, command=action, width=31)
            btn.grid(row=i, column=0, sticky='ew', pady=3)
            self.buttons[key] = btn
            ttk.Label(grid, text=desc).grid(row=i, column=1, sticky='w', padx=12)
            var = tk.StringVar(value=tr('— nincs ellenőrizve'))
            self.status[key] = var
            label = ttk.Label(grid, textvariable=var, width=25, foreground='#666666')
            label.grid(row=i, column=2, sticky='w')
            var.trace_add('write', lambda *args, v=var, w=label: w.configure(foreground=status_color(v.get())))
            if key in ('core', 'lidar', 'mapping'):
                ttk.Button(grid, text=tr('▣ Napló'), command=lambda k=key: self.open_process_terminal(k)).grid(row=i, column=3, padx=4)
        grid.columnconfigure(1, weight=1)
        files = ttk.Frame(outer)
        files.pack(fill='x')
        ttk.Label(files, text=tr('Új térkép neve:')).grid(row=0, column=0, sticky='w')
        ttk.Entry(files, textvariable=self.name, width=40).grid(row=0, column=1, sticky='ew', padx=8, pady=4)
        ttk.Label(files, text=tr('Másolás célja:')).grid(row=1, column=0, sticky='w')
        ttk.Entry(files, textvariable=self.destination).grid(row=1, column=1, sticky='ew', padx=8)
        ttk.Button(files, text=tr('Tallózás…'), command=self.choose_folder).grid(row=1, column=2)
        ttk.Button(files, text=tr('RViz-beállítás…'), command=self.choose_rviz).grid(row=0, column=2)
        files.columnconfigure(1, weight=1)
        ttk.Button(outer,text=tr('RViz alapnézet visszaállítása'),command=self.reset_rviz).pack(anchor='e')
        ttk.Label(outer, text=tr('Mentés: egy PCD a leállításkor; addig RAM-ban gyűlik. Először rövid próba.'), foreground='#8b5615').pack(anchor='w', pady=(10, 4))
        self.operation=tk.StringVar(value='')
        ttk.Label(outer,textvariable=self.operation,foreground='#946200').pack(anchor='w')
        self.progress = ttk.Progressbar(outer, mode='indeterminate')
        self.progress.pack(fill='x', pady=4)
        ttk.Label(outer, text=tr('Napló • a zöld állapotot a ROS ellenőrzése igazolja, nem pusztán a gombnyomás.')).pack(anchor='w')
        self.log = tk.Text(outer, height=10, bg='#122338', fg='#d7e8f8', font=('DejaVu Sans Mono', 9), wrap='word')
        self.log.pack(fill='both', expand=True, pady=5)
        self.log_dir = Path.home() / '.local/state/tron-control'
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.logfile = self.log_dir / ('session_' + time.strftime('%Y%m%d_%H%M%S') + '.log')
        self.emit('log', tr('Első használat: SSH beállítása, majd Kapcsolat ellenőrzése. A jelszót nem tároljuk.\nA már meglévő Jenna_test_map.pcd másolásához a 7. gombot válaszd.\n'))
        ttk.Label(tools,text=tr('Adatok és indulási ellenőrzés'),style='Title.TLabel').pack(anchor='w',pady=8)
        for label,action in [('▣ Mentett pontfelhő megnyitása',self.open_pcd),('✓ Indulási ellenőrzés',self.preflight),('● Nyers rögzítés indítása',self.start_bag),('■ Nyers rögzítés lezárása',self.stop_bag),('⇩ Nyers felvétel másolása',self.copy_bag)]:
            ttk.Button(tools,text=tr(label),command=action,width=40).pack(anchor='w',pady=6)
        self.status['bag']=tk.StringVar(value=tr('— nincs ellenőrizve'))
        bag_label=ttk.Label(tools,textvariable=self.status['bag'],foreground='#666666')
        bag_label.pack(anchor='w')
        self.status['bag'].trace_add('write', lambda *args: bag_label.configure(foreground=status_color(self.status['bag'].get())))
        ttk.Button(tools,text=tr('▣ Napló'),command=lambda:self.open_process_terminal('bag')).pack(anchor='w',pady=8)
        ttk.Label(tools,text=tr('Nyers adatok: LiDAR + IMU, opcionálisan TF és Odometry. 1 GiB-os részek.\nA térképezés és a nyers rögzítés külön indul és külön áll le.\nA műveletek eredménye a Robot fül naplójában látható.'),wraplength=950).pack(anchor='w',pady=12)
        ttk.Label(simulation,text=tr('SZIMULÁCIÓ • csak a Dell gépen'),style='Title.TLabel').pack(anchor='w',pady=10)
        ttk.Label(simulation,text=tr('Külön ROS: 127.0.0.1:11321 • Gazebo: 11355\nAz üres világ robot nélkül is használható. A TRON1 modellhez válaszd ki a már telepített Gazebo launch fájlt.'),wraplength=950).pack(anchor='w',pady=10)
        ttk.Label(simulation,text=tr('Helyi workspace:')).pack(anchor='w')
        ttk.Entry(simulation,textvariable=self.sim_workspace,width=85).pack(anchor='w',pady=5)
        ttk.Label(simulation,text=tr('TRON1 Gazebo indítófájl:')).pack(anchor='w')
        ttk.Entry(simulation,textvariable=self.sim_launch,width=85).pack(anchor='w',pady=5)
        ttk.Button(simulation,text=tr('Telepített Gazebo-indítók keresése'),command=self.find_sim_launch).pack(anchor='w',pady=5)
        ttk.Button(simulation,text=tr('Indítófájl kiválasztása'),command=self.pick_sim_launch).pack(anchor='w',pady=5)
        for label,action in [('▷ Világ indítása ROBOT NÉLKÜL',lambda:self.start_simulation(False)),('▣ TRON1 szimuláció indítása',lambda:self.start_simulation(True)),('▤ Világfájl kiválasztása',self.pick_world),('▦ Akadályos világ ROBOT NÉLKÜL',self.training_world),('■ Szimuláció leállítása',self.stop_simulation)]:
            ttk.Button(simulation,text=tr(label),command=action,width=40).pack(anchor='w',pady=5)
        ttk.Label(simulation,text=tr('A TRON1 modellhez a TRON1 szimuláció indítása gombot használd. A modell saját launch fájlja határozza meg a világát.'),wraplength=950).pack(anchor='w',pady=5)
        ttk.Label(simulation,textvariable=self.sim_world,wraplength=950).pack(anchor='w')
        proximity=ttk.Frame(tabs,padding=12)
        tabs.add(proximity,text=tr('Élő közelségfigyelő'))
        self.proximity_text=tk.StringVar(value=tr('— nincs ellenőrizve'))
        ttk.Label(proximity,text=tr('CSAK JELZÉS – nem állítja meg a robotot'),foreground='#c62828').pack(anchor='w',pady=10)
        ttk.Label(proximity,text=tr('LiDAR-középponttól mért távolság, minden irányban. A padló és a robot teste is mérés lehet. A 0,5 méternél közelebbi pontokat kihagyja.'),wraplength=900).pack(anchor='w',pady=10)
        self.proximity_label=ttk.Label(proximity,textvariable=self.proximity_text)
        self.proximity_label.pack(anchor='w',pady=10)
        ttk.Button(proximity,text=tr('Élő figyelés indítása'),command=self.enable_monitor).pack(anchor='w',pady=8)
        ttk.Label(proximity,text=tr('Ez még nem akadálymentességi igazolás. Irány, talajszűrés, robotméret és fékút kalibrálása szükséges.'),wraplength=900).pack(anchor='w')
        self.root.after(5000,self.monitor_tick)
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.pump()

    def change_language(self, event=None):
        global LANGUAGE
        LANGUAGE = 'en' if self.language.get() == 'English' else 'hu'
        def update(widget):
            try:
                value = widget.cget('text')
                if value: widget.configure(text=translate_existing(str(value), LANGUAGE))
            except tk.TclError:
                pass
            for child in widget.winfo_children(): update(child)
        update(self.root)
        for i,label in enumerate(self.tab_labels): self.tabs.tab(i,text=tr(label))
        for value in self.status.values(): value.set(translate_existing(value.get(), LANGUAGE))
        # Translate app-generated historical log phrases; raw ROS/SSH output stays original.
        old = self.log.get('1.0', 'end-1c')
        self.log.delete('1.0', 'end')
        self.log.insert('1.0', translate_existing(old, LANGUAGE))
        self.log.see('end')
        self.persist()

    def emit(self, *e):
        self.events.put(e)

    def pump(self):
        try:
            while True:
                e = self.events.get_nowait()
                if e[0] == 'log':
                    self.log.insert('end', translate_existing(e[1], LANGUAGE))
                    self.log.see('end')
                    with self.logfile.open('a') as f:
                        f.write(e[1])
                elif e[0] == 'status':
                    self.status[e[1]].set(translate_existing(e[2], LANGUAGE))
                    if e[1]=='connection' and e[2].startswith('●'): self.monitor_enabled=True
                elif e[0] == 'operation':
                    self.operation.set(e[1])
                elif e[0] == 'proximity':
                    self.proximity_text.set(e[1])
                    self.proximity_label.configure(foreground=e[2])
                elif e[0] == 'done':
                    self.operation.set('')
                    self.busy = False
                    self.progress.stop()
                elif e[0] == 'error':
                    messagebox.showerror('TRON Control', translate_existing(e[1], LANGUAGE))
                elif e[0] == 'saved':
                    self.saved = e[1]
                    self.name.set(Path(e[1]).stem)
        except queue.Empty:
            pass
        self.root.after(100, self.pump)

    def host(self):
        ip = str(ipaddress.IPv4Address(self.ip.get().strip()))
        return ip

    def persist(self):
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(json.dumps({'ip': self.ip.get(), 'destination': self.destination.get(), 'rviz': self.rviz_config.get(), 'language': LANGUAGE, 'sim_workspace':self.sim_workspace.get(), 'sim_launch':self.sim_launch.get()}))

    def ssh_args(self, ip, cmd, tty=False):
        return ['ssh', '-i', str(Path.home() / '.ssh/tron_control_ed25519'), '-tt' if tty else '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=7', '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=3', 'guest@' + ip, 'bash -lc ' + shlex.quote(cmd)]

    def remote(self, ip, cmd, timeout=20):
        r = subprocess.run(self.ssh_args(ip, cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        if r.returncode:
            raise RuntimeError(r.stderr.strip() or r.stdout.strip() or tr('SSH-parancs sikertelen'))
        return r.stdout.strip()

    def task(self, fn):
        if self.busy:
            messagebox.showinfo(tr('Folyamatban'), tr('Várd meg az aktuális művelet végét.'))
            return
        try:
            ip = self.host()
            self.persist()
            self.terminal_language = LANGUAGE
        except ValueError:
            messagebox.showerror(tr('IP-cím'), tr('Érvényes IPv4-címet adj meg.'))
            return
        self.busy = True
        self.operation.set(tr('Folyamatban'))
        self.progress.start()

        def run():
            try:
                fn(ip)
            except Exception as ex:
                self.emit('log', tr('HIBA: ') + str(ex) + '\n')
                self.emit('error', str(ex))
            finally:
                self.emit('done')
        threading.Thread(target=run, daemon=True).start()

    def setup_ssh(self):
        try:
            ip = self.host()
            self.persist()
            script = Path(__file__).with_name('setup_ssh.sh')
            subprocess.Popen(['gnome-terminal', '--', 'bash', str(script), ip, LANGUAGE])
        except Exception as ex:
            messagebox.showerror('SSH', str(ex))

    def open_process_terminal(self, key):
        path = self.process_logs.get(key)
        if not path:
            messagebox.showinfo('TRON Control', tr('Ehhez a folyamathoz még nincs saját napló. Ha külső terminálban fut, ott követhető.'))
            return
        try:
            title = {'core':'TRON • ROS master', 'lidar':'TRON • Livox LiDAR', 'mapping':'TRON • FAST-LIO','bag':'TRON1 • ROS bag','simulation':'TRON1 • Gazebo'}[key]
            subprocess.Popen(['gnome-terminal', '--window', '--title='+title, '--', 'tail', '-n', '+1', '-F', str(path)])
        except OSError as ex:
            self.emit('log', tr('Naplóterminál nem nyitható meg: ') + str(ex) + '\n')

    def enable_monitor(self):
        self.host()
        self.monitor_enabled=True

    def stop_all(self):
        if self.busy:
            messagebox.showinfo('TRON Control',tr('Várd meg az aktuális művelet végét.'));return
        def work(ip):
            self.monitor_enabled=False
            # Fail closed: never stop sensors/master if saving could not finish.
            for key,pending,finish in [('mapping',self.pending,self.finish_mapping),('bag',self.bag_pending,self.finish_bag)]:
                p=self.processes.get(key)
                if p and p.poll() is None and not pending:
                    raise RuntimeError('Unknown recording state: preserve processes and inspect logs.')
                if pending:
                    self.emit('operation',tr('… leállítás / írás')+': '+key)
                    finish(ip)
            # Externally started recorders cannot be finalized by this instance.
            for node in ['/laserMapping','/tron_control_recorder']:
                try: alive=self.node(ip,node)
                except Exception:
                    raise RuntimeError('Cannot verify robot state; sensors/master were not stopped.')
                if alive: raise RuntimeError('External recording still active: '+node)
            self.emit('operation','LiDAR / ROS / Gazebo leállítása / stopping')
            if self.node(ip,'/livox_lidar_publisher2'):
                self.expected_stops.add('lidar')
                self.remote(ip,environment(ip)+'rosnode kill /livox_lidar_publisher2',timeout=20)
                for _ in range(20):
                    if not self.node(ip,'/livox_lidar_publisher2'): break
                    time.sleep(0.5)
                else: raise RuntimeError('LiDAR shutdown could not be confirmed')
            for key in ['lidar','core']:
                p=self.processes.get(key)
                if p and p.poll() is None:
                    self.expected_stops.add(key)
                    p.stdin.write(b'\x03');p.stdin.flush();p.wait(timeout=30)
                self.emit('status',key,tr('○ szándékosan leállítva') if p or key=='lidar' else tr('— nincs ellenőrizve'))
            self.stop_simulation()
            if self.sim_process: self.sim_process.wait(timeout=30)
            self.emit('log','Leállítás kész. A mentett fájlok megmaradtak. A külső ROS központot nem állítottam le. / Stopped; saved files preserved; external ROS master untouched.\n')
        self.task(work)

    def stop_lidar(self):
        def work(ip):
            for name in ['/laserMapping','/tron_control_recorder']:
                if self.node(ip,name): raise RuntimeError(tr('Előbb állítsd le a térképezést és a nyers rögzítést.'))
            self.expected_stops.add('lidar')
            self.emit('status','lidar',tr('… leállítás'))
            # Target only the known LiDAR ROS node, including an externally started instance.
            self.remote(ip,environment(ip)+'rosnode kill /livox_lidar_publisher2',timeout=20)
            for _ in range(10):
                if not self.node(ip,'/livox_lidar_publisher2'):
                    self.emit('status','lidar',tr('○ szándékosan leállítva'));return
                time.sleep(0.5)
            raise RuntimeError(tr('A LiDAR leállása nem igazolható.'))
        self.task(work)

    def monitor_tick(self):
        self.root.after(5000,self.monitor_tick)
        if not self.monitor_enabled or self.busy or self.monitor_busy: return
        try: ip=self.host()
        except ValueError: return
        self.monitor_busy=True
        def work():
            try:
                health=json.loads(self.remote(ip,environment(ip)+pycmd(LIVE_HEALTH),timeout=15))
                self.emit('status','connection',tr('● SSH elérhető'))
                self.emit('status','core',tr('● ROS központ elérhető'))
                counts=health['counts']
                for key,topic,node in [('lidar','lidar','/livox_lidar_publisher2'),('mapping','cloud','/laserMapping')]:
                    fresh=counts[topic]>0 and (key!='lidar' or counts['imu']>0)
                    alive=node in health['nodes']
                    if fresh and alive:
                        self.seen_live.add(key)
                        text=tr('● friss adat érkezik')
                    elif key in self.expected_stops:
                        text=tr('○ szándékosan leállítva')
                    elif alive or key in self.seen_live:
                        text=tr('! nincs friss adat / leállt')
                    else: text=tr('○ nem fut')
                    self.emit('status',key,text)
                bag_alive='/tron_control_recorder' in health['nodes']
                if bag_alive: self.seen_live.add('bag')
                bag_text=tr('● node válaszol') if bag_alive else (tr('! nincs friss adat / leállt') if 'bag' in self.seen_live and 'bag' not in self.expected_stops else tr('○ nem fut'))
                self.emit('status','bag',bag_text)
                distance=health['nearest']
                if not counts['lidar'] or distance is None:
                    self.emit('proximity',tr('! Nincs érvényes LiDAR-mérés'),'#c62828')
                else:
                    # Neutral text is deliberately never a green permission to move.
                    self.emit('proximity',tr('Legközelebbi mért felület: %.2f m (szenzorközépponttól)') % distance,'#946200' if distance<1.5 else '#333333')
            except Exception:
                for key in ['connection','core','lidar','mapping','bag']:
                    self.emit('status',key,tr('! ellenőrzés sikertelen / állapot ismeretlen'))
                self.emit('proximity',tr('! Nincs érvényes LiDAR-mérés'),'#c62828')
            finally: self.monitor_busy=False
        threading.Thread(target=work,daemon=True).start()

    def sync_clock(self):
        def work(ip):
            for key in ['lidar','mapping','bag']:
                process=self.processes.get(key)
                if process is not None and process.poll() is None:
                    raise RuntimeError(tr('Előbb állítsd le a LiDAR-t, térképezést és nyers rögzítést.'))
            script=Path(__file__).with_name('clock_sync.py')
            self.emit('operation', 'Óraszinkron: a terminálban add meg a jelszót, majd a végén nyomj Entert. / Clock sync: enter password, then press Enter to close.')
            subprocess.run(['gnome-terminal','--wait','--window',
                            '--title=TRON clock sync','--','python3',str(script),ip],check=True)
            before=time.time()
            epoch=float(self.remote(ip,'date +%s.%N').strip())
            after=time.time()
            if abs(epoch-(before+after)/2)+(after-before)/2>5:
                raise RuntimeError(tr('Az órák egyezése nem igazolható; próbáld újra.'))
            self.emit('log',tr('Óra ellenőrizve. A LiDAR újraindítható.\n'))
        self.task(work)

    def robot_terminal(self):
        try:
            ip = self.host()
            # Interactive SSH: if the dedicated key is not set up, SSH asks for
            # the password in this terminal, never in a stored GUI text field.
            args = self.ssh_args(ip, environment(ip) + 'exec bash -i', tty=True)
            args = ['BatchMode=no' if value == 'BatchMode=yes' else value for value in args]
            subprocess.Popen(['gnome-terminal', '--window', '--title=TRON • SSH', '--'] + args)
            self.emit('log', tr('Robot terminál: a kézi parancsok nem kerülnek az alkalmazás folyamatkezelésébe.\n'))
        except Exception as ex:
            messagebox.showerror('SSH', str(ex))

    def node(self, ip, name):
        script = "import rosnode;print('YES' if rosnode.rosnode_ping(%r,max_count=1,verbose=False) else 'NO')" % name
        return self.remote(ip, environment(ip) + pycmd(script), timeout=15).splitlines()[-1] == 'YES'

    def master(self, ip):
        script = "import xmlrpc.client; r=xmlrpc.client.ServerProxy('http://%s:11311').getUri('/tron_control'); assert r[0]==1; print(r[2])" % ip
        self.remote(ip, pycmd(script), timeout=10)

    def check(self):

        def work(ip):
            self.emit('status', 'connection', tr('… ellenőrzés'))
            out = self.remote(ip, 'date -Iseconds; test -f ' + shlex.quote(SETUP) + ' && echo WORKSPACE_OK')
            if 'WORKSPACE_OK' not in out:
                raise RuntimeError(tr('A ROS workspace nem található.'))
            self.emit('log', tr('Robot elérhető. Robotóra: ') + out.splitlines()[0] + '\n')
            self.emit('status', 'connection', tr('● SSH elérhető'))
        self.task(work)

    def refresh(self):

        def work(ip):
            self.remote(ip, 'true')
            self.emit('status', 'connection', tr('● SSH elérhető'))
            try:
                self.master(ip)
                self.emit('status', 'core', tr('● ROS központ elérhető'))
            except Exception:
                self.emit('status', 'core', tr('○ nem elérhető'))
                return
            for key, name in [('lidar', '/livox_lidar_publisher2'), ('mapping', '/laserMapping'), ('bag','/tron_control_recorder')]:
                alive = self.node(ip, name)
                self.emit('status', key, tr('● node válaszol') if alive else tr('○ nem fut'))
            for topic in ['/livox/lidar', '/livox/imu', '/cloud_registered']:
                try:
                    self.remote(ip, environment(ip) + 'timeout 5s rostopic echo -n 1 --noarr ' + topic + ' >/dev/null', timeout=12)
                    self.emit('log', topic + tr(': üzenet érkezik.\n'))
                except Exception:
                    self.emit('log', topic + tr(': 5 másodperc alatt nincs üzenet.\n'))
        self.task(work)

    def start(self, key):
        if key in self.processes and self.processes[key].poll() is None:
            return
        filename = self.name.get().strip()
        if key == 'mapping' and (not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,79}', filename)):
            messagebox.showerror(tr('Térképnév'), tr('Angol betűk, számok, kötőjel és aláhúzás; legfeljebb 80 karakter.'))
            return

        def work(ip):
            self.remote(ip, 'true')
            self.emit('status', 'connection', tr('● SSH elérhető'))
            if key != 'core':
                self.master(ip)
            if key == 'core':
                try:
                    self.master(ip)
                    self.emit('status', 'core', tr('● már fut'))
                    return
                except Exception:
                    pass
            else:
                target = '/livox_lidar_publisher2' if key == 'lidar' else '/laserMapping'
                if self.node(ip, target):
                    self.emit('status', key, tr('● már fut (külső)'))
                    return
            if key == 'mapping':
                before=time.time()
                health=json.loads(self.remote(ip,pycmd(PREFLIGHT,ROOT)))
                if abs(health['epoch']-(before+time.time())/2)>5: raise RuntimeError(tr('A robot és a laptop órája több mint 5 másodperccel eltér.'))
                if health['disk_free_GiB']<5 or health['memory_available_GiB']<2: raise RuntimeError(tr('Kevés szabad tárhely vagy memória. Futtasd az indulási ellenőrzést.'))
                self.remote(ip,environment(ip)+pycmd("import rospy; assert not rospy.get_param('/use_sim_time',False), 'Robot ROS uses simulated time'"))
                if not self.node(ip, '/livox_lidar_publisher2'):
                    raise RuntimeError(tr('Előbb indítsd el a LiDAR-t.'))
                for topic in ['/livox/lidar', '/livox/imu']:
                    self.remote(ip, environment(ip) + 'timeout 5s rostopic echo -n 1 --noarr ' + topic + ' >/dev/null', timeout=12)
                if self.pending:
                    raise RuntimeError(tr('Előbb fejezd be az előző felvétel mentését.'))
                dest = ROOT + '/PCD/' + filename
                launch = self.remote(ip, pycmd(PREPARE_CHUNKS, ROOT, dest)).strip()
                self.pending = (ip, dest)
                self.saved = None
            cmd = {'core': 'exec roscore', 'lidar': 'exec roslaunch livox_ros_driver2 msg_MID360.launch', 'mapping': 'exec roslaunch ' + shlex.quote(launch) if key == 'mapping' else ''}[key]
            self.expected_stops.discard(key)
            p = subprocess.Popen(self.ssh_args(ip, environment(ip) + cmd, tty=True), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
            self.processes[key] = p
            logfile = self.log_dir / (key + '_' + time.strftime('%Y%m%d_%H%M%S') + '.log')
            logfile.write_text(tr('NAPLÓABLAK — csak megfigyelés. A leállítást és mentést a vezérlőablakban végezd.\n'))
            self.process_logs[key] = logfile
            self.open_process_terminal(key)
            self.emit('status', key, tr('… indul'))
            threading.Thread(target=self.read_process, args=(key, p), daemon=True).start()
            for _ in range(20):
                if p.poll() is not None:
                    raise RuntimeError(tr('A folyamat kilépett; részletek a naplóban.'))
                try:
                    if key == 'core':
                        self.master(ip)
                        alive = True
                    else:
                        alive = self.node(ip, '/livox_lidar_publisher2' if key == 'lidar' else '/laserMapping')
                    if alive:
                        self.emit('status', key, tr('● működik (itt indult)'))
                        return
                except Exception:
                    pass
                time.sleep(1)
            raise RuntimeError(tr('Az indulás még nincs igazolva. Használd az Állapot frissítése gombot.'))
        self.task(work)

    def read_process(self, key, p):
        while True:
            chunk = p.stdout.read(2048)
            if not chunk:
                break
            text = chunk.decode('utf-8', 'replace')
            with self.process_logs[key].open('a') as output: output.write(text)
            self.emit('log', '[' + key + '] ' + text)
        rc = p.wait()
        with self.process_logs[key].open('a') as output: output.write('\n' + tr('Folyamat kilépési kódja: ') + str(rc) + '\n')
        expected=key in self.expected_stops
        self.emit('status', key, ('○ ' if expected else '! ') + tr('leállt (%s)') % rc)

    def stop_mapping(self):
        p = self.processes.get('mapping')
        if not p or not self.pending:
            messagebox.showinfo(tr('Térképezés'), tr('Csak az ebből az ablakból indított térképezést tudom leállítani. A korábbi mentés másolásához használd a 7. gombot.'))
            return
        ip, dest = self.pending

        self.task(self.finish_mapping)

    def finish_mapping(self, _):
        p=self.processes['mapping']
        ip,dest=self.pending
        self.emit('status', 'save', tr('… leállítás / írás'))
        if p.poll() is None:
            self.expected_stops.add('mapping')
            p.stdin.write(b'\x03')
            p.stdin.flush()
        try:
            p.wait(timeout=300)
        except subprocess.TimeoutExpired:
            raise RuntimeError(tr('A leállítás még tart. Nem küldtem kényszerleállítást. Nézd meg a naplót; ne zárd be az ablakot.'))
        if p.returncode != 0:
            raise RuntimeError(tr('Az SSH/roslaunch hibával lépett ki; a scans.pcd-t külön ellenőrizni kell.'))
        details = self.remote(ip, pycmd(FINALIZE_CHUNKS, ROOT, dest, VALIDATE), timeout=300)
        self.emit('saved', dest)
        self.pending = None
        self.emit('status', 'save', tr('● méret ellenőrizve'))
        self.emit('log', tr('Mentve saját néven: ') + dest + tr('\nPCD-ellenőrzés: ') + details + '\n')

    def copy_map(self, chosen_override=None, kind="pcd"):
        name = self.name.get().strip()
        chosen = chosen_override or self.saved
        if not chosen:
            name = tk.simpledialog.askstring(tr('Meglévő térkép'), tr('Roboton lévő felvételmappa vagy régi fájl neve (.pcd nélkül):'), initialvalue='Jenna_test_map', parent=self.root)
            if name is None:
                return
            if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,79}', name):
                messagebox.showerror(tr('Név'), tr('Csak angol betű, szám, kötőjel és aláhúzás.'))
                return
            chosen = ROOT + '/PCD/' + name
        folder = Path(self.destination.get()).expanduser()

        def work(ip):
            resolved = self.remote(ip, pycmd("import os,sys; p=sys.argv[1]; print(p if os.path.exists(p) else p+'.pcd')", chosen)).strip()
            if kind == 'bag':
                entries=json.loads(self.remote(ip,environment(ip)+pycmd(VALIDATE_BAGS,resolved),timeout=300))['files']
            else:
                entries = json.loads(self.remote(ip, pycmd(LIST_RECORDING, resolved, VALIDATE), timeout=300))
            folder.mkdir(parents=True, exist_ok=True)
            is_recording = not resolved.endswith('.pcd')
            final = folder / Path(resolved).name
            if final.exists(): raise RuntimeError(tr('Már létezik a célfájl: ') + str(final))
            import tempfile, shutil
            output = Path(tempfile.mkdtemp(prefix='.tron-copy-', dir=str(folder))) if is_recording else folder
            try:
                for meta in entries:
                    chosen_file = meta['path']
                    dest = output / Path(chosen_file).name
                    if dest.exists():
                        raise RuntimeError(tr('Már létezik a célfájl: ') + str(dest))
                    import tempfile
                    fd, tmp = tempfile.mkstemp(prefix=dest.name + '.', suffix='.part', dir=str(output))
                    os.close(fd)
                    tmp = Path(tmp)
                    self.emit('status', 'copy', tr('… másolás; várj'))
                    self.emit('log', tr('Másolás indul: %.2f GB. Maradj a robot Wi-Fi-jén.\n') % (meta['bytes'] / 1000000000.0))
                    try:
                        result = subprocess.run(['scp', '-i', str(Path.home() / '.ssh/tron_control_ed25519'), '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=7', '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=3', 'guest@' + ip + ':' + chosen_file, str(tmp)], capture_output=True, text=True)
                        if result.returncode:
                            raise RuntimeError(result.stderr or tr('Másolási hiba'))
                        if tmp.stat().st_size != meta['bytes']:
                            raise RuntimeError(tr('Eltérő fájlméret'))
                        self.emit('status', 'copy', tr('… SHA-256 ellenőrzés'))
                        remote_hash = self.remote(ip, 'sha256sum ' + shlex.quote(chosen_file), timeout=300).split()[0]
                        digest = hashlib.sha256()
                        with tmp.open('rb') as f:
                            for block in iter(lambda: f.read(1024 * 1024), b''):
                                digest.update(block)
                        if digest.hexdigest() != remote_hash:
                            raise RuntimeError(tr('Eltérő SHA-256 ellenőrzőösszeg'))
                        os.link(str(tmp), str(dest))
                        tmp.unlink()
                        self.emit('log', tr('Kész, azonos SHA-256: ') + str(dest) + '\n')
                    finally:
                        if tmp.exists():
                            tmp.unlink()
                if is_recording:
                    (output / 'manifest.json').write_text(json.dumps({'format':'tron-bag-1' if kind=='bag' else 'tron-recording-1','files':entries},indent=2))
                    # mkdir reserves the public name; partial transfers never appear complete.
                    final.mkdir()
                    try:
                        for item in output.iterdir(): os.link(str(item), str(final/item.name))
                    except Exception:
                        shutil.rmtree(final)
                        raise
                self.emit('status', 'copy', tr('● másolat ellenőrizve'))
            finally:
                if is_recording: shutil.rmtree(output)
        self.task(work)

    def preflight(self):
        def work(ip):
            before=time.time()
            data=json.loads(self.remote(ip, pycmd(PREFLIGHT, ROOT)))
            data['clock_difference_seconds']=round(data['epoch']-(before+time.time())/2,2)
            self.emit('log', tr('Indulási ellenőrzés: ') + json.dumps(data,indent=2)+'\n')
            self.master(ip)
            for topic in ['/livox/lidar','/livox/imu']:
                try:
                    self.remote(ip,environment(ip)+'timeout 5s rostopic echo -n 1 --noarr '+topic+' >/dev/null',timeout=12)
                    self.emit('log',topic+tr(': üzenet érkezik.\n'))
                except Exception: self.emit('log',topic+tr(': 5 másodperc alatt nincs üzenet.\n'))
            if abs(data['clock_difference_seconds'])>5:
                raise RuntimeError(tr('A robot és a laptop órája több mint 5 másodperccel eltér.'))
            self.emit('log',tr('Az óra és az erőforrásadatok ellenőrizve. A részleteket nézd meg a naplóban.\n'))
        self.task(work)

    def open_pcd(self):
        import shutil
        from local_tools import viewer_command
        paths=filedialog.askopenfilenames(initialdir=self.destination.get(),filetypes=[('PCD','*.pcd')])
        if not paths: return
        if not shutil.which('pcl_viewer'):
            messagebox.showinfo('PCL Viewer',tr('A pontfelhőnéző hiányzik. A Dell termináljában: sudo apt install pcl-tools'))
            return
        try: subprocess.Popen(viewer_command(paths))
        except Exception as ex: messagebox.showerror('PCL Viewer',str(ex))

    def find_sim_launch(self):
        from local_tools import gazebo_launch_candidates
        from tkinter import simpledialog
        candidates=gazebo_launch_candidates(self.sim_workspace.get())
        if not candidates:
            messagebox.showinfo('Gazebo',tr('Nem találtam Gazebo launch fájlt. Ellenőrizd a workspace útvonalát.'));return
        root=Path(self.sim_workspace.get()).expanduser().resolve()
        labels=['%d. %s' % (i+1,str(Path(p).relative_to(root))) for i,p in enumerate(candidates)]
        selection=simpledialog.askinteger('Gazebo',tr('Válaszd ki a TRON1 indítójának sorszámát:')+'\n\n'+'\n'.join(labels),minvalue=1,maxvalue=len(candidates),parent=self.root)
        if selection:
            self.sim_launch.set(candidates[selection-1]);self.persist()

    def pick_sim_launch(self):
        path=filedialog.askopenfilename(initialdir=str(Path(self.sim_workspace.get()).expanduser()/'src'),filetypes=[('Gazebo launch','*.launch')])
        if path: self.sim_launch.set(path);self.persist()

    def training_world(self):
        self.sim_world.set(str(Path(__file__).with_name('training.world')))
        self.start_simulation(False)

    def pick_world(self):
        path=filedialog.askopenfilename(filetypes=[('Gazebo world','*.world')])
        if path: self.sim_world.set(path)

    def start_simulation(self, robot=False):
        from local_tools import simulation_command
        if self.sim_process and self.sim_process.poll() is None:
            messagebox.showinfo('Gazebo',tr('A szimuláció már fut.'));return
        try:
            launch=self.sim_launch.get() if robot else ''
            if robot and not launch: self.pick_sim_launch();launch=self.sim_launch.get()
            if robot and not launch: return
            cmd=simulation_command(self.sim_workspace.get(),launch,self.sim_world.get() if not robot else '')
            logfile=self.log_dir/('simulation_'+time.strftime('%Y%m%d_%H%M%S')+'.log')
            import os
            with logfile.open('wb') as output:
                self.sim_process=subprocess.Popen(['bash','-c',cmd],stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
            self.process_logs['simulation']=logfile
            self.open_process_terminal('simulation')
            self.emit('log',tr('Szimuláció indítása kérve; külön helyi ROS: 11321. Ellenőrizd a Gazebo ablakát.\n'))
        except Exception as ex: messagebox.showerror('Gazebo',str(ex))

    def stop_simulation(self):
        p=self.sim_process
        if not p or p.poll() is not None: return
        import signal
        os.killpg(p.pid,signal.SIGINT)
        self.emit('log',tr('Szimuláció leállítása kérve.\n'))

    def start_bag(self):
        if self.processes.get('bag') and self.processes['bag'].poll() is None: return
        name=self.name.get().strip()
        if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,79}',name):
            messagebox.showerror('ROS bag',tr('Csak angol betű, szám, kötőjel és aláhúzás.'));return
        def work(ip):
            if self.bag_pending: raise RuntimeError(tr('Előbb zárd le az előző nyers felvételt.'))
            self.master(ip)
            before=time.time()
            health=json.loads(self.remote(ip,pycmd(PREFLIGHT,ROOT)))
            if abs(health['epoch']-(before+time.time())/2)>5: raise RuntimeError(tr('A robot és a laptop órája több mint 5 másodperccel eltér.'))
            if health['disk_free_GiB']<5: raise RuntimeError(tr('Kevés szabad tárhely vagy memória. Futtasd az indulási ellenőrzést.'))
            if self.node(ip,'/tron_control_recorder'): raise RuntimeError(tr('Már fut nyers adatrögzítő.'))
            for topic in ['/livox/lidar','/livox/imu']:
                self.remote(ip,environment(ip)+'timeout 5s rostopic echo -n 1 --noarr '+topic+' >/dev/null',timeout=12)
            dest=ROOT+'/bags/'+name+'_'+time.strftime('%Y%m%d_%H%M%S')
            self.remote(ip,pycmd("import os,sys; os.makedirs(os.path.dirname(sys.argv[1]),exist_ok=True);os.mkdir(sys.argv[1])",dest))
            self.bag_pending=(ip,dest)
            self.bag_saved=None
            cmd='exec rosbag record --split --size=1024 --buffsize=256 --min-space=5G -O '+shlex.quote(dest+'/raw.bag')+' /livox/lidar /livox/imu /tf /tf_static /Odometry __name:=tron_control_recorder'
            p=subprocess.Popen(self.ssh_args(ip,environment(ip)+cmd,tty=True),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=0)
            self.processes['bag']=p
            logfile=self.log_dir/('bag_'+time.strftime('%Y%m%d_%H%M%S')+'.log');logfile.touch()
            self.process_logs['bag']=logfile;self.open_process_terminal('bag')
            threading.Thread(target=self.read_process,args=('bag',p),daemon=True).start()
            for _ in range(15):
                if p.poll() is not None: raise RuntimeError(tr('A folyamat kilépett; részletek a naplóban.'))
                if self.node(ip,'/tron_control_recorder'):
                    self.emit('status','bag',tr('● node válaszol'));return
                time.sleep(1)
            raise RuntimeError(tr('Az indulás még nincs igazolva. Használd az Állapot frissítése gombot.'))
        self.task(work)

    def stop_bag(self):
        p=self.processes.get('bag')
        if not p or not self.bag_pending: return
        ip,dest=self.bag_pending
        self.task(self.finish_bag)

    def finish_bag(self, _):
        p=self.processes['bag']
        ip,dest=self.bag_pending
        self.expected_stops.add('bag')
        if p.poll() is None: p.stdin.write(b'\x03');p.stdin.flush()
        p.wait(timeout=120)
        if p.returncode!=0: raise RuntimeError(tr('A nyers rögzítő hibával lépett ki; őrizd meg a fájlokat.'))
        info=self.remote(ip,environment(ip)+pycmd(VALIDATE_BAGS,dest),timeout=300)
        self.bag_saved=dest;self.bag_pending=None
        self.emit('status','bag',tr('● méret ellenőrizve'))
        self.emit('log',tr('Nyers felvétel lezárva: ')+dest+'\n'+info+'\n')

    def copy_bag(self):
        chosen=self.bag_saved
        if not chosen:
            name=tk.simpledialog.askstring('ROS bag',tr('A roboton lévő nyers felvételmappa neve:'),parent=self.root)
            if not name: return
            if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,119}',name): return
            chosen=ROOT+'/bags/'+name
        self.copy_map(chosen_override=chosen,kind='bag')

    def choose_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.destination.set(folder)

    def choose_rviz(self):
        path = filedialog.askopenfilename(filetypes=[(tr('RViz beállítás'), '*.rviz')])
        if path:
            self.rviz_config.set(path)
            self.persist()

    def open_folder(self):
        folder = Path(self.destination.get()).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(['xdg-open', str(folder)])

    def reset_rviz(self):
        self.rviz_config.set('')
        self.persist()
        self.emit('log',tr('A következő RViz indítás a TRON1 élő pontfelhőnézetét használja.\n'))

    def rviz(self):
        custom=self.rviz_config.get().strip()
        def work(ip):
            self.master(ip)
            # Verify a new mapped message before opening a mapping-specific view.
            probe="import rospy,json;from sensor_msgs.msg import PointCloud2;rospy.init_node('tron_rviz_check',anonymous=True,disable_signals=True);m=rospy.wait_for_message('/cloud_registered',PointCloud2,timeout=6);print(json.dumps({'frame':m.header.frame_id}))"
            try: frame=json.loads(self.remote(ip,environment(ip)+pycmd(probe),timeout=15))['frame']
            except Exception:
                raise RuntimeError(tr('Nincs friss térképpontfelhő. Ellenőrizd a kapcsolatot, majd indítsd el a LiDAR-t és a térképezést.'))
            if not frame: raise RuntimeError('Point cloud frame_id is empty')
            if custom:
                config=Path(custom).expanduser()
                if not config.is_file(): raise RuntimeError('Selected RViz configuration does not exist: '+str(config))
            else:
                template=Path(__file__).with_name('live_mapping.rviz').read_text()
                config=self.log_dir/'live_mapping.rviz'
                config.write_text(template.replace('__FRAME__',json.dumps(frame)))
            out=subprocess.check_output(['ip','-j','route','get',ip],text=True)
            laptop=json.loads(out)[0]['prefsrc'];ipaddress.IPv4Address(laptop)
            cmd='source /opt/ros/noetic/setup.bash && export ROS_MASTER_URI='+shlex.quote('http://'+ip+':11311')+' ROS_IP='+shlex.quote(laptop)+' && unset ROS_HOSTNAME && exec '+shlex.join(['rviz','-d',str(config)])
            subprocess.Popen(['gnome-terminal','--window','--title=TRON1 RViz','--','bash','-lc',cmd])
            self.emit('status','rviz',tr('↗ megnyitás kérve'))
            self.emit('log','RViz: '+str(config)+'; /cloud_registered; frame='+frame+'\n')
        self.task(work)

    def close(self):
        if self.sim_process and self.sim_process.poll() is None:
            messagebox.showinfo('Gazebo',tr('Előbb állítsd le a szimulációt a Gazebo fülön.'));return
        if self.busy or any((p.poll() is None for p in self.processes.values())):
            messagebox.showinfo(tr('Még futnak folyamatok'), tr('Az ablakot nyitva tartom. Előbb mentsd a térképet. A ROS/LiDAR folyamatok leállításához használd a lenti lehetőséget.'))
            self.shutdown_dialog()
            return
        self.persist()
        self.root.destroy()

    def shutdown_dialog(self):
        if self.busy:
            return
        if any(self.processes.get(k) and self.processes[k].poll() is None for k in ['mapping','bag']):
            return
        if not messagebox.askyesno(tr('Munkamenet vége'), tr('Leállítsam az itt indított LiDAR-t és ROS központot? A külső folyamatokhoz nem nyúlok.')):
            return

        def work(ip):
            for key in ['lidar', 'core']:
                p = self.processes.get(key)
                if p and p.poll() is None:
                    self.expected_stops.add(key)
                    p.stdin.write(b'\x03')
                    p.stdin.flush()
                    p.wait(timeout=30)
            self.emit('log', tr('Az itt indított folyamatok leálltak. Most bezárhatod az ablakot.\n'))
        self.task(work)
if __name__ == '__main__':
    import tkinter.simpledialog
    root = tk.Tk()
    App(root)
    root.mainloop()
