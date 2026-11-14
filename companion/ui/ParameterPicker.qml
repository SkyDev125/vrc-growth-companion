import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Item {
    id: picker
    implicitHeight: 40
    property var parameters: []
    property string address: ""
    property string selectedKind: "float"
    property bool browsingAll: false
    property bool setting: false
    property var filtered: []
    signal selected(string address, string kind)
    function setAddress(value) {
        setting = true
        address = value
        var found = parameters.find(p => p.address === value)
        input.text = found ? found.name : value
        setting = false
    }
    function filter() {
        var query = browsingAll ? "" : input.text.toLowerCase()
        filtered = parameters.filter(p => p.name.toLowerCase().includes(query) || p.address.toLowerCase().includes(query))
        list.currentIndex = -1
    }
    function choose(index) {
        var entry = filtered[index]
        if (!entry || !entry.writable) return
        setAddress(entry.address)
        selectedKind = entry.kind
        selected(entry.address, entry.kind)
        popup.close()
        input.forceActiveFocus()
    }
    onParametersChanged: filter()
    InputField {
        id: input
        objectName: "parameterSearch"
        anchors.fill: parent
        rightPadding: 42
        placeholderText: "Search or enter a parameter"
        onTextEdited: {
            picker.address = text
            picker.browsingAll = false
            picker.filter()
            popup.open()
            forceActiveFocus()
        }
        Keys.onDownPressed: {
            if (!popup.visible) { picker.browsingAll = text.length === 0; picker.filter(); popup.open() }
            for (var i = list.currentIndex + 1; i < picker.filtered.length; ++i) if (picker.filtered[i].writable) { list.currentIndex = i; break }
        }
        Keys.onUpPressed: {
            for (var i = list.currentIndex - 1; i >= 0; --i) if (picker.filtered[i].writable) { list.currentIndex = i; break }
        }
        Keys.onReturnPressed: { if (popup.visible && list.currentIndex >= 0) picker.choose(list.currentIndex); else popup.close() }
        Keys.onEnterPressed: { if (popup.visible && list.currentIndex >= 0) picker.choose(list.currentIndex); else popup.close() }
        Keys.onEscapePressed: if (popup.visible) popup.close()
    }
    ActionButton {
        objectName: "parameterDropdown"
        anchors.right: parent.right; anchors.rightMargin: 3; anchors.verticalCenter: parent.verticalCenter
        width: 34; height: 34; quiet: true; text: "⌄"
        Accessible.name: "Browse avatar parameters"
        onClicked: {
            if (popup.visible) popup.close()
            else { picker.browsingAll = true; picker.filter(); popup.open(); input.forceActiveFocus() }
        }
    }
    Popup {
        id: popup
        parent: picker
        y: picker.height + 6; width: picker.width
        height: Math.min(300, Math.max(86, list.contentHeight + 44))
        padding: 6
        focus: false
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutsideParent
        background: Rectangle { color: "#1b2633"; radius: 12; border.color: "#3a495b" }
        contentItem: ColumnLayout {
            spacing: 4
            Text { text: picker.browsingAll ? "AVATAR PARAMETERS" : "SEARCH RESULTS"; color: "#8c9bac"; font.pixelSize: 10; font.weight: Font.DemiBold; Layout.leftMargin: 8; Layout.topMargin: 4 }
            ListView {
                id: list
                objectName: "parameterResults"
                Layout.fillWidth: true; Layout.fillHeight: true
                model: picker.filtered; clip: true
                ScrollBar.vertical: ScrollBar {}
                delegate: ItemDelegate {
                    id: row
                    required property int index
                    required property var modelData
                    width: list.width; height: 36
                    enabled: modelData.writable
                    contentItem: RowLayout {
                        Text { text: row.modelData.name; color: row.enabled ? "#e4ebf1" : "#7e8c9c"; font.pixelSize: 13; elide: Text.ElideMiddle; Layout.fillWidth: true }
                        Text { text: row.enabled ? row.modelData.kind : "read-only"; color: "#91a0b0"; font.pixelSize: 11 }
                    }
                    background: Rectangle { radius: 7; color: row.hovered || list.currentIndex === row.index ? "#304055" : "transparent" }
                    onClicked: picker.choose(index)
                }
            }
            Text { visible: picker.filtered.length === 0; text: "No matches. You can enter an exact parameter name."; color: "#a4b0bd"; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true }
        }
        enter: Transition { ParallelAnimation { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 110 } NumberAnimation { property: "scale"; from: .98; to: 1; duration: 110 } } }
    }
}
