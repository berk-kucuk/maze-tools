# maze-tools

The **in-house Maze Linux utility suite**, extracted from the Maze ISO's
`airootfs` overlay into a single pacman package. Instead of baking these scripts
directly into every image, Maze can now build this package once and pull it from
the repo like any other — the first step in moving all Maze-authored components
out of `airootfs/` and into proper packages.

## What's inside

Everything installs to the exact paths the tools, `.desktop` launchers and
systemd units already reference (`/usr/local/{bin,lib}`), so the package is a
**drop-in replacement** for the files currently in `airootfs/`.

| Path | Contents |
| ---- | -------- |
| `usr/local/bin/` | CLI/GUI tools — `mazelinux`, `maze-doctor`, `maze-welcome`, `maze-control-center`, `maze-kernel`, `maze-kernel-helper`, `maze-hardware`, `maze-guard`, `maze-guardd`, `maze-sentinel`, `maze-sentinel-setup`, `maze-killswitch`, `maze-panic`, `maze-panic-restore`, `maze-gpu-driver`, `maze-flatpak-setup`, `maze-enable-blackarch`, `maze-apply-wallpaper`, `maze-primary-screen`, `maze-install-vmware`, `maze-power-saver`, `maze-audit`, `maze-exercise`, `maze-selftest`, `maze-sandbox-check` |
| `usr/local/lib/maze/` | Shared Python libraries — `maze_status.py`, `maze_ui.py`, `maze_i18n.py` |
| `usr/lib/systemd/system/` | Service units — `maze-guardd`, `maze-sentinel`, `maze-sentinel-setup`, `maze-flatpak-setup`. MAC randomisation is not handled here — it's owned exclusively by `maze-guard`/`maze-guardd`. |
| `usr/share/applications/` | Desktop launchers — control center, welcome, kernel switcher, panic, hardware, VMware setup |
| `usr/share/pixmaps/` | Icons the tools/launchers use |

## `maze-doctor` — checking a system

`maze-doctor` is the one tool here that is meant to be run when something feels
wrong, and its output is meant to be pasted into a bug report:

```bash
sudo maze-doctor            # full check
sudo maze-doctor --deep     # also verify every installed file against its package
maze-doctor --no-color      # plain text, for pasting
```

It is **read-only** — it inspects and reports, it never repairs — and every
finding prints the command that fixes it. Exit code is 0 when clean, 2 when only
warnings were raised, 1 when something needs attention.

It verifies the whole of what Maze adds on top of stock Arch, in 18 sections:
the Secure Boot chain end to end (via `maze-boot-check`), installed kernels and
their DKMS modules, every Maze package and whether anything unowned is shadowing
packaged files, branding and identity, the kernel command line and initramfs
hooks, pacman configuration and signature policy, **live-medium residue** (the
installer, passwordless sudo, autologin, the live user — the class of leftover
that is a security hole on a real install), storage and ESP headroom, filesystem
and btrfs integrity, snapshots, systemd units, the security posture (Secure
Boot, MOK enrolment, AppArmor, LUKS, sysctl hardening, firewall), recent kernel
errors in the journal, and SMART on every disk.

Live in `usr/local/bin/maze-doctor` — this package is its only home, so there is
nothing to keep in sync.

## `maze-selftest` — checking that the audit fixes work

`maze-selftest` proves that the fixes from the September 2026 audit
(`MAZE-DENETIM-RAPORU.md`) are installed and behave as promised. Where a fix can
be exercised safely it is exercised, not just looked for:
- HazeDrop is started on 127.0.0.1 and asked for a file without the link key.
- A cut-short transfer is decrypted and must be rejected.
- Maze AI's command classifier is fed the commands it must refuse.
- Maze Cloak generates addresses.
- The guard daemon's session check is run.

Each check is gated on the package version that carries its fix, so a package
that is not updated yet shows up as SKIP, not FAIL. It changes nothing.

```sh
sudo maze-selftest          # everything, including ESP / keyring / boot images
maze-selftest               # without root: root-only checks are skipped
```

Exit code 0 means no FAIL.

## Layout

```
maze-tools/
├── PKGBUILD          # the build script (pacman package)
├── build.sh          # convenience wrapper: build [+ install / + add to repo]
├── README.md
└── maze-tools/       # payload — a verbatim mirror of the target filesystem
    └── usr/...
```

Adding or updating a tool means dropping it into `maze-tools/usr/...` at its
final install path and bumping `pkgver` — `PKGBUILD` copies the whole tree, so
it never needs editing for content changes.

## Building

`makepkg` (and therefore `build.sh`) must run as a **normal user**, not root:

```sh
./build.sh                 # -> maze-tools-1.1.0-7-any.pkg.tar.zst
./build.sh --install       # build, then sudo pacman -U the result
./build.sh --repo ../MazeLinux/localrepo   # build + add to the ISO's local repo
```

Once it's in the `localrepo`, list `maze-tools` in the ISO's `packages.x86_64`
and the tool files can be removed from `airootfs/` — the package supplies them.

## Notes

- **Ready out of the box.** Because a PKGBUILD may not enable services directly,
  the package ships a systemd preset (`usr/lib/systemd/system-preset/90-maze-tools.preset`)
  and a `.install` scriptlet. On install they enable `maze-guardd`,
  `maze-flatpak-setup`, `maze-sentinel` and `maze-sentinel-setup`,
  and reload udev rules — no user action required. The safe services
  (broker + sentinel) start immediately on a live install. Upgrades reload
  units/rules but do **not** re-enable, so admin choices stick.
- **Not included** (deliberately): archiso stock scripts (`choose-mirror`,
  `Installation_guide`, `livecd-sound`), the Calamares launcher
  (`maze-calamares`, installer-only), and ISO/branding assets — those belong to
  their own packages in later extraction steps.
