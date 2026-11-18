#!/bin/bash
# Runs INSIDE a distro container against the unchanged released executable.
set -euo pipefail
family=${1:?Expected distro family}
case "$family" in
  ubuntu)
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y --no-install-recommends xvfb ca-certificates fonts-dejavu-core libegl1 libopengl0 libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libxcb-xinerama0 libxcb-shape0 libxcb-randr0 libxcb-xfixes0 libxcb-sync1 libxcb-shm0 libxcb-render0 libxcb-glx0 libxcb-xkb1
    ;;
  fedora)
    dnf install -y xorg-x11-server-Xvfb ca-certificates dejavu-sans-fonts mesa-libEGL libglvnd-opengl libxcb xcb-util-cursor xcb-util-wm xcb-util-image xcb-util-keysyms xcb-util-renderutil libxkbcommon-x11
    ;;
  arch)
    pacman -Syu --noconfirm xorg-server-xvfb ca-certificates ttf-dejavu libglvnd libxcb xcb-util-cursor xcb-util-wm xcb-util-image xcb-util-keysyms xcb-util-renderutil libxkbcommon-x11
    ;;
  opensuse)
    zypper --non-interactive refresh
    zypper --non-interactive install --no-recommends xorg-x11-server-Xvfb ca-certificates dejavu-fonts libglvnd libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libxcb-xinerama0 libxcb-shape0 libxcb-randr0 libxcb-xfixes0 libxcb-sync1 libxcb-shm0 libxcb-render0 libxcb-glx0 libxcb-xkb1
    ;;
  *) echo "Unknown family: $family" >&2; exit 2 ;;
esac
cat /etc/os-release
ldd --version
Xvfb :99 -screen 0 800x600x24 -nolisten tcp >"/reports/$family-xvfb.log" 2>&1 &
xvfb_pid=$!
trap 'kill "$xvfb_pid" 2>/dev/null || true' EXIT
for attempt in {1..50}; do
  if [ -S /tmp/.X11-unix/X99 ]; then break; fi
  if ! kill -0 "$xvfb_pid" 2>/dev/null; then cat "/reports/$family-xvfb.log"; exit 1; fi
  sleep 0.1
done
export DISPLAY=:99
export MIDSDEN_SMOKE_REPORT="/reports/$family.json"
/app/mids-den-companion-linux-x64 --self-test
[ -s "$MIDSDEN_SMOKE_REPORT" ]
cat "$MIDSDEN_SMOKE_REPORT"
echo "Released executable GUI/SSL/OSC smoke check passed on $family (x86_64)."
