# ChilloutVR

1. Enable **Settings → Implementation → OSC** in ChilloutVR.
2. In the companion, choose **Settings → Connection → App → ChilloutVR**.
3. Wear your avatar. The parameter picker discovers its OSC parameters; read-only entries remain visible but disabled.
4. Add a mapping, select a website measurement and a writable avatar parameter, and save.

The app identifies ChilloutVR's OSCQuery service and uses its advertised OSC receive port. The default is `127.0.0.1:9000`. Keep the default OSCQuery prefix `ChilloutVR`. If mDNS is blocked, set `oscQueryPort` in the saved configuration to the game's TCP query port. Without identified ChilloutVR discovery, no ChilloutVR mappings are sent. “Detected” confirms OSCQuery availability, not UDP delivery or a visible avatar effect.

## Scaling

Choose **Presets → Scale mapping** to start with Height and a range mapping. Select the scale parameter actually authored on your avatar, and enter its measurement and parameter ranges. The initial `0–10 → 0–1` values are examples; replace them with the avatar's real limits.

For example, if an avatar's scale slider maps **1–5 metres** to **0–1**, a website height of **3 metres** sends **0.5**. This only works if that avatar's animator/AAS setup defines that relationship. OSCQuery exposes names and types, but cannot detect what a parameter does or its scaling limits.

Use **Growth ratio** only when the parameter expects current ÷ starting height. **Current value** sends the measurement in its saved unit. The companion does not assume metres are a scale factor, and there is no documented universal VRChat-style `/avatar/eyeheight` command for ChilloutVR. Avatars need a suitable animation/parameter before OSC can drive their size.

## Saved mappings and smoothing

ChilloutVR, VRChat and Resonite keep separate mappings and connection destinations. Detected ChilloutVR avatars and avatar profiles each have their own mapping set. Switching avatars or reconnecting reapplies that set once; settled values are deduplicated.

Smooth mode, pace, curves, maximum duration and Finish now work with ChilloutVR float mappings. The scale preset opts into smoothing; other float mappings can enable it individually. Integers and booleans remain immediate. Website calculations, linked quantities and saved units are unchanged.

If running VRChat and ChilloutVR simultaneously, use separate receive ports: both default to UDP 9000. ChilloutVR accepts `--osc-listener-port=<port>`; discovery follows its advertised port. This companion is a sender, so it does not need to bind that receive port.

**Copy setup** in Settings copies these instructions plus your current destinations and mapping ranges.

Protocol tests cover a local mock OSCQuery server, actual UDP packets, type/read-only checks, deduplication, advertised ports and game/profile switching. They do not replace an in-game ChilloutVR check with a compatible avatar.

Official references: [OSC](https://docs.chilloutvr.net/chilloutvr/game/osc/), [launch arguments](https://docs.chilloutvr.net/chilloutvr/game/launch-arguments/), [CVR Avatar](https://docs.chilloutvr.net/cck/components/cvr-avatar/).
