# TRON Control

Python/Tkinter desktop application for the Savonia TRON1 robotics project.
Version **1.4.9 — 2026-10-27**. English by default; Hungarian is also available. Existing language preferences are preserved.

## Features

- SSH setup, ROS master and Livox MID-360 startup
- FAST-LIO mapping, single-PCD saving and SHA-256 verified copy
- Live RViz view and raw ROS bag recording
- Robot clock correction and live status monitoring
- Save-first process shutdown and dedicated LiDAR stop
- Local Gazebo launch selection and world-only environments
- Experimental read-only LiDAR proximity display

## Installation

Target: Ubuntu 20.04, ROS Noetic, Python 3.8+, tkinter, OpenSSH tools,
gnome-terminal. Install RViz, Gazebo, PCL viewer and the LimX simulation
workspace separately as needed. Robot workspace paths are project-specific;
review ROOT and SETUP in tron_control.py before use with another setup.

```bash
git clone https://github.com/Morganaa-01/Tron-Control.git
cd Tron-Control
bash install.sh
```

The installer creates a desktop launcher and installs local app files.

## Documentation

- [Magyar útmutató](README_HU.txt)
- [English guide](README_EN.txt)

## Tests

```bash
python3 -m unittest discover -s . -p 'test*.py'
```

Automated tests do not replace hardware and GUI integration checks.
Proximity monitoring does not stop robot motion. Process shutdown is not a
robot emergency stop. Autonomous navigation is not implemented.
Credentials, SSH keys, recordings and private settings are not included.
