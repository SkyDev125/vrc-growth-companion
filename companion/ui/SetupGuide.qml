import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Popup {
    id: guide
    objectName: "setupGuide"
    property string appId: "vrchat"
    property string gameName: "VRChat"
    property string host: "127.0.0.1"
    property int port: 9000
    property var mappings: []
    property int step: 0
    property var steps: appId === "resonite" ? [
        {
            title: "Send your target height",
            body: "In the companion, open Presets → Avatar height and save the mapping. If the website says 3 m, the companion sends 3 to /midsden/height.",
            tip: guide.mappings.some(m => m.address === "/midsden/scale" && m.mappingEnabled)
                ? "You already have an Avatar scale mapping. Leave it active for your old receiver, or turn it off when you switch that avatar to the new height receiver."
                : "Set up the receiver once on the avatar you want to resize. The next steps show how to do that in Resonite.",
            url: "https://wiki.resonite.com/OSC"
        },
        {
            title: "Receive the height in Resonite",
            body: "1. In your avatar’s Scene Inspector, add OSC_Receiver. Set HandlingUser to you, Port to " + port + " and AccessReason to Mid’s Den height. Allow OSC receiving when prompted.\n\n2. Add OSC_Value<float>. Drag the receiver into Handler, set Path to /midsden/height and set ArgumentIndex to 0.\n\n3. Click Resend in the companion. In the inspector, Value should show the website height in metres.",
            tip: "If Value stays at 0, check IsListening, the path, and the saved destination " + host + ":" + port + ".",
            url: "https://wiki.resonite.com/Component:OSC_Value"
        },
        {
            title: "Tell Resonite how tall this avatar is",
            body: "Measure your avatar standing upright in metres. At the same size, use User Root Global Scale to read your UserRoot’s scale. Divide the measured height by that number and save the result as a fixed float in ProtoFlux.\n\nFor example, an avatar measuring 1.8 m at scale 0.9 stands 2 m tall at scale 1. Keep 2 as its reference height.",
            tip: "The reference lets Resonite turn metres into the right resize amount for this avatar. Repeat the measurement if you change the avatar’s proportions.",
            url: "https://wiki.resonite.com/User_Scale"
        },
        {
            title: "Wire up resizing and test",
            body: "With the ProtoFlux Tool, create a Source from OSC_Value’s Value field. Connect it to a float Divide node and put the fixed reference height in the second input. Wire the result into Scale on Set User Scale.\n\nFeed Value into Fire On Change. Set OnlyForUser to the wearer and route OnChanged through an If check for Value > 0 before calling Set User Scale. Connect the same wearer to User User Root and wire its output into UserRoot. Set AnimationTime to 0.",
            tip: "Try a nearby website height and check the result in a world that allows resizing. With a reference height of 2 m, a target of 3 m gives a scale of 1.5. The companion handles smoothing.",
            url: "https://wiki.resonite.com/ProtoFlux:SetUserScale"
        }
    ] : appId === "chilloutvr" ? [
        {title:"Enable OSC", body:"In ChilloutVR, open Settings → Implementation → OSC and enable it. Wear your avatar, then wait for “ChilloutVR detected” in the companion.", tip:"The companion uses the receive port advertised by ChilloutVR. Keep its default OSCQuery name prefix. If both games run together, VRChat and ChilloutVR need different receive ports.", url:"https://docs.chilloutvr.net/chilloutvr/game/osc/"},
        {title:"Choose what to control", body:"Add a mapping and choose a website measurement. Open the Avatar parameter dropdown to browse your avatar’s parameters, or type to search. Choose a writable parameter and save.", tip:"Your avatar must already have an animation or parameter that controls the property. OSC cannot add one.", url:"https://docs.chilloutvr.net/cck/components/cvr-avatar/"},
        {title:"Map size and check", body:"For height, use Presets → Scale mapping and select your avatar’s scaling parameter. Replace the example range with that avatar’s actual limits.\n\nExample: an avatar slider authored for 1–5 m → 0–1 needs 0.5 at 3 m.\n\nSave, then use Resend and check the result in-game.", tip:"ChilloutVR has no documented universal eye-height command. A detected connection confirms discovery, not that an avatar animation responded.", url:"https://docs.chilloutvr.net/chilloutvr/game/osc/"}
    ] : [
        {title:"Enable OSC", body:"In VRChat’s Action Menu, open OSC → Enabled. Keep the companion running while you play.", tip:"On this computer, use 127.0.0.1 and the usual receive port 9000. For another device, use its private network IP.", url:"https://docs.vrchat.com/docs/osc-overview"},
        {title:"Add a mapping", body:"Presets → Eye height connects website Height to avatar eye height. For other properties, add a mapping and choose a writable avatar parameter from the dropdown.", tip:"The avatar must already provide the parameter and animation you want to control. Each detected avatar keeps its own mappings.", url:"https://docs.vrchat.com/docs/osc-avatar-parameters"},
        {title:"Check in-game", body:"Save your mapping and use Resend. Check that your avatar responds. Enable Smooth in Settings if you want gradual changes.", tip:"Worlds can restrict avatar scaling. “VRChat detected” confirms OSCQuery discovery, not delivery of each OSC message.", url:"https://docs.vrchat.com/docs/osc-overview"}
    ]
    property var page: steps[Math.min(step, steps.length - 1)]
    anchors.centerIn: parent
    width: Math.min(620, parent.width - 48)
    height: Math.min(500, parent.height - 40)
    padding: 24; modal: true; focus: true
    closePolicy: Popup.CloseOnEscape
    onOpened: step = 0
    background: Rectangle { radius: 18; color: "#18212d"; border.color: "#405067" }
    Overlay.modal: Rectangle { color: "#a6080d15" }
    contentItem: ColumnLayout {
        spacing: 16
        RowLayout {
            Layout.fillWidth: true
            Text { text: guide.gameName + " setup"; color: "#eef2f7"; font.pixelSize: 20; font.weight: Font.DemiBold; Layout.fillWidth: true }
            ActionButton { objectName:"closeSetupGuide"; text:"×"; quiet:true; Accessible.name:"Close setup guide"; onClicked:guide.close() }
        }
        RowLayout {
            spacing: 8
            Repeater {
                model: guide.steps.length
                ActionButton {
                    required property int index
                    text:String(index + 1); primary:guide.step === index
                    implicitWidth:36
                    Accessible.name:"Step " + (index + 1) + ": " + guide.steps[index].title
                    onClicked:guide.step=index
                }
            }
            Item { Layout.fillWidth:true }
            Text { text:"Step " + (guide.step + 1) + " of " + guide.steps.length; color:"#8e9baa"; font.pixelSize:12 }
        }
        Item {
            id: body
            Layout.fillWidth:true; Layout.fillHeight:true; Layout.minimumHeight:0
            Flickable {
                id: scroll
                objectName:"setupGuideScroll"
                anchors.fill:parent
                anchors.rightMargin:contentHeight > height + 1 ? 16 : 0
                contentWidth:width; contentHeight:content.implicitHeight
                interactive:contentHeight > height + 1; clip:true; boundsBehavior:Flickable.StopAtBounds
                onContentHeightChanged:contentY=0
                Connections { target:guide; function onStepChanged() { scroll.contentY=0 } }
                ScrollBar.vertical: ScrollBar { parent:body; x:body.width-width; width:6; height:scroll.height; visible:scroll.interactive }
                ColumnLayout {
                    id:content
                    width:scroll.width; spacing:14
                    Text { text:guide.page.title; color:"#eef2f7"; font.pixelSize:17; font.weight:Font.DemiBold; wrapMode:Text.WordWrap; Layout.fillWidth:true }
                    Text { text:guide.page.body; textFormat:Text.PlainText; color:"#d0d9e3"; font.pixelSize:13; lineHeight:1.3; wrapMode:Text.WordWrap; Layout.fillWidth:true }
                    Text {
                        readonly property var otherMappings: guide.mappings.filter(m => m.mappingEnabled && m.address !== "/midsden/height" && m.address !== "/midsden/scale")
                        visible: guide.appId === "resonite" && guide.step === 1 && otherMappings.length > 0
                        text: "For your other mappings, use the paths below. Add an OSC_Value<float> for decimals or OSC_Value<int> for whole numbers and on/off values.\n\n"
                            + otherMappings.map(m => m.name + " → " + m.address + " · " + (m.kind === "bool" ? "int (0/1)" : m.kind)).join("\n")
                        textFormat: Text.PlainText; color: "#dfc48d"; font.pixelSize: 12
                        wrapMode: Text.Wrap; Layout.fillWidth: true
                    }
                    Text { text:guide.page.tip; textFormat:Text.PlainText; color:"#93a4b7"; font.pixelSize:12; lineHeight:1.25; wrapMode:Text.WordWrap; Layout.fillWidth:true }
                }
            }
        }
        Rectangle { Layout.fillWidth:true; height:1; color:"#303b4a" }
        RowLayout {
            Layout.fillWidth:true; spacing:8
            ActionButton { text:"Official reference ↗"; quiet:true; onClicked:Qt.openUrlExternally(guide.page.url) }
            Item { Layout.fillWidth:true }
            ActionButton { objectName:"setupGuideBack"; text:"Back"; quiet:true; enabled:guide.step > 0; onClicked:guide.step-- }
            ActionButton { objectName:"setupGuideNext"; text:guide.step === guide.steps.length - 1 ? "Done" : "Next"; primary:true; onClicked:{if(guide.step < guide.steps.length - 1) guide.step++; else guide.close()} }
        }
    }
}
