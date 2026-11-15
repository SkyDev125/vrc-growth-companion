# Mid's Den VRChat Companion

Syncs Mid’s Den measurements to VRChat’s eye height and avatar parameters over OSC. Each platform package includes its own Python runtime, so you do not need to install Python or download a runtime on first launch.

## Start

Download from the website: run the Windows setup EXE, drag the macOS app from its DMG into Applications, or mark the Linux x64 executable as executable and open it. No Python installation or manual archive extraction is needed.

The desktop window saves the VRChat IP and OSC receive port (defaults: `127.0.0.1`, `9000`). It applies enabled mappings on startup, then sends only changed OSC values. Use Stop, edit settings, then Start to apply changes. Enable OSC in VRChat and keep the window open. “Sending” does not confirm receipt inside the game.

Settings are stored in your user application settings directory and survive app upgrades. The desktop interface uses Qt Quick/QML through PySide6, bundled with the application. It uses the website’s paw icon for the app and native installers. Builds are unsigned and may require OS opening approval. Windows/macOS/Linux native builds and smoke tests run in [GitHub Actions](https://github.com/SkyDev125/vrc-growth-companion/actions).

The included runtime is CPython 3.13.18 from [python-build-standalone](https://github.com/astral-sh/python-build-standalone/releases/tag/20261110). Its original license and notices are included with each runtime.

The companion reads measurement names, units, current values and starting values. It does not use the dashboard password or read the ledger. OSCQuery discovery uses local mDNS; it does not need an OSC receive port. It sends OSC only to this computer or a private IP you enter. Network isolation can block local OSC traffic.

OSC accepts eye heights from `0.01m` to `10,000m`. Only `0.1m`–`100m` is officially supported by VRChat; outside that range the game displays a warning and some systems may misbehave. Worlds can still restrict scaling.

## Diagnostics

With OSC enabled, start the launcher with `--test-osc 2` to send a 2m test value without contacting Mid's Den. If VRChat runs on another computer, also pass `--osc-host 192.168.1.42` with its private IP. Adjust your avatar back afterward if desired.

The website is checked every five seconds. Unchanged values are not resent. Avatar switches and detected reconnections apply mappings once again; use Resend for a deliberate retry when discovery is unavailable. OSCQuery is not required. UDP sending does not confirm receipt inside the game. Existing settings keep their port; use `--configure` to change it.

## Avatar mappings

Choose a measurement and an avatar parameter, then Save mapping. OSCQuery lists writable float, int and bool parameters from the current avatar. Mappings are saved separately for each detected avatar. If discovery is unavailable, enter a parameter name manually; these mappings are shared across avatars.

- **Value:** send the current amount in its saved unit.
- **Ratio:** current ÷ original (1 = starting amount).
- **Range:** map a measurement range to an OSC range, clamped at both ends. For example, 0–200 cm → 0–1.
- **Threshold:** turn a bool on at or above an amount.

Linked measurements already include their website scaling. Display conversions do not change mapping units. Eye height is an ordinary mapping. Use + Eye height preset to add it; disable or remove its row to stop syncing. The status shows when OSCQuery responds, not an acknowledgement of UDP delivery. The avatar must already have a suitable writable parameter and animator setup; OSC cannot add one. Discovery is optional and may be unavailable across devices.

The parameter field supports case-insensitive substring search. The field’s dropdown arrow browses the complete discovered list; read-only or unsupported parameters are visible but disabled. Mapping rows show calculated OSC outputs; these previews do not confirm UDP delivery.

Windows setup installs the bundled runtime alongside the app, so one app window uses one process and upgrades do not depend on the single-file launcher. If you allow setup to close the running app, it may force-close it; save any open mapping edit first.
