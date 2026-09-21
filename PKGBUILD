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
pkgrel=41
pkgdesc="Maze Linux in-house utility suite (mazelinux, welcome, control center, kernel switcher, guard, sentinel, panic, MAC/GPU helpers, system doctor, maze-audit, maze-exercise)"
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
backup=()
# Scriptlet that enables the shipped services on install (Arch forbids doing
# this from package()), so the system is ready out of the box.
install="${pkgname}.install"
# The tools ship inside this package directory (no remote source).
source=()

package() {
  # The payload tree sits next to this PKGBUILD, under ./maze-tools/usr/...
  # ($startdir is the directory containing the PKGBUILD). Copy it straight in.
  cp -a "${startdir}/maze-tools/usr" "${pkgdir}/usr"

  # Normalise permissions: every shipped tool must be executable.
  local f
  for f in "${pkgdir}"/usr/local/bin/*; do
    chmod 755 "$f"
  done
}
