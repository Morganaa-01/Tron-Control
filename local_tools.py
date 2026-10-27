"""Local-only Gazebo and offline viewer commands; Python 3.8."""
import os
from pathlib import Path
import shlex

SIM_MASTER='http://127.0.0.1:11321'
SIM_GAZEBO='http://127.0.0.1:11355'

def simulation_command(workspace, launch='', world=''):
    workspace=Path(workspace).expanduser().resolve()
    setup=workspace/'devel/setup.bash'
    if not setup.is_file(): setup=workspace/'devel_isolated/setup.bash'
    if launch and not setup.is_file(): raise ValueError('Workspace setup.bash not found')
    if launch:
        target=Path(launch).expanduser().resolve()
        if not target.is_file() or target.suffix!='.launch' or 'gazebo' not in str(target).lower():
            raise ValueError('Choose a Gazebo .launch file')
        args=['roslaunch','-p','11321',str(target)]
    else:
        args=['roslaunch','-p','11321','gazebo_ros','empty_world.launch']
        if world:
            target=Path(world).expanduser().resolve()
            if not target.is_file() or target.suffix!='.world': raise ValueError('Choose a .world file')
            args.append('world_name:='+str(target))
    source='source /opt/ros/noetic/setup.bash && '
    if setup.is_file(): source+='source '+shlex.quote(str(setup))+' && '
    # Reset addresses after workspace setup; no robot shell environment is inherited.
    source+='export ROS_MASTER_URI='+SIM_MASTER+' ROS_IP=127.0.0.1 ROS_HOSTNAME=localhost GAZEBO_MASTER_URI='+SIM_GAZEBO+' ROBOT_TYPE=WF_TRON1A && '
    return source+'exec '+shlex.join(args)

def viewer_command(paths):
    paths=[str(Path(p).expanduser().resolve()) for p in paths]
    if not paths or any(not Path(p).is_file() or Path(p).suffix.lower()!='.pcd' for p in paths):
        raise ValueError('Choose existing .pcd files')
    return ['pcl_viewer']+paths

def gazebo_launch_candidates(workspace):
    """Offer candidates for review, never silently pick a robot launch."""
    import xml.etree.ElementTree as ET
    root=Path(workspace).expanduser()/'src'
    result=[]
    for p in sorted(root.rglob('*.launch')):
        if 'gazebo' not in str(p).lower(): continue
        try: tree=ET.parse(p).getroot()
        except (ET.ParseError,OSError): continue
        if tree.tag=='launch': result.append(str(p.resolve()))
    return result
