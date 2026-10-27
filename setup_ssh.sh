#!/usr/bin/env bash
set -euo pipefail
robot_ip=${1:?Robot IP required}
lang=${2:-hu}
key_path="$HOME/.ssh/tron_control_ed25519"
if [ "$lang" = en ]; then
    printf 'TRON Control — SSH setup\n\nA dedicated local SSH key will be created for this application.\nYour robot password is not stored. The key stays on this Dell.\n\n'
else
    printf 'TRON Control — SSH beállítás\n\nKülön helyi SSH-kulcs készül ehhez az alkalmazáshoz.\nA robot jelszavát nem tároljuk. A kulcs ezen a Dell gépen marad.\n\n'
fi
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
if [ ! -f "$key_path" ]; then
    ssh-keygen -t ed25519 -N '' -C 'TRON Control on Dell' -f "$key_path"
fi
ssh-copy-id -i "$key_path.pub" "guest@$robot_ip"
if [ "$lang" = en ]; then
    printf '\nDone! Close this terminal, then click Check connection.\n'
    read -r -p 'Press Enter to close… ' answer
else
    printf '\nKész! Zárd be ezt a terminált, majd kattints a Kapcsolat ellenőrzése gombra.\n'
    read -r -p 'Enter a bezáráshoz… ' answer
fi
