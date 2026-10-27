TRON CONTROL 1.4.8 — Jenna — Hungarian / English — 2026-10-27

CURRENT VERSION
Three tabs: Robot/mapping, Data/checks, Simulation/Gazebo.
Includes local PCD viewer, raw ROS bag recording/stop/copy, preflight checks,
chunked PCD recording and isolated local simulation master ports.
Gazebo uses ROS port 11321 and Gazebo port 11355. Empty/custom world and
synthetic obstacle world are provided. For TRON1 select its existing local
Gazebo launch file and workspace once; the app does not guess a filename.
Custom .world selection applies to the empty-world launcher, not the robot
launcher's own world. Stop simulation using its dedicated button.
Start ROS and LiDAR, then raw recording, then mapping. Stop/save mapping,
then stop raw recording, then copy both. Raw recording includes required
LiDAR/IMU plus TF and Odometry when published. Splits at 1 GiB, uses a
256 MiB buffer and a 5 GiB minimum-space threshold. Inspect logs for drops.
Bag validation checks readable indexes and sensor counts, not losslessness.
Mapping refuses >5s clock difference, <5 GiB disk or <2 GiB available RAM.
Clock repair is not automatic. Post-power-cycle clock retention is unverified.
PCD viewer supports multiple selected parts; large clouds need laptop RAM.
Local automated tests pass; real ROS/Gazebo/hardware integration remains to
be tested. Begin with 25–30s lab recording, stop/save, copy and inspect.
No autonomous navigation, motor commands, emergency stop, bag playback,
PCD merging or map localization is implemented.
Update: save/stop existing recordings, close old app, extract ZIP and run
bash install.sh inside TRON-Control on Dell. SSH key/settings are retained.
Earlier version notes below are historical; raw recording IS available in 1.4.

TRON CONTROL 1.1 — Jenna — Hungarian / English

INSTALL ON THE DELL (Ubuntu 20.04, ROS Noetic)
Extract the ZIP. Open the TRON-Control folder in a terminal:
    bash install.sh
If tkinter is missing:
    sudo apt install python3-tk
Then run the installer again. Launch TRON Control from Applications.
If the desktop icon opens an editor, right-click it and Allow Launching.
Before updating an existing installation, finish saving and stop its managed
processes, then close the old application and run the new installer.

LANGUAGE
Choose Magyar or English from Nyelv / Language at the top of the window.
Labels, dialogs and app-generated status/log messages change immediately.
The selection is remembered. Raw ROS/SSH output keeps its original language.

CONNECT
Join the robot Wi-Fi. Robot IP: 10.192.1.3.
Set up SSH opens a terminal. Verify the robot host identity and enter the
robot's SSH password. A dedicated unencrypted SSH key is created locally at
~/.ssh/tron_control_ed25519 and its public key is installed on the robot.
The robot password is not stored. Protect your Dell account and private key.

WORKFLOW
Check connection → Start ROS master → Start LiDAR → Start mapping.
Use a unique map name containing English letters, digits, hyphens or
underscores. Refresh status checks both node responses and incoming messages.
Select the saved THOR-lidar-mapping.rviz configuration, then Open live map.
Use camera_init as Fixed Frame and /cloud_registered for PointCloud2.
Stop and save waits for graceful FAST-LIO exit, checks the binary PCD header
and exact file size, then archives it under your chosen name.
Copy saved map transfers to ~/Documents/TRON_maps and compares SHA-256 hashes.
Existing destination files are never overwritten. Transfer shows a busy
indicator rather than a percentage. Stay on robot Wi-Fi during the transfer.
To copy the existing Jenna_test_map.pcd, use button 7 without starting mapping.

LIMITS
The program controls only processes it started. External processes must be
stopped in their own terminal. It sends no robot movement commands.
The ROS programs must already be installed at the paths configured for this
robot. Mapping requires pcd_save_en:true and interval:-1; it does not edit YAML.
An existing scans.pcd blocks a new recording until you preserve it separately.
interval:-1 accumulates recorded points in RAM: use short tests first.
Successful file validation does not establish geometric map quality.
The robot clock is displayed but not changed. Earlier it showed 1970.
Finish saving before closing; closing offers to stop managed LiDAR/ROS.

