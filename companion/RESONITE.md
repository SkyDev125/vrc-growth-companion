# Set your Resonite avatar’s height from Mid’s Den

If Mid’s Den says **3 m**, the **Avatar height** preset sends **3** to Resonite. Set up an OSC receiver and a small ProtoFlux graph once on the avatar you want to resize. After that, you can work in metres.

## Send the height

In the companion, select **Settings → Connection → App → Resonite**. Leave the IP at `127.0.0.1` if both apps run on the same computer. Note the OSC port shown in Settings. It defaults to `9002`.

Choose **Presets → Avatar height**, then **Save mapping**. The preset uses **Height**, **Current value**, and `/midsden/height`. Fresh Resonite profiles already include it.

## Receive it in Resonite

1. Wear the avatar. In its Scene Inspector, add an `OSC_Receiver` component. Set `HandlingUser` to yourself, `Port` to the companion’s port, and `AccessReason` to “Mid’s Den height”. Allow OSC receiving when prompted. Check that `IsListening` is on.
2. Add `OSC_Value<float>`. Drag the receiver into `Handler`, enter `/midsden/height` in `Path`, and set `ArgumentIndex` to `0`.
3. Click **Resend** in the companion. Check `OSC_Value.Value` in the inspector. It should show the website height in metres. If it stays at zero, check the receiver, port and path before building the graph.

See the [OSC Receiver](https://wiki.resonite.com/Component:OSC_Receiver) and [OSC Value](https://wiki.resonite.com/Component:OSC_Value) references for inspector screenshots.

## Connect the height to resizing

Resonite’s **Set User Scale** node expects a scale factor. An avatar that stands 2 m tall at scale 1 needs a scale of 1.5 to reach 3 m. A different avatar can need a different factor for the same target. [User scale](https://wiki.resonite.com/User_Scale) · [Set User Scale](https://wiki.resonite.com/ProtoFlux:SetUserScale)

**Measure once.** Stand upright and measure the avatar in metres. Read **User Root Global Scale** from your avatar’s `UserRoot` at that same size. Divide the measured height by that scale and store it as a fixed float. For instance, 1.8 m measured at scale 0.9 gives a reference height of 2 m. Measure from the floor to the same point you mean by “height” on the website. Remeasure if you change the avatar’s proportions or the reference changes. [User Root Global Scale](https://wiki.resonite.com/ProtoFlux:UserRootGlobalScale)

**Wire the value.** With the ProtoFlux Tool equipped, grab the `Value` field name on `OSC_Value<float>` and choose **Source** in the context menu. Connect it to a float **Divide** node. Use the incoming value as the first input and your fixed reference height as the second input. Connect **Divide** to `Scale` on **Set User Scale**. Connect the wearer to **User User Root** and wire its output to `UserRoot`. Set `AnimationTime` to `0` so the companion can handle smoothing. [Using the ProtoFlux Tool](https://wiki.resonite.com/ProtoFlux#Interfacing_With_Components_/_Slots)

**Call it when the height changes.** Connect the same **Source** to `Value` on **Fire On Change**. Set `OnlyForUser` to the avatar’s wearer. Connect `OnChanged` to an **If** node with the condition `Value > 0`, then connect its true output to the impulse input on **Set User Scale**. This skips the initial zero before the first packet arrives. Keep the setup scoped to the wearer. [Fire On Change](https://wiki.resonite.com/ProtoFlux:FireOnChange)

Test with a nearby height change in a world that allows resizing. If `Value` changes in the inspector and the avatar stays the same, check the graph’s impulse wiring, `UserRoot`, and the world’s scaling rules. **Resend** sends the latest value again after a receiver is reloaded. **Fire On Change** reacts when the received number changes.

## Existing receivers and other measurements

An existing **Avatar scale (legacy)** mapping still sends the website’s current height divided by its starting height to `/midsden/scale`. Keep that mapping for an existing receiver. To switch the same avatar to the new preset, point the new graph at `/midsden/height` and disable the old resize mapping so both graphs do not drive the same avatar.

For other measurements, use the exact path shown on the mapping, with `OSC_Value<float>` for decimals or `OSC_Value<int>` for whole numbers and on/off values. On/off arrives as `0` or `1`. **Current value** uses the measurement’s saved unit. Connect the received value to the avatar field or ProtoFlux graph for that property.

The companion’s **receiver unverified** status means it has sent UDP without a game acknowledgement. The outgoing metre values and legacy ratios are covered by local UDP tests. The resizing graph still needs validation on a live avatar.
