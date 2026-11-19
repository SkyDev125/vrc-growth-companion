# Send a measurement to Resonite

Use the same setup for a tail length, a volume, a custom counter, or any other measurement from Mid’s Den. Start with a field or graph on your Resonite object that can use the value.

1. **Pick a measurement.** In the companion, choose **Settings → App → Resonite**, then **New mapping**. Select the measurement and keep its suggested receiver path, or enter the path your object already uses. **Current value** sends the number in its website unit. A tail length of 30 cm sends `30`, so use a field that expects centimetres or select **Map a range** to match what the field expects.
2. **Receive the number.** In Resonite’s Scene Inspector, add `OSC_Receiver` to your object. Set `HandlingUser` to yourself, enter the OSC port shown in the companion (usually `9002`), give it an `AccessReason`, and allow receiving when prompted. Add an `OSC_Value` for the mapping and fill in `Handler` with that receiver, `Path` with the path shown in the companion, and `ArgumentIndex` with `0`. Use `float` for decimals and `int` for whole numbers and on/off values. The app’s **Setup guide** lists the paths and types for your enabled mappings.
3. **Try it.** Click **Resend** and check `OSC_Value.Value`. If it stays empty, check `IsListening`, the port and the path. For a direct connection to a numeric field, set up `OSC_Field` with the same settings in place of `OSC_Value`, then drag the field into `Field`. For custom behaviour, read `OSC_Value.Value` in ProtoFlux. Convert on/off values from `0` or `1` there.

On the same computer, keep the companion IP at `127.0.0.1`. One receiver can handle many paths. The companion sends changes and can resend the current values after a reload. You can check receipt in the Resonite inspector. [OSC receiver](https://wiki.resonite.com/Component:OSC_Receiver) · [OSC Value](https://wiki.resonite.com/Component:OSC_Value) · [OSC Field](https://wiki.resonite.com/Component:OSC_Field)

## Avatar height

Use **Presets → Avatar height** for a receiver that scales the whole wearer. This sends metres as a `float` to `/midsden/height`. If an existing receiver already uses that path, save the mapping and use **Resend**. An older receiver on `/midsden/scale` can keep using its saved mapping.

### Use the avatar’s rig when it can be verified

`VRIKAvatar.AvatarHeight` describes the rig’s floor-to-eye height. An avatar with a floor and eye marker in its authored standing pose can be calibrated from those slots. This keeps headset position out of the reference. `HeightCompensation` is reported separately because it can change how the avatar fits the tracking points. [VRIKAvatar fields](https://wiki.resonite.com/Component:VRIKAvatar)

The authoring tool reads the equipped avatar through a temporary local ResoniteLink session. It transforms the rig’s height into wearer space and compares it with the authored markers. Save [`resonite-height-calibration.mjs`](https://raw.githubusercontent.com/SkyDev125/vrc-growth-companion/main/companion/resonite-height-calibration.mjs) and run it with Node 22 or newer. Run it in a private session on a copy of the avatar. Use the slots from the model’s neutral pose rather than the live view or feet trackers. [ResoniteLink setup](https://wiki.resonite.com/ResoniteLink)

```sh
node resonite-height-calibration.mjs --port PORT --avatar-slot AVATAR_ID --eye-slot EYE_ID --floor-slot FLOOR_ID
```

This command previews the result. If the rig and markers agree within 2%, add `--apply --reference-slot RIG_REFERENCE_ID` to save the reference on that avatar. The destination must be a child slot tagged `midsden/rig-eye-height` with one `ValueField<float>`. Start its value at zero. In the height graph, prefer this field when it contains a positive value and use the stored standing capture otherwise. If a later check reports a mismatch, reset the rig reference to zero to use the fallback. The authoring tool only needs ResoniteLink while you set up the avatar. Save the configured avatar after testing it.

### Build the height receiver and standing fallback

Set up `OSC_Value<float>` at `/midsden/height` as above. The fallback captures the wearer’s standing view height once. In VR it can reflect headset position, so use it only if the avatar has no verified rig reference. Use a flat floor and normal first-person view when capturing. [Set User Scale](https://wiki.resonite.com/ProtoFlux:SetUserScale) · [Position At User](https://wiki.resonite.com/Component:PositionAtUser)

1. **Read the wearer.** Put the graph under the avatar. Use **Get Active User Self** for the wearer, **User User Root** for the resize command, and **User Root Slot** for coordinate conversion. Create two helper slots with `PositionAtUser` set to the wearer. Use `PositionSource` **View** for one and **GroundProjectedHead** for the other, with zero position offsets. Set each component’s `PositionDrive` to the `Position` field of its helper slot. Read both world positions with **Global Transform**. [Get Active User Self](https://wiki.resonite.com/ProtoFlux:GetActiveUserSelf) · [User Root Slot](https://wiki.resonite.com/ProtoFlux:UserRootSlot)
2. **Capture the reference.** Convert both positions into the **User Root Slot** using **Global Point To Local**. Subtract the floor position’s Y from the view position’s Y. Make a **Capture standing height** button and wire its **Pressed** event to store that result in a `ValueField<float>` when it is positive. Only accept a capture from the wearer. Stand upright and press it once. Retake it if you change avatars or change the avatar’s proportions. [Global Point To Local](https://wiki.resonite.com/ProtoFlux:GlobalPointToLocal) · [Button Events](https://wiki.resonite.com/ProtoFlux:ButtonEvents)
3. **Apply the incoming height.** Select the verified rig reference or the standing fallback as described above. Divide `OSC_Value.Value` by that reference. Wire the result into `Scale` on **Set User Scale** and set `AnimationTime` to `0` so the companion can smooth changes. Use **Fire On Change** on the OSC value, with `OnlyForUser` set to the wearer, to run the resize. Apply only when both numbers are positive. Run the same check after calibration so the latest value takes effect even if it arrived first. [Fire On Change](https://wiki.resonite.com/ProtoFlux:FireOnChange)

### Check it in-game before adopting it

1. Compare the authoring tool’s preview at two different wearer scales. The reference in wearer space should stay the same. If the avatar geometry changes, clear the rig reference before using it again.
2. In a world that allows resizing, send two nearby target heights from the companion. Verify that the `OSC_Value` in Resonite receives both numbers. Then verify that the wearer resizes and the distance from the authored floor to the eyes matches each target. A change in the inspector’s OSC field confirms receipt only.
3. Repeat with the rig reference empty and a separate standing capture stored. Check that the fallback works and crouching later keeps the saved reference.

The companion’s **receiver unverified** label describes its one-way OSC connection. The authoring tool and its checks have been tested against simulated ResoniteLink data, and the wiring still needs a live Resonite check.
