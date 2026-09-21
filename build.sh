#!/usr/bin/env bash
#
# build.sh — build (and optionally install) the maze-tools package in one shot.
#
#   ./build.sh            build the package  ->  ./maze-tools-<ver>.pkg.tar.zst
#   ./build.sh --install  build, then install it with pacman (needs root)
#   ./build.sh --repo DIR  build, then add the package to the pacman repo DIR
#                          (updates DIR/maze-aur.db.tar.zst — matches the ISO's
#                          [maze-aur] localrepo used by tools/build-aur.sh)
#
# makepkg refuses to run as root, so run this as a normal user; only the
# install / repo-add steps escalate.
set -euo pipefail

cd "$(dirname "$(readlink -f "$0")")"

INSTALL=0
REPO=""
while [ $# -gt 0 ]; do
  case "$1" in
    --install) INSTALL=1 ;;
    --repo) REPO="${2:?--repo needs a directory}"; shift ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "build.sh: unknown option '$1'" >&2; exit 2 ;;
  esac
  shift
done

echo ">> building maze-tools with makepkg…"
makepkg -f --nodeps

PKGFILE=$(ls -t maze-tools-*.pkg.tar.* 2>/dev/null | head -1 || true)
[ -n "$PKGFILE" ] || { echo "build.sh: no package produced" >&2; exit 1; }
echo ">> built: $PKGFILE"

if [ "$INSTALL" -eq 1 ]; then
  echo ">> installing (sudo pacman -U)…"
  sudo pacman -U --noconfirm "$PKGFILE"
fi

if [ -n "$REPO" ]; then
  mkdir -p "$REPO"
  cp -f "$PKGFILE" "$REPO/"
  echo ">> adding to repo $REPO …"
  repo-add "$REPO/maze-aur.db.tar.zst" "$REPO/$PKGFILE"
fi

echo ">> done."
