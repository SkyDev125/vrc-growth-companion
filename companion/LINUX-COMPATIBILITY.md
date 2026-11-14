# Linux compatibility checks

The exact Linux x64 executable from release `desktop-2-1` passed on all four representative distro userlands:

| Family | Tested image | Result |
| --- | --- | --- |
| Debian/Ubuntu | Ubuntu 22.04 | Passed |
| Fedora | Fedora 43 | Passed |
| Arch | archlinux:base (rolling) | Passed |
| openSUSE | Leap 16.0 | Passed |

[Actions results](https://github.com/SkyDev125/vrc-growth-companion/actions/runs/43537055824)

Artifact SHA-256: `c8728d71e1080dea40cbd67e881f2cfc89c43642339a208e5af1a3bc0427ec70`.

Each check verifies the released binary checksum, installs a virtual X display and ordinary desktop prerequisites in an official distro container, then executes the app's bundled Tk/SSL/OSC self-test. No distro-specific rebuild is substituted for the downloadable executable. Reports record the tested release and container image digests.

Containers share the runner's Linux kernel. These checks cover x64 userland library compatibility and GUI startup. They do not test complete GNOME/KDE/Wayland sessions, hardware, live VRChat, or all derivative distros. Ubuntu and Kubuntu share a base and are deliberately not duplicated. Alpine (musl), NixOS, and ARM are outside this binary's tested coverage.

The compatibility workflow can be run manually and runs after successful desktop installer builds. In that case it selects the release produced by the triggering build commit.
