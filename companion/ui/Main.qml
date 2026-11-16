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
    color: "#0f151e"
    flags: Qt.Window | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint
    title: "Mid’s Den · Companion"
    font.family: Qt.platform.os === "windows" ? "Segoe UI" : Qt.platform.os === "osx" ? "SF Pro Display" : "DejaVu Sans"
    font.pixelSize: 13
    property var state: JSON.parse(bridge.stateJson)
    property var editorData: ({})
    property var draft: ({})
    property string editError: ""
    property string connectionError: ""
    property string growthError: ""
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
        else if (editor.visible) {
            var latest = JSON.parse(bridge.editorJson)
            if (JSON.stringify(parameter.parameters) !== JSON.stringify(latest.parameters)) parameter.parameters = latest.parameters || []
        }
    }
    function saveGrowth(key,value) {
        var options=Object.assign({},state.growthOptions)
        options[key]=value
        growthError=bridge.saveGrowthOptions(JSON.stringify(options))
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
        smoothMapping.checked = draft.smooth !== undefined ? draft.smooth : !!((draft.target === "/avatar/eyeheight" || draft.target === "/midsden/scale") || (editorData.sources[sourceSelect.currentIndex] || {}).syncTarget && editorData.sources[sourceSelect.currentIndex].syncTarget !== "none")
        editor.open()
    }
    function saveEditor() {
        var item = {source:sourceSelect.currentValue || "",target:parameter.address,
            kind:kindSelect.currentValue,mode:modeSelect.currentValue,platform:window.editorData.platform || 'vrchat',enabled:enabledToggle.checked,smooth:smoothMapping.checked,
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
        anchors.fill: parent; color: "#0f151e"; radius: 0; border.width: 0
        ColumnLayout {
            anchors.fill: parent; anchors.margins: 1; spacing: 0
            ColumnLayout {
                Layout.fillWidth: true; Layout.fillHeight: true
                Layout.leftMargin: 24; Layout.rightMargin: 24; Layout.topMargin: 18; Layout.bottomMargin: 14
                spacing: 18
                RowLayout {
                    Layout.fillWidth: true; spacing: 12
                    Image { source: "app-icon.svg"; sourceSize.width: 44; sourceSize.height: 44; Layout.preferredWidth: 44; Layout.preferredHeight: 44; smooth: true }
                    ColumnLayout {
                        spacing: 3
                        Text { text: "Mid’s Den"; color: "#f0f3f7"; font.pixelSize: 21; font.weight: Font.DemiBold }
                        SmallText { text: window.state.targetName + " companion" }
                    }
                    Item { Layout.fillWidth: true }
                    ActionButton { text: "Resend"; quiet: true; enabled: !window.state.paused; onClicked: bridge.resend(); ToolTip.visible: hovered; ToolTip.text: "Apply the current values once again" }
                    ActionButton { objectName: "connectionSettings"; text: "Settings"; quiet: true; onClicked: { hostInput.text = window.state.host; portInput.text = String(window.state.port); window.connectionError = ""; settings.open() } }
                    ActionButton { text: window.state.paused ? "Resume" : "Pause"; onClicked: bridge.toggleRun() }
                }
                Rectangle {
                    visible: window.state.update.available || window.state.update.busy
                    Layout.fillWidth: true; implicitHeight: 54
                    radius: 10; color: "#273027"; border.color: "#48513d"
                    RowLayout {
                        anchors.fill: parent; anchors.margins: 10; spacing: 12
                        Text { text: window.state.update.message + (window.state.update.progress >= 0 ? " " + window.state.update.progress + "%" : ""); color: "#dfe7d5"; font.pixelSize: 12; Layout.fillWidth: true; elide: Text.ElideRight }
                        ActionButton { objectName: "installUpdate"; text: "Update & restart"; primary: true; enabled: !window.state.update.busy; onClicked: bridge.installUpdate() }
                    }
                }
                Rectangle {
                    Layout.fillWidth: true; Layout.preferredHeight: 39
                    radius: 10; color: "#17222c"; border.color: "#263947"
                    RowLayout {
                        anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12; spacing: 9
                        Rectangle { width: 6; height: 6; radius: 3; color: window.state.paused ? "#dfc48d" : window.state.detected ? "#83c7b4" : "#8795a5"; Behavior on color { ColorAnimation { duration: 160 } } }
                        Text { text: window.state.paused ? "Paused" : window.state.targetApp === "resonite" ? "Resonite OSC · receiver unverified" : window.state.detected ? window.state.targetName + " detected" : "Waiting for " + window.state.targetName; color: "#c6d6df"; font.pixelSize: 12; font.weight: Font.Medium }
                        SmallText { text: window.state.targetApp === "resonite" ? "Resonite mappings" : (window.state.profile === "manual" || window.state.profile === "chilloutvr:manual") ? "Shared mappings" : "Avatar · " + window.state.profile.slice(-8); Layout.leftMargin: 9 }
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
                            SmallText { text: window.state.targetApp === "resonite" ? "RECEIVER PATH" : "AVATAR PARAMETER"; font.pixelSize: 9; font.letterSpacing: 1; Layout.fillWidth: true }
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
                    SmallText { text: window.state.motion.active ? "Growing…" : window.state.status; Layout.fillWidth: true }
                    ActionButton { objectName:"finishGrowth"; text:"Finish now"; quiet:true; visible:window.state.motion.active; onClicked:bridge.finishGrowth() }
                    SmallText { text: "Checks every 5s · sends changes only" }
                }
            }
        }
    }
    Popup {
        id: presets
        parent: presetsButton
        x: presetsButton.width - width; y: presetsButton.height + 6; width: 190; padding: 6
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutsideParent
        background: Rectangle { radius: 10; color: "#202c3a"; border.color: "#3a485a" }
        contentItem: ActionButton { text: window.state.targetApp === "chilloutvr" ? "Scale mapping" : window.state.targetApp === "resonite" ? "Avatar scale" : "Eye height"; quiet: true; onClicked: { presets.close(); bridge.eyeHeightPreset() } }
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
                FieldLabel { text: window.state.targetApp === "resonite" ? "Receiver path" : "Avatar parameter" }
                SelectField { id: sourceSelect; Layout.preferredWidth: 175; Layout.fillWidth: true; model: [] }
                ParameterPicker {
                    id: parameter
                    listTitle: window.state.targetApp === "resonite" ? "SUGGESTED RECEIVER PATHS" : "AVATAR PARAMETERS"
                    searchHint: window.state.targetApp === "resonite" ? "Enter an OSC receiver path" : "Search or enter a parameter"
                    Layout.preferredWidth: 340; Layout.fillWidth: true
                    onSelected: function(address,kind) {
                        kindSelect.currentIndex = ["float","int","bool"].indexOf(kind)
                        if (address === "/avatar/eyeheight") {
                            smoothMapping.checked = true
                            sourceSelect.currentIndex = sourceSelect.model.findIndex(s => s.value === "height")
                            modeSelect.currentIndex = 0
                        } else if (address === "/midsden/scale") {
                            sourceSelect.currentIndex=sourceSelect.model.findIndex(s => s.value === "height");modeSelect.currentIndex=1;smoothMapping.checked=true
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
                Toggle { id:smoothMapping; objectName:"smoothMapping"; visible:kindSelect.currentValue === "float"; Accessible.name:"Smooth this mapping" }
                SmallText { text:"Smooth"; visible:kindSelect.currentValue === "float" }
                Item { Layout.fillWidth: true }
                ActionButton { text: "Cancel"; quiet: true; onClicked: editor.close() }
                ActionButton { objectName: "saveMapping"; text: "Save mapping"; primary: true; onClicked: window.saveEditor() }
            }
        }
    }
    Popup {
        id: settings
        objectName: "settingsPopup"
        anchors.centerIn: parent
        width: Math.min(720, window.width - 48)
        height: Math.min(settingsLayout.implicitHeight + 48, window.height - 40)
        padding: 24; modal: true; focus: true
        closePolicy: Popup.CloseOnEscape
        background: Rectangle { radius: 18; color: "#18212d"; border.color: "#405067" }
        Overlay.modal: Rectangle { color: "#a6080d15" }
        contentItem: ColumnLayout {
            id: settingsLayout
            spacing: 18
            RowLayout {
                Layout.fillWidth: true
                Text { text: "Settings"; color: "#eef2f7"; font.pixelSize: 20; font.weight: Font.DemiBold }
                Item { Layout.fillWidth: true }
                ActionButton { text: "×"; quiet: true; onClicked: settings.close(); Accessible.name: "Close settings" }
            }
            Item {
                id: settingsBody
                Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 0
                implicitHeight: settingsFields.implicitHeight
                Flickable {
                    id: settingsScroll
                    objectName: "settingsScroll"
                    anchors.fill: parent
                    anchors.rightMargin: contentHeight > height + 1 ? 16 : 0
                    contentWidth: width; contentHeight: settingsFields.implicitHeight
                    interactive: contentHeight > height + 1
                    boundsBehavior: Flickable.StopAtBounds; clip: true
                    ScrollBar.vertical: ScrollBar {
                        objectName: "settingsScrollbar"
                        parent: settingsBody
                        x: settingsBody.width - width; y: 0; width: 6; height: settingsScroll.height
                        visible: settingsScroll.contentHeight > settingsScroll.height + 1
                    }
                    GridLayout {
                        id: settingsFields
                        width: settingsScroll.width
                        columns: 2; columnSpacing: 28; rowSpacing: 0
                        ColumnLayout {
                            objectName: "growthSettingsColumn"
                            Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.minimumWidth: 285; Layout.alignment: Qt.AlignTop
                            spacing: 12
                            SmallText { text: "GROWTH"; color: "#dfc48d"; font.letterSpacing: 1 }
                            RowLayout {
                                Layout.fillWidth: true
                                FieldLabel { text: "Mode" }
                                SelectField {
                                    objectName: "growthMode"; Layout.preferredWidth: 170
                                    model: [{label:"Instant",value:false},{label:"Smooth",value:true}]
                                    currentIndex: window.state.smoothGrowth ? 1 : 0
                                    onActivated: bridge.setSmoothGrowth(currentValue)
                                }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true; spacing: 10; visible: window.state.smoothGrowth
                                RowLayout {
                                    Layout.fillWidth: true
                                    FieldLabel { text: "Pace" }
                                    SelectField {
                                        objectName: "growthPace"; Layout.preferredWidth: 170
                                        model: [{label:"Very slow · ¼×",value:0.25},{label:"Slow · ½×",value:0.5},{label:"Normal",value:1},{label:"Fast · 2×",value:2},{label:"Very fast · 4×",value:4}]
                                        currentIndex: [0.25,0.5,1,2,4].indexOf(window.state.growthOptions.speed)
                                        onActivated: window.saveGrowth("speed",currentValue)
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    FieldLabel { text: "Curve" }
                                    SelectField {
                                        objectName: "growthCurve"; Layout.preferredWidth: 170
                                        model: [{label:"Gentle",value:"gentle"},{label:"Steady",value:"steady"},{label:"Quick start",value:"quickStart"}]
                                        currentIndex: ["gentle","steady","quickStart"].indexOf(window.state.growthOptions.curve)
                                        onActivated: window.saveGrowth("curve",currentValue)
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    FieldLabel { text: "Maximum duration" }
                                    InputField {
                                        id: growthMaximum; objectName: "growthMaximum"; Layout.preferredWidth: 64
                                        Component.onCompleted: text=String(window.state.growthOptions.maxDuration)
                                        Connections {
                                            target: window
                                            function onStateChanged() {
                                                if (!growthMaximum.activeFocus) growthMaximum.text=String(window.state.growthOptions.maxDuration)
                                            }
                                        }
                                        validator: IntValidator { bottom: 3; top: 120 }
                                        onTextEdited: window.growthError=acceptableInput ? "" : "Use 3–120 seconds."
                                        onEditingFinished: window.saveGrowth("maxDuration",Number(text))
                                    }
                                    SmallText { text: "seconds" }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    SmallText { text: "Changes apply immediately"; Layout.fillWidth: true }
                                    ActionButton { objectName:"resetGrowth"; text:"Reset"; quiet:true; onClicked:{window.growthError=bridge.saveGrowthOptions("{}");growthMaximum.text=String(window.state.growthOptions.maxDuration)} }
                                }
                                Text { text:window.growthError; color:"#f1a49c"; visible:text.length>0; Layout.fillWidth:true; wrapMode:Text.WordWrap; font.pixelSize:12 }
                            }
                        }
                        ColumnLayout {
                            objectName: "connectionSettingsColumn"
                            Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.minimumWidth: 260; Layout.alignment: Qt.AlignTop
                            spacing: 12
                            SmallText { text: "CONNECTION"; color: "#dfc48d"; font.letterSpacing: 1 }
                            RowLayout {
                                Layout.fillWidth:true
                                FieldLabel { text:"App" }
                                SelectField { objectName:"targetApp";Layout.preferredWidth:170
                                    model:[{label:"VRChat",value:"vrchat"},{label:"Resonite",value:"resonite"},{label:"ChilloutVR",value:"chilloutvr"}]
                                    currentIndex:["vrchat","resonite","chilloutvr"].indexOf(window.state.targetApp)
                                    onActivated:{window.connectionError=bridge.setTargetApp(currentValue);hostInput.text=window.state.host;portInput.text=String(window.state.port)}
                                }
                            }
                            RowLayout {
                                Layout.fillWidth:true; spacing:12
                                ColumnLayout {
                                    Layout.fillWidth:true; Layout.minimumWidth:0; spacing:6
                                    FieldLabel { text:"IP address" }
                                    InputField { id:hostInput;objectName:"hostInput";Layout.fillWidth:true;Layout.minimumWidth:0 }
                                }
                                ColumnLayout {
                                    Layout.preferredWidth:88; Layout.minimumWidth:88; Layout.maximumWidth:88; spacing:6
                                    FieldLabel { text:"OSC port" }
                                    InputField { id:portInput;objectName:"portInput";Layout.fillWidth:true;Layout.minimumWidth:0 }
                                }
                            }
                            Text { text:window.connectionError; color:"#f1a49c"; visible:text.length>0; wrapMode:Text.WordWrap; Layout.fillWidth:true; font.pixelSize:12 }
                            RowLayout {
                                Layout.fillWidth: true
                                ActionButton { objectName:"openSetupGuide";text:"Setup guide";quiet:true;onClicked:{settings.close();setupGuide.open()} }
                                Item { Layout.fillWidth: true }
                                ActionButton { objectName:"saveConnection"; text:"Save connection"; primary:true; onClicked:{window.connectionError=bridge.saveConnection(hostInput.text,portInput.text);if(!window.connectionError)settings.close()} }
                            }
                        }
                    }
                }
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: "#303b4a" }
            RowLayout {
                Layout.fillWidth: true
                SmallText { text: "Version " + window.state.update.version; Layout.fillWidth: true }
                ActionButton { objectName:"checkUpdates"; text:"Check updates"; quiet:true; enabled:!window.state.update.busy; onClicked:bridge.checkUpdates() }
                ActionButton { text: "Close"; quiet: true; onClicked: settings.close() }
            }
            Text { text:window.state.update.message; visible:text.length>0; color:"#acb8c5"; wrapMode:Text.WordWrap; Layout.fillWidth:true; font.pixelSize:12 }
        }
    }
    SetupGuide {
        id: setupGuide
        appId: window.state.targetApp
        gameName: window.state.targetName
        host: window.state.host
        port: window.state.port
        mappings: window.state.rows
    }

}
