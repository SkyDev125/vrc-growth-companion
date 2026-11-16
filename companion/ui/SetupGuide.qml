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
        {title:"Create a receiver", body:"In Resonite, add an OSC_Receiver to a slot on your avatar. Set HandlingUser to the wearer, Port to " + port + " and AccessReason to Mid’s Den growth. Allow OSC receiving when prompted.", tip:"Saved destination · " + host + ":" + port, url:"https://wiki.resonite.com/Component:OSC_Receiver"},
        {title:"Connect a measurement", body:"Create a mapping in the companion. In Resonite, add OSC_Value<float> for a decimal value, or OSC_Value<int> for a whole number or on/off value. Set Handler to your receiver, Path to the mapping’s exact receiver path, and ArgumentIndex to 0.", tip:"Wire Value to the avatar field or ProtoFlux you want to control. On/off values arrive as 0 or 1.", url:"https://wiki.resonite.com/Component:OSC_Value"},
        {title:"Calibrate avatar scale", body:"For Presets → Avatar scale, first match your avatar to the website’s starting height. Store User Root Global Scale once as BaselineScale.\n\nTarget scale = BaselineScale × received /midsden/scale\n\nApply it with Set User Scale, the wearer’s UserRoot and AnimationTime = 0. Only the wearer should execute it; ignore zero or negative received values.", tip:"Keep the baseline fixed during growth. Recalibrate for a different avatar or baseline; multiplying the live scale would compound growth. Skip this step for other measurements.", url:"https://wiki.resonite.com/ProtoFlux:SetUserScale"},
        {title:"Check it in-world", body:"OSC_Receiver.IsListening should be true. Use Resend in the companion and watch OSC_Value.Value change in-world. If the value arrives but nothing moves, check the field or ProtoFlux connection.", tip:"Resonite does not acknowledge UDP delivery. Resend after reloading a receiver or changing worlds; settled values are not repeatedly sent.", url:"https://wiki.resonite.com/OSC"}
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
                    Text { visible:guide.appId === "resonite" && guide.step === 1 && guide.mappings.length > 0; text:guide.mappings.map(m => m.name + " → " + m.address + " · " + (m.kind === "bool" ? "int (0/1)" : m.kind)).join("\n"); textFormat:Text.PlainText; color:"#dfc48d"; font.pixelSize:12; wrapMode:Text.WrapAnywhere; Layout.fillWidth:true }
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
