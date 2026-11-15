# Mid's Den VRChat Companion

Syncs Mid’s Den measurements to VRChat’s eye height and avatar parameters over OSC. Each platform package includes its own Python runtime, so you do not need to install Python or download a runtime on first launch.

## Start

Download from the website: run the Windows setup EXE, drag the macOS app from its DMG into Applications, or mark the Linux x64 executable as executable and open it. No Python installation or manual archive extraction is needed.

The desktop window saves the VRChat IP and OSC receive port (defaults: `127.0.0.1`, `9000`). It applies enabled mappings on startup, then sends only changed OSC values. Use Stop, edit settings, then Start to apply changes. Enable OSC in VRChat and keep the window open. “Sending” does not confirm receipt inside the game.

Settings are stored in your user application settings directory and survive app upgrades. The desktop interface uses Qt Quick/QML through PySide6, bundled with the application. It uses the website’s paw icon for the app and native installers. Builds are unsigned and may require OS opening approval. Windows/macOS/Linux native builds and smoke tests run in [GitHub Actions](https://github.com/SkyDev125/vrc-growth-companion/actions).

## Smooth growth

In Settings, choose **Growth → Smooth** (experimental; Instant remains the default). Small changes take a few seconds; larger proportional changes get more time, capped at 120 seconds. The same relative change takes the same duration at small and giant scales. The curve eases in and out, reaches the exact endpoint, and retargets from its current value when a new send arrives. **Finish now** completes the current transition.

Smooth mode exposes **Pace** (¼×–4×), **Curve** (Gentle, Steady, Quick start), and **Maximum duration** (3–120 seconds). Gentle is the original eased curve; Steady uses a constant proportional pace; Quick start moves fastest at the beginning and settles gradually. Pace scales the adaptive timing, while Maximum duration caps it. Preferences are saved, apply to ongoing transitions without a size jump, and use the same timeline for linked quantities. **Reset** restores Normal/Gentle/120 seconds. These preferences affect animation only, never the website’s calculated targets or growth rates.

Eye height and linked float mappings smooth by default when this mode is enabled. Each float mapping has its own **Smooth** switch; unrelated parameters opt in there. Boolean and integer mappings stay immediate. Linked quantities keep their linear, squared or cubic relationship throughout the animation. Custom units stay in their saved units. The website and bot continue to show the final calculated amounts; only the companion animates the transition.

The animation worker runs at up to 20 updates per second separately from five-second website polling, deduplicates identical OSC packets, and stops sending once settled. Pause, mapping removal/disable, destination changes and detected VRChat disconnection cancel outgoing transitions. Starting/reconnecting uses observed eye height when OSCQuery provides it; without an observed start, the current website value is applied once. World-disabled height writes are skipped. Smooth OSC scaling can expose VRChat camera jitter on some systems; use Instant if needed. Native automated checks do not replace an in-game Windows/VR comfort test.

## Updates

From version 1.3.0, the installed app checks on startup and every six hours. Choose **Update & restart** when convenient; Settings also has **Check updates**. Mappings and connection settings are kept. No Python or separate updater installation is required. An unsigned older app needs one manual upgrade to get this feature.

The updater verifies an Ed25519-signed release manifest and the exact package size and SHA-256 before installation. Update downloads contain only the app and come from the fixed Mid’s Den update service, independently of your measurement server setting. Windows uses its per-user installer; Linux replaces its executable; macOS replaces the app bundle. Keep the Linux executable or macOS app in a writable location (not inside the mounted DMG). The app stays open if the updater cannot start. Installation results and logs are stored beside your settings under `updates`.

Release publishing happens on the website host after native builds and installer checks pass. Run `node companion/publish-update.cjs <verified-artifact-directory> <data-directory> <build-number> <attempt>` there; the private signing key remains in the host user’s private application data directory, outside this repository and GitHub Actions. Versioned packages are immutable, and the feed is published atomically after all four packages exist. Keep a secure backup of the signing key; key rotation requires an app release trusting the new key first.

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
