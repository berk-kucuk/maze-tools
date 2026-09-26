# Maintainer: Berk Küçük <dev.berkkucukk@gmail.com>
#
# maze-tools — the in-house Maze Linux utility suite, extracted from the ISO's
# airootfs overlay into a single pacman package so it can be built once and
# pulled from the Maze repo instead of being baked into every image.
#
# The payload lives verbatim under ./maze-tools/ (a mirror of the target
# filesystem). package() simply copies that tree into $pkgdir, so adding or
# updating a tool never means touching this file — drop it into maze-tools/
# at its final install path and rebuild.
#
# Paths are intentionally kept at /usr/local/{bin,lib} to match the locations
# every tool, .desktop launcher and systemd unit already hard-codes, making the
# package a drop-in replacement for the files currently in airootfs.

pkgname=maze-tools
pkgver=1.1.0
pkgrel=54
pkgdesc="Maze Linux in-house utility suite (mazelinux, welcome, control center, kernel switcher, guard, sentinel, panic, MAC/GPU helpers, system doctor, maze-audit, maze-exercise, maze-selftest)"
arch=('any')
url="https://mazelinux.berkkucukk.com.tr"
license=('GPL3')
depends=(
  'python'
  'pyside6'
  'bash'
  'polkit'
  'networkmanager'
  'util-linux'
  'iproute2'
  'maze-branding'   # supplies the shared /usr/share/pixmaps/maze-*-logo.png used by the GUI apps and .desktop icons
)
optdepends=(
  'flatpak: Flathub registration (maze-flatpak-setup)'
  'ollama: local-AI status in mazelinux / maze-welcome'
  'nvidia-utils: NVIDIA driver management and GPU telemetry (maze-gpu-driver)'
  'audit: Maze Sentinel audit watches (maze-sentinel)'
)
provides=('mazelinux')
backup=(
  # ── Adopted from the ISO's airootfs (2026-09) ──────────────────────────────
  # These used to exist only in the live image, so installed machines carried
  # them UNOWNED and no update ever reached them. They are in backup=() so the
  # takeover is silent: pacman does not treat an existing unowned file that the
  # package lists as a backup as a conflict — an identical copy is simply
  # adopted, a locally edited one is kept and the packaged one lands as .pacnew.
  # Without this, `pacman -Syu` on every installed Maze would stop with
  # "exists in filesystem" until the user ran --overwrite by hand.
  'usr/share/plasma/plasmoids/com.mazelinux.panic/contents/icons/maze-panic.svg'
  'usr/share/plasma/plasmoids/com.mazelinux.panic/contents/ui/main.qml'
  'usr/share/plasma/plasmoids/com.mazelinux.panic/metadata.json'
  'etc/maze/sentinel.conf'
)
# Scriptlet that enables the shipped services on install (Arch forbids doing
# this from package()), so the system is ready out of the box.
install="${pkgname}.install"
# The tools ship inside this package directory (no remote source).
source=()

package() {
  # The payload tree sits next to this PKGBUILD, under ./maze-tools/usr/...
  # ($startdir is the directory containing the PKGBUILD). Copy it straight in.
  cp -a "${startdir}/maze-tools/usr" "${pkgdir}/usr"
  cp -a "${startdir}/maze-tools/etc" "${pkgdir}/etc"
  # Never ship bytecode left behind by running a tool from the source tree
  # (git ignores it, but cp -a does not): a stale .pyc under /usr/local/bin
  # would sit next to the real script, owned by this package, forever.
  find "${pkgdir}" \( -name '__pycache__' -o -name '*.pyc' \) -prune -exec rm -rf {} +

  # Normalise permissions: every shipped tool must be executable.
  local f
  for f in "${pkgdir}"/usr/local/bin/*; do
    if [ -f "$f" ]; then chmod 755 "$f"; fi
  done
}
