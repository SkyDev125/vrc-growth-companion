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
    property bool heightHelp: false
    readonly property var activeMappings: mappings.filter(mapping => mapping.mappingEnabled)
    readonly property var heightPage: ({
        "title": "Resize the whole avatar",
        "body": "Use Presets → Avatar height to send your target in metres to /midsden/height. In Resonite, set up the receiver once for your avatar. The setup guide includes a tool to check the avatar’s own eye height and steps for wiring it to the resize graph.",
        "tip": "Use a standing capture if your rig has no verified eye height. In VR, that fallback can reflect headset height.",
        "url": "https://github.com/SkyDev125/vrc-growth-companion/blob/main/companion/RESONITE.md#avatar-height"
    })
    property var steps: appId === "resonite" ? [
        {
            title: "Choose a measurement",
            body: "Select New mapping and pick the measurement you want to use. Keep the suggested receiver path, or enter the path of a receiver you already have. Save the mapping.",
            tip: "Current value sends the number in its website unit. A Tail length of 30 cm sends 30. Use Map a range if the field expects a different range.",
            url: "https://wiki.resonite.com/OSC"
        },
        {
            title: "Receive it in Resonite",
            body: "In the Scene Inspector, add an OSC_Receiver. Set HandlingUser to yourself and Port to " + port + ". Give it an AccessReason and allow OSC receiving when prompted.\n\nAdd an OSC_Value for each measurement. Copy its receiver path into Path, set Handler to the OSC_Receiver and leave ArgumentIndex at 0. Use float for decimals and int for whole numbers or on/off values.",
            tip: "Click Resend and check Value in the inspector. If nothing arrives, check IsListening and the connection at " + host + ":" + port + ".",
            url: "https://wiki.resonite.com/Component:OSC_Value"
        },
        {
            title: "Connect it to a property",
            body: "For a numeric field with the same units, use OSC_Field instead of OSC_Value. Use the same receiver settings and drag the property you want to change into Field. For custom behaviour, read OSC_Value’s Value in ProtoFlux.",
            tip: "On/off values arrive as 0 and 1. In ProtoFlux, compare the value to 1 to get a switch.",
            url: "https://wiki.resonite.com/Component:OSC_Field"
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
    property var page: heightHelp ? heightPage : steps[Math.min(step, steps.length - 1)]
    anchors.centerIn: parent
    width: Math.min(620, parent.width - 48)
    height: Math.min(500, parent.height - 40)
    padding: 24; modal: true; focus: true
    closePolicy: Popup.CloseOnEscape
    onOpened: { step = 0; heightHelp = false }
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
                    text:String(index + 1); primary:!guide.heightHelp && guide.step === index
                    implicitWidth:36
                    Accessible.name:"Step " + (index + 1) + ": " + guide.steps[index].title
                    onClicked:{guide.heightHelp=false; guide.step=index}
                }
            }
            Item { Layout.fillWidth:true }
            Text { text:guide.heightHelp ? "" : "Step " + (guide.step + 1) + " of " + guide.steps.length; color:"#8e9baa"; font.pixelSize:12 }
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
                Connections {
                    target: guide
                    function onStepChanged() { scroll.contentY = 0 }
                    function onHeightHelpChanged() { scroll.contentY = 0 }
                }
                ScrollBar.vertical: ScrollBar { parent:body; x:body.width-width; width:6; height:scroll.height; visible:scroll.interactive }
                ColumnLayout {
                    id:content
                    width:scroll.width; spacing:14
                    Text { text:guide.page.title; color:"#eef2f7"; font.pixelSize:17; font.weight:Font.DemiBold; wrapMode:Text.WordWrap; Layout.fillWidth:true }
                    Text { text:guide.page.body; textFormat:Text.PlainText; color:"#d0d9e3"; font.pixelSize:13; lineHeight:1.3; wrapMode:Text.WordWrap; Layout.fillWidth:true }
                    TextEdit {
                        objectName: "setupReceiverPaths"
                        visible: guide.appId === "resonite" && guide.step === 1 && !guide.heightHelp && guide.activeMappings.length > 0
                        text: guide.activeMappings.map(mapping => mapping.name + " · "
                            + (mapping.kind === "float" ? "float" : "int") + "\n" + mapping.address).join("\n\n")
                        readOnly: true; selectByMouse: true; activeFocusOnTab: visible
                        textFormat: TextEdit.PlainText; color: "#dfc48d"; font.pixelSize: 12
                        selectionColor: "#405067"; selectedTextColor: "#fff"; wrapMode: TextEdit.Wrap
                        Layout.fillWidth: true
                    }
                    Text { text:guide.page.tip; textFormat:Text.PlainText; color:"#93a4b7"; font.pixelSize:12; lineHeight:1.25; wrapMode:Text.WordWrap; Layout.fillWidth:true }
                    ActionButton {
                        objectName: "resoniteHeightHelp"
                        text: "Avatar height setup"
                        visible: guide.appId === "resonite" && guide.step === 2 && !guide.heightHelp
                        onClicked: guide.heightHelp = true
                    }
                }
            }
        }
        Rectangle { Layout.fillWidth:true; height:1; color:"#303b4a" }
        RowLayout {
            Layout.fillWidth:true; spacing:8
            ActionButton { text:guide.heightHelp ? "Height setup guide ↗" : "Official reference ↗"; quiet:true; onClicked:Qt.openUrlExternally(guide.page.url) }
            Item { Layout.fillWidth:true }
            ActionButton { objectName:"setupGuideBack"; text:"Back"; quiet:true; enabled:guide.heightHelp || guide.step > 0; onClicked:{if (guide.heightHelp) guide.heightHelp = false; else guide.step--} }
            ActionButton { objectName:"setupGuideNext"; text:guide.step === guide.steps.length - 1 ? "Done" : "Next"; primary:true; onClicked:{if(guide.step < guide.steps.length - 1) guide.step++; else guide.close()} }
        }
    }
}
