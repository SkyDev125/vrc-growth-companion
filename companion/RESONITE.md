# Resonite OSC integration

In Settings → Connection, choose **Resonite**. The companion keeps VRChat and Resonite mappings and destination ports separately. Our suggested Resonite port is **9002**; it is a convention you can change, not an official Resonite default. Set the same port on your in-world receiver. VRChat remains on its previous port when you switch back.

Resonite has native generic OSC input. It has no universal `/avatar/eyeheight` endpoint or standard OSCQuery avatar-parameter catalogue. Suggested paths in this companion are receiver conventions, not automatically discovered fields. **Copy setup** copies instructions and your current mapping paths, types and units to the clipboard. This is a receiver setup guide, not a ready-to-import avatar asset. A receiver must be configured in-world once.

## Receiver

1. Add `OSC_Receiver` to a slot on your avatar. Assign `HandlingUser` to the wearer, `Port` to the companion destination port, and `AccessReason` to “Mid's Den growth”. Accept the OSC-receiving permission prompt. `IsListening` should become true.
2. Add `OSC_Value<float>` for each decimal mapping or `OSC_Value<int>` for whole-number/on-off mappings. Assign its `Handler` to that receiver, `Path` exactly to the path listed by the companion, and `ArgumentIndex` to 0. Observe `Value` to check reception. You can use `OSC_Field<T>` to drive a matching scalar field directly instead.
3. Connect the values to the desired avatar fields or ProtoFlux. Custom paths can be entered directly in the mapping editor. Suggestions use `/midsden/measurements/<measurement-id>`; they stay stable when a measurement is renamed.

## Avatar scale preset

**Presets → Avatar scale** maps Height to `/midsden/scale` using **Growth ratio**. A website starting height of 2 m and current height of 3 m sends **1.5**, not 3 metres. Resonite scale is dimensionless. It depends on avatar/user/world configuration, so a metre value is not a valid substitute for a scale multiplier.

Calibrate in Resonite with the avatar at the website's starting height. Capture **User Root Global Scale** into a stored `BaselineScale` value. On changes to the received scale, calculate:

`target scale = BaselineScale × received /midsden/scale`

Use **Set User Scale** with the wearer's UserRoot and that target. Set **AnimationTime = 0** because the companion already animates intermediate values. Resonite documents that a running Set User Scale animation blocks additional scale requests until it finishes. Guard execution so only the wearer handles these changes; `Local User Root` must not be used to scale other viewers of a shared object. Ignore uninitialized/non-positive received scale values.

Keep the baseline constant during growth. Multiplying the incoming ratio by the current live scale would compound growth. Recalibrate for a different avatar or a changed baseline/parent scale. The companion cannot measure or calibrate a Resonite avatar through this one-way OSC connection.

## Attributes and smoothing

Value, ratio, range and threshold mappings work as in the existing companion. Decimals use OSC float32, whole numbers use int32, and on/off mappings use **int32 0/1** (compare against zero in ProtoFlux to obtain a bool). This avoids depending on undocumented OSC boolean support. Original units are preserved: a volume stays a volume, and custom units remain unchanged. Use range mapping if a receiver expects a different numeric range.

The same opt-in Smooth mode, pace, curve, duration cap and Finish now controls apply. Linked measurements keep their linear/squared/cubic relationships. Resonite scale mappings are not subjected to VRChat's eye-height clamp; mapped floats still have OSC float32 limits. Receiver/world rules can impose additional restrictions.

## Status and reconnects

The app says **Resonite OSC · receiver unverified**. A successful UDP send is not a receipt acknowledgement. It does not claim the game is detected or the receiver is connected. Check the receiver and value in-world.

Use **Resend** after equipping/reloading the receiver or changing worlds. At rest, unchanged values are not repeatedly sent, so a receiver created after the initial packet needs a deliberate resend. Pause and app/endpoint changes stop old outgoing transitions. Smooth growth with no observed initial Resonite size applies the first target once, then smooths later changes; it does not invent a starting height.

## Research and validation

Chosen transport: native generic OSC. ResoniteLink is an alternative, but it is beta and is enabled per session with host/builder/world permission restrictions. This first integration does not require ResoniteLink or a mod.

Verified with real local UDP sockets, including scale ratios, custom addresses, int on/off values, unchanged-packet suppression, separate saved app destinations/profiles and UI switching. This environment has not run a live Resonite avatar; the in-world receiver/calibration instructions need an actual game check before claiming end-to-end validation.

Official sources checked during implementation:

- [OSC](https://wiki.resonite.com/OSC)
- [OSC Receiver](https://wiki.resonite.com/Component:OSC_Receiver)
- [OSC Value](https://wiki.resonite.com/Component:OSC_Value)
- [OSC Field](https://wiki.resonite.com/Component:OSC_Field)
- [User scale](https://wiki.resonite.com/User_Scale)
- [Set User Scale](https://wiki.resonite.com/ProtoFlux:SetUserScale)
- [User Root Global Scale](https://wiki.resonite.com/ProtoFlux:UserRootGlobalScale)
- [ResoniteLink](https://wiki.resonite.com/ResoniteLink)
- [Official ResoniteLink project](https://github.com/Yellow-Dog-Man/ResoniteLink)