VALIDATION
Local syntax, shell quoting, binary PCD integrity and language-switch tests
passed. Live Dell GUI/robot integration has not yet been tested remotely.
First use should be supervised. Full campus mapping and autonomous navigation
are outside this version.
Logs: ~/.local/state/tron-control/
Settings: ~/.config/tron-control/settings.json

SEPARATE TERMINALS — VERSION 1.2
Starting ROS, LiDAR or FAST-LIO automatically opens a separate log terminal.
They run concurrently. Reopen a log using its Log button. These are viewing
windows: Ctrl+C or closing one stops the viewer only. Always use Stop and
save in the app for FAST-LIO, rather than closing its log terminal.
Robot terminal opens an additional interactive SSH shell for manual commands.
You can open several shells. Manually started processes are not app-managed.
Enter the password after password: in the Set up SSH terminal. Nothing is
displayed as you type, not even dots or asterisks; press Enter to submit.
Until key setup is complete, Robot terminal may also ask for the password.
Button-based startup requires Set up SSH first. Processes started externally
keep their output in their original terminals; duplicate instances are avoided.

1.4.8 – Single-file baseline test
Saving interval is -1 again. Points accumulate in RAM until graceful
shutdown writes scans.pcd. An interruption may lose unwritten points.
Each run retains its own PCD/<recording> folder and recording.launch.
Original launch/YAML files remain unchanged. Manifest and SHA-256 verified
copy remain available, including support for earlier chunked recordings.
Raw bag recording remains separately controlled on the Data tab.
This change does not establish or automatically fix the distortion cause.
Test briefly at rest, then moving slowly; inspect live and saved clouds.
Before updating, save and stop active processes and close the old app.
Extract the ZIP and run bash install.sh in its TRON-Control folder.
Installation does not modify robot files or earlier recordings.

1.4.8: Sync robot clock / Ora szinkronizalasa: stop LiDAR, mapping and bag first.
Requires SSH key setup and robot sudo password in the terminal.
Uses the Dell clock as reference; verify laptop time first.
One-shot system clock correction, not persistent NTP/RTC configuration.

1.4.8: Confirmed status text is green; pending amber; unverified/stopped grey.

1.4.8 – Live health / Elo allapotfigyeles
Automatic probes after connection: 2.5 s message sampling, approximately
5–10 s refresh when idle. Probes pause during app operations; displayed
status during a long save/copy is the last checked state, not a guarantee.
Green sensor/mapping labels require new messages; missing messages or
unexpected process exit are red. Intentional stops are grey.
Stop LiDAR button targets the known Livox node, refuses active mapping/bag.
Clock sync now displays instructions while its terminal waits for input.
Live proximity tab is READ ONLY. No movement/stop commands are published.
Range is radial from LiDAR center, all directions, ignoring points <0.5m.
A 1.5m amber indication is a diagnostic threshold, NOT a stopping distance.
Floor, body, occlusion, glass and missing points are not resolved; this is
not an obstacle avoidance or safety system. Calibrate frame, ground filter,
footprint and drive interface before adding any motion control.
Hardware/GUI integration testing is still required.

1.4.8: Stop all and save button. Closes managed mapping and bag with normal
validation, then stops Livox, managed ROS master and managed Gazebo.
Save errors or unknown/external recording state abort remaining shutdown.
No SIGKILL. Not a robot motion emergency stop or power-off. External ROS
masters, standalone RViz/viewers, log terminals are not killed.
Unavailable during another operation; finish clock terminal/password first.

1.4.8 – RViz / Gazebo launch review
RViz uses bundled live_mapping.rviz when no custom config is selected.
It requires fresh /cloud_registered and uses its actual header frame_id.
Reset RViz live view clears an old custom selection. Install includes config.
Gazebo world-only buttons explicitly say WITHOUT ROBOT. TRON1 requires a
verified installed robot launch, offered by Find installed Gazebo launches.
Candidates are not guaranteed robot launch entry points; inspect selection.
Custom world selection applies only to world-only mode, not the robot launch.
Fixed log-window title lookup for Gazebo and raw bag recording.
Live GUI/ROS integration remains to be checked on the Dell and robot.
