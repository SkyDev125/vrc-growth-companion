import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Window

ApplicationWindow {
    id: window
    objectName: "companionWindow"
    visible: true
    width: 960; height: 640
    minimumWidth: 820; minimumHeight: 600
    color: "transparent"
    flags: Qt.Window | Qt.FramelessWindowHint
    title: "Mid’s Den · Companion"
    font.family: Qt.platform.os === "windows" ? "Segoe UI" : Qt.platform.os === "osx" ? "SF Pro Display" : "DejaVu Sans"
    font.pixelSize: 13
    property var state: JSON.parse(bridge.stateJson)
    property var editorData: ({})
    property var draft: ({})
    property string editError: ""
    property string connectionError: ""
    property int draftIndex: -1
    ListModel { id: mappingModel }
    function updateState() {
        state = JSON.parse(bridge.stateJson)
        if (mappingModel.count !== state.rows.length) {
            mappingModel.clear()
            for (var row of state.rows) mappingModel.append(row)
        } else {
            for (var i = 0; i < state.rows.length; ++i) mappingModel.set(i, state.rows[i])
        }
        if (editor.visible && editorData.profile !== state.profile) editError = "Avatar changed. Reopen this mapping before saving."
    }
    function loadEditor() {
        editorData = JSON.parse(bridge.editorJson)
        if (!editorData.item) return
        draft = editorData.item
        draftIndex = editorData.index
        editError = ""
        var sourceOptions = editorData.sources.map(s => ({label:s.name + " · " + s.unit, value:s.id}))
        sourceSelect.model = sourceOptions
        sourceSelect.currentIndex = sourceOptions.findIndex(s => s.value === draft.source)
        parameter.parameters = editorData.parameters
        parameter.setAddress(draft.target)
        kindSelect.currentIndex = ["float","int","bool"].indexOf(draft.kind)
        modeSelect.currentIndex = ["value","ratio","range","threshold"].indexOf(draft.mode)
        inMin.text = String(draft.inputMin === undefined ? 0 : draft.inputMin)
        inMax.text = String(draft.inputMax === undefined ? 10 : draft.inputMax)
        outMin.text = String(draft.outputMin === undefined ? 0 : draft.outputMin)
        outMax.text = String(draft.outputMax === undefined ? 1 : draft.outputMax)
        threshold.text = String(draft.threshold === undefined ? 1 : draft.threshold)
        enabledToggle.checked = draft.enabled !== false
        editor.open()
    }
    function saveEditor() {
        var item = {source:sourceSelect.currentValue || "",target:parameter.address,
            kind:kindSelect.currentValue,mode:modeSelect.currentValue,enabled:enabledToggle.checked,
            inputMin:inMin.text,inputMax:inMax.text,outputMin:outMin.text,outputMax:outMax.text,threshold:threshold.text}
        editError = bridge.saveMapping(JSON.stringify(item))
        if (!editError) editor.close()
    }
    Component.onCompleted: updateState()
    Connections { target: bridge; function onStateChanged() { window.updateState() } function onEditorChanged() { window.loadEditor() } }
    component SmallText: Text { color: "#8e9baa"; font.pixelSize: 11; elide: Text.ElideRight }
    component FieldLabel: Text { color: "#acb8c5"; font.pixelSize: 12; Layout.fillWidth: true }
    component Toggle: Switch {
        id: toggle
        implicitWidth: 34; implicitHeight: 24
        padding: 0
        indicator: Rectangle {
            width: 34; height: 20; y: 2; radius: 10
            color: toggle.checked ? "#d8bc83" : "#354151"
            Behavior on color { ColorAnimation { duration: 120 } }
            Rectangle {
                x: toggle.checked ? 17 : 3; y: 3; width: 14; height: 14; radius: 7
                color: toggle.checked ? "#262118" : "#c0cbd7"
                Behavior on x { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
            }
        }
    }
    Rectangle {
        anchors.fill: parent; color: "#0f151e"; radius: window.visibility === Window.Maximized ? 0 : 14; border.color: "#2c3746"
        ColumnLayout {
            anchors.fill: parent; anchors.margins: 1; spacing: 0
            Item {
                Layout.fillWidth: true; Layout.preferredHeight: 34
                MouseArea { anchors.fill: parent; onPressed: window.startSystemMove(); onDoubleClicked: window.visibility === Window.Maximized ? window.showNormal() : window.showMaximized() }
                RowLayout {
                    anchors.fill: parent; anchors.leftMargin: 16; anchors.rightMargin: 5
                    SmallText { text: "MID’S DEN / COMPANION"; color: "#8190a3"; font.pixelSize: 10; font.letterSpacing: 1 }
                    Item { Layout.fillWidth: true }
                    ActionButton { text: "−"; quiet: true; width: 36; height: 26; onClicked: window.showMinimized(); Accessible.name: "Minimize" }
                    ActionButton { text: "□"; quiet: true; width: 36; height: 26; onClicked: window.visibility === Window.Maximized ? window.showNormal() : window.showMaximized(); Accessible.name: "Maximize or restore" }
                    ActionButton { text: "×"; quiet: true; danger: true; width: 36; height: 26; onClicked: window.close(); Accessible.name: "Close companion" }
                }
            }
            ColumnLayout {
                Layout.fillWidth: true; Layout.fillHeight: true
                Layout.leftMargin: 24; Layout.rightMargin: 24; Layout.bottomMargin: 14
                spacing: 18
                RowLayout {
                    Layout.fillWidth: true; spacing: 12
                    Image { source: "app-icon.svg"; sourceSize.width: 44; sourceSize.height: 44; Layout.preferredWidth: 44; Layout.preferredHeight: 44; smooth: true }
                    ColumnLayout {
                        spacing: 3
                        Text { text: "Mid’s Den"; color: "#f0f3f7"; font.pixelSize: 21; font.weight: Font.DemiBold }
                        SmallText { text: "VRChat companion" }
                    }
                    Item { Layout.fillWidth: true }
                    ActionButton { text: "Resend"; quiet: true; enabled: !window.state.paused; onClicked: bridge.resend(); ToolTip.visible: hovered; ToolTip.text: "Apply the current values once again" }
                    ActionButton { text: "Settings"; quiet: true; onClicked: { hostInput.text = window.state.host; portInput.text = String(window.state.port); window.connectionError = ""; settings.open() } }
                    ActionButton { text: window.state.paused ? "Resume" : "Pause"; onClicked: bridge.toggleRun() }
                }
                Rectangle {
                    Layout.fillWidth: true; Layout.preferredHeight: 39
                    radius: 10; color: "#17222c"; border.color: "#263947"
                    RowLayout {
                        anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12; spacing: 9
                        Rectangle { width: 6; height: 6; radius: 3; color: window.state.paused ? "#dfc48d" : window.state.detected ? "#83c7b4" : "#8795a5"; Behavior on color { ColorAnimation { duration: 160 } } }
                        Text { text: window.state.paused ? "Paused" : window.state.detected ? "VRChat detected" : "Waiting for VRChat"; color: "#c6d6df"; font.pixelSize: 12; font.weight: Font.Medium }
                        SmallText { text: window.state.profile === "manual" ? "Shared mappings" : "Avatar · " + window.state.profile.slice(-8); Layout.leftMargin: 9 }
                        Item { Layout.fillWidth: true }
                        SmallText { text: window.state.sourceCount + " measurements" }
                    }
                }
                Rectangle {
                    Layout.fillWidth: true; Layout.fillHeight: true; radius: 14
                    color: "#151d28"; border.color: "#2b3544"
                    ColumnLayout {
                        anchors.fill: parent; spacing: 0
                        RowLayout {
                            Layout.fillWidth: true; Layout.margins: 14; spacing: 8
                            Text { text: "Mappings"; color: "#e8edf3"; font.pixelSize: 15; font.weight: Font.DemiBold }
                            Rectangle { width: countText.width + 14; height: 22; radius: 6; color: "#283343"; Text { id: countText; anchors.centerIn: parent; text: mappingModel.count; color: "#b8c4d1"; font.pixelSize: 11 } }
                            Item { Layout.fillWidth: true }
                            MenuButton { id: presetsButton; text: "Presets"; quiet: true; expanded: presets.visible; onClicked: presets.visible ? presets.close() : presets.open() }
                            ActionButton { text: "+ New mapping"; primary: true; onClicked: bridge.openEditor(-1) }
                        }
                        Rectangle { Layout.fillWidth: true; height: 1; color: "#293443" }
                        RowLayout {
                            Layout.fillWidth: true; Layout.leftMargin: 62; Layout.rightMargin: 118; spacing: 12; Layout.topMargin: 10; Layout.bottomMargin: 5
                            SmallText { text: "MEASUREMENT"; font.pixelSize: 9; font.letterSpacing: 1; Layout.preferredWidth: 200 }
                            SmallText { text: "AVATAR PARAMETER"; font.pixelSize: 9; font.letterSpacing: 1; Layout.fillWidth: true }
                            SmallText { text: "OUTPUT"; font.pixelSize: 9; font.letterSpacing: 1; Layout.preferredWidth: 74; horizontalAlignment: Text.AlignRight }
                        }
                        ListView {
                            id: mappings
                            objectName: "mappingList"
                            Layout.fillWidth: true; Layout.fillHeight: true
                            clip: true; model: mappingModel; boundsBehavior: Flickable.StopAtBounds
                            ScrollBar.vertical: ScrollBar { }
                            delegate: Rectangle {
                                id: row
                                required property int index
                                required property string name
                                required property string value
                                required property string target
                                required property string mode
                                required property string kind
                                required property string output
                                required property string health
                                required property bool mappingEnabled
                                width: mappings.width; height: 68
                                color: hover.hovered ? "#1c2837" : "transparent"
                                Behavior on color { ColorAnimation { duration: 120 } }
                                HoverHandler { id: hover }
                                RowLayout {
                                    anchors.fill: parent; anchors.leftMargin: 16; anchors.rightMargin: 12; spacing: 12
                                    Toggle { checked: row.mappingEnabled; onToggled: bridge.enableMapping(row.index,checked); Accessible.name: "Enable " + row.name }
                                    ColumnLayout {
                                        Layout.preferredWidth: 200; Layout.minimumWidth: 200; Layout.maximumWidth: 200; spacing: 5
                                        Text { text: row.name; color: row.mappingEnabled ? "#e8edf3" : "#8995a5"; font.pixelSize: 13; font.weight: Font.Medium; elide: Text.ElideRight; Layout.fillWidth: true }
                                        SmallText { text: row.value; font.family: "monospace" }
                                    }
                                    ColumnLayout {
                                        Layout.fillWidth: true; spacing: 5
                                        Text { text: row.target; color: row.mappingEnabled ? "#d9e2ec" : "#8995a5"; font.pixelSize: 13; elide: Text.ElideMiddle; Layout.fillWidth: true }
                                        SmallText { text: row.mode + " · " + row.kind }
                                    }
                                    Rectangle {
                                        Layout.preferredWidth: 74; height: 28; radius: 7
                                        color: row.health === "ready" ? "#21312f" : "#26303d"
                                        Text { anchors.fill: parent; anchors.margins: 5; text: row.output; color: row.health === "ready" ? "#a8d4c3" : "#aab5c3"; font.pixelSize: 12; font.family: "monospace"; elide: Text.ElideRight; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                                        ToolTip.visible: outputHover.hovered; ToolTip.text: "Calculated OSC value; delivery is not acknowledged"
                                        HoverHandler { id: outputHover }
                                    }
                                    ActionButton { text: "Edit"; quiet: true; onClicked: bridge.openEditor(row.index) }
                                    ActionButton { text: "×"; quiet: true; danger: true; implicitWidth: 30; onClicked: bridge.removeMapping(row.index); Accessible.name: "Remove " + row.name }
                                }
                                Rectangle { anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.leftMargin: 16; anchors.right: parent.right; height: 1; color: "#222d3b" }
                            }
                            Label { visible: mappingModel.count === 0; anchors.centerIn: parent; text: "No mappings yet. Add one or choose a preset."; color: "#8e9baa"; font.pixelSize: 13 }
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    SmallText { text: window.state.status; Layout.fillWidth: true }
                    SmallText { text: "Checks every 5s · sends changes only" }
                }
            }
        }
        MouseArea { anchors.right: parent.right; anchors.bottom: parent.bottom; width: 12; height: 12; cursorShape: Qt.SizeFDiagCursor; onPressed: window.startSystemResize(Qt.RightEdge | Qt.BottomEdge) }
    }
    Popup {
        id: presets
        parent: presetsButton
        x: presetsButton.width - width; y: presetsButton.height + 6; width: 190; padding: 6
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutsideParent
        background: Rectangle { radius: 10; color: "#202c3a"; border.color: "#3a485a" }
        contentItem: ActionButton { text: "Eye height"; quiet: true; onClicked: { presets.close(); bridge.eyeHeightPreset() } }
    }
    Popup {
        id: editor
        objectName: "mappingEditor"
        parent: window.contentItem
        anchors.centerIn: parent
        width: Math.min(610, window.width - 48)
        height: Math.min(editorLayout.implicitHeight + 48, window.height - 40)
        padding: 24
        modal: true; focus: true
        closePolicy: Popup.CloseOnEscape
        background: Rectangle { radius: 18; color: "#18212d"; border.color: "#405067" }
        Overlay.modal: Rectangle { color: "#a6080d15"; Behavior on opacity { NumberAnimation { duration: 140 } } }
        enter: Transition { ParallelAnimation { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 140 } NumberAnimation { property: "scale"; from: .97; to: 1; duration: 160; easing.type: Easing.OutCubic } } }
        contentItem: ColumnLayout {
            id: editorLayout
            spacing: 16
            RowLayout {
                id: editorHeader
                objectName: "editorHeader"
                Layout.fillWidth: true; Layout.fillHeight: false
                ColumnLayout {
                    spacing: 4
                    Text { text: window.draftIndex >= 0 ? "Edit mapping" : "New mapping"; color: "#eef2f7"; font.pixelSize: 20; font.weight: Font.DemiBold }
                    SmallText { text: "Connect a measurement to your avatar." }
                }
                Item { Layout.fillWidth: true }
                ActionButton { text: "×"; quiet: true; onClicked: editor.close(); Accessible.name: "Close mapping editor" }
            }
            ScrollView {
                id: editorScroll
                objectName: "editorFieldsScroll"
                Layout.fillWidth: true; Layout.fillHeight: true
                Layout.minimumHeight: 0
                implicitHeight: editorFields.implicitHeight
                clip: true
                contentWidth: availableWidth
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                ColumnLayout {
                    id: editorFields
                    width: editorScroll.availableWidth
                    spacing: 16
            GridLayout {
                columns: 2; rowSpacing: 7; columnSpacing: 14; Layout.fillWidth: true
                FieldLabel { text: "Measurement" }
                FieldLabel { text: "Avatar parameter" }
                SelectField { id: sourceSelect; Layout.preferredWidth: 175; Layout.fillWidth: true; model: [] }
                ParameterPicker {
                    id: parameter
                    Layout.preferredWidth: 340; Layout.fillWidth: true
                    onSelected: function(address,kind) {
                        kindSelect.currentIndex = ["float","int","bool"].indexOf(kind)
                        if (address === "/avatar/eyeheight") {
                            sourceSelect.currentIndex = sourceSelect.model.findIndex(s => s.value === "height")
                            modeSelect.currentIndex = 0
                        } else if (kind === "bool") modeSelect.currentIndex = 3
                    }
                }
                FieldLabel { text: "Value type"; Layout.topMargin: 6 }
                FieldLabel { text: "Send as"; Layout.topMargin: 6 }
                SelectField {
                    id: kindSelect; Layout.fillWidth: true
                    model: [{label:"Decimal",value:"float"},{label:"Whole number",value:"int"},{label:"On / off",value:"bool"}]
                    onActivated: { if (currentValue === "bool") modeSelect.currentIndex = 3; else if (modeSelect.currentIndex === 3) modeSelect.currentIndex = 2 }
                }
                SelectField {
                    id: modeSelect; Layout.fillWidth: true
                    model: [{label:"Current value",value:"value"},{label:"Growth ratio",value:"ratio"},{label:"Map a range",value:"range"},{label:"On / off threshold",value:"threshold"}]
                }
            }
            Rectangle {
                Layout.fillWidth: true; implicitHeight: rangeGrid.implicitHeight + 24; radius: 10; color: "#111a24"; border.color: "#293747"
                visible: modeSelect.currentValue === "range" || modeSelect.currentValue === "threshold"
                GridLayout {
                    id: rangeGrid
                    anchors.fill: parent; anchors.margins: 12; columns: 2; rowSpacing: 6; columnSpacing: 12
                    FieldLabel { text: "Measurement from"; visible: modeSelect.currentValue === "range" }
                    FieldLabel { text: "Measurement to"; visible: modeSelect.currentValue === "range" }
                    InputField { id: inMin; Layout.fillWidth: true; visible: modeSelect.currentValue === "range" }
                    InputField { id: inMax; Layout.fillWidth: true; visible: modeSelect.currentValue === "range" }
                    FieldLabel { text: "Parameter from"; visible: modeSelect.currentValue === "range" }
                    FieldLabel { text: "Parameter to"; visible: modeSelect.currentValue === "range" }
                    InputField { id: outMin; Layout.fillWidth: true; visible: modeSelect.currentValue === "range" }
                    InputField { id: outMax; Layout.fillWidth: true; visible: modeSelect.currentValue === "range" }
                    FieldLabel { text: "Turn on at"; Layout.columnSpan: 2; visible: modeSelect.currentValue === "threshold" }
                    InputField { id: threshold; Layout.fillWidth: true; Layout.columnSpan: 2; visible: modeSelect.currentValue === "threshold" }
                }
            }
            Text {
                Layout.fillWidth: true; wrapMode: Text.WordWrap; color: "#92a2b5"; font.pixelSize: 12
                property string unit: sourceSelect.currentIndex >= 0 && window.editorData.sources ? window.editorData.sources[sourceSelect.currentIndex].unit : "saved units"
                text: modeSelect.currentValue === "ratio" ? "Current ÷ starting amount. 1 means the original size." : modeSelect.currentValue === "range" ? "Maps the measurement range in " + unit + " to the avatar’s range, with limits." : modeSelect.currentValue === "threshold" ? "Turns on at or above the amount in " + unit + "." : "Sends the current amount in " + unit + "."
            }
                }
            }
            Text { text: window.editError; color: "#f1a49c"; visible: text.length > 0; wrapMode: Text.WordWrap; Layout.fillWidth: true; font.pixelSize: 12 }
            Rectangle { Layout.fillWidth: true; height: 1; color: "#303b4a" }
            RowLayout {
                id: editorFooter
                objectName: "editorFooter"
                Layout.fillWidth: true; Layout.fillHeight: false; spacing: 8
                Toggle { id: enabledToggle; Accessible.name: "Mapping enabled" }
                SmallText { text: enabledToggle.checked ? "Enabled" : "Disabled" }
                Item { Layout.fillWidth: true }
                ActionButton { text: "Cancel"; quiet: true; onClicked: editor.close() }
                ActionButton { objectName: "saveMapping"; text: "Save mapping"; primary: true; onClicked: window.saveEditor() }
            }
        }
    }
    Popup {
        id: settings
        anchors.centerIn: parent; width: 410; padding: 24; modal: true; focus: true
        closePolicy: Popup.CloseOnEscape
        background: Rectangle { radius: 18; color: "#18212d"; border.color: "#405067" }
        Overlay.modal: Rectangle { color: "#a6080d15" }
        contentItem: ColumnLayout {
            spacing: 12
            Text { text: "Connection settings"; color: "#eef2f7"; font.pixelSize: 20; font.weight: Font.DemiBold }
            FieldLabel { text: "VRChat IP address" }
            InputField { id: hostInput; Layout.fillWidth: true }
            FieldLabel { text: "OSC receive port" }
            InputField { id: portInput; Layout.fillWidth: true }
            Text { text: window.connectionError; color: "#f1a49c"; visible: text.length > 0; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                ActionButton { text: "Cancel"; quiet: true; onClicked: settings.close() }
                ActionButton { text: "Save connection"; primary: true; onClicked: { window.connectionError = bridge.saveConnection(hostInput.text,portInput.text); if (!window.connectionError) settings.close() } }
            }
        }
    }
}
