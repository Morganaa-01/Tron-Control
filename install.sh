#!/usr/bin/env bash
set -euo pipefail
source_dir=$(cd -- "$(dirname -- "$0")" && pwd)
app_dir="$HOME/.local/share/tron-control"
if ! python3 -c 'import tkinter' 2>/dev/null; then
    printf 'A grafikus ablakhoz python3-tk szükséges. Telepítés:\n'
    printf 'sudo apt install python3-tk\n'
    exit 1
fi
for binary in ssh scp ssh-copy-id ssh-keygen gnome-terminal; do
    if ! command -v "$binary" >/dev/null; then
        printf 'Hiányzó program: %s\n' "$binary"
        exit 1
    fi
done
mkdir -p "$app_dir" "$HOME/.local/share/applications"
cp "$source_dir/tron_control.py" "$source_dir/local_tools.py" "$source_dir/clock_sync.py" "$source_dir/training.world" "$source_dir/live_mapping.rviz" "$source_dir/setup_ssh.sh" "$source_dir/tron.svg" "$app_dir/"
chmod +x "$app_dir/tron_control.py" "$app_dir/setup_ssh.sh"
python3 - "$app_dir" <<'PY'
import os,shlex,subprocess,sys
from pathlib import Path
p=Path(sys.argv[1]); home=Path.home()
# Desktop Exec follows freedesktop quoting, not shell syntax.
def dq(s): return '"'+str(s).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$')+'"'
text='[Desktop Entry]\nVersion=1.0\nType=Application\nName=TRON Control\nComment=LiDAR, mapping and recording\nExec=python3 '+dq(p/'tron_control.py')+'\nIcon='+str(p/'tron.svg')+'\nTerminal=false\nCategories=Science;Education;\n'
launcher=home/'.local/share/applications/tron-control.desktop'
launcher.write_text(text); launcher.chmod(0o755)
try: desktop=Path(subprocess.check_output(['xdg-user-dir','DESKTOP'],text=True).strip())
except (OSError,subprocess.CalledProcessError): desktop=home/'Desktop'
if desktop!=home:
    desktop.mkdir(parents=True,exist_ok=True)
    target=desktop/'TRON-Control.desktop'; target.write_text(text); target.chmod(0o755)
    subprocess.run(['gio','set',str(target),'metadata::trusted','true'],check=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
print('Installation complete. Find TRON Control in your applications.')
print('Ha az asztali ikon szövegszerkesztőt nyit: jobb klikk → Allow Launching / Indítás engedélyezése.')
PY
python3 "$app_dir/tron_control.py"
