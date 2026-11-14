import QtQuick
import QtQuick.Controls.Basic
ComboBox {
    id: control
    implicitHeight: 40
    textRole: "label"
    valueRole: "value"
    font.pixelSize: 13
    leftPadding: 12
    rightPadding: 34
    contentItem: Text {
        text: control.displayText
        color: "#e5ebf0"
        font: control.font
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    indicator: Text {
        x: control.width - 26; y: (control.height - height) / 2
        text: "⌄"; color: "#b7c3d0"; font.pixelSize: 17
    }
    background: Rectangle {
        radius: 9; color: control.hovered ? "#202b38" : "#161e28"
        border.color: control.activeFocus ? "#ceb37f" : "#303b49"
        Behavior on color { ColorAnimation { duration: 120 } }
    }
    delegate: ItemDelegate {
        id: entry
        required property int index
        required property var modelData
        width: control.width - 12; height: 36
        highlighted: control.highlightedIndex === index
        contentItem: Text { text: entry.modelData.label; color: "#e5ebf0"; font.pixelSize: 13; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
        background: Rectangle { radius: 6; color: entry.highlighted || entry.hovered ? "#2b394a" : "transparent" }
    }
    popup: Popup {
        y: control.height + 5; width: control.width; padding: 6
        implicitHeight: Math.min(260, contentItem.implicitHeight + 12)
        background: Rectangle { color: "#1c2633"; radius: 11; border.color: "#3b4a5c" }
        contentItem: ListView {
            clip: true; implicitHeight: contentHeight
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
            ScrollIndicator.vertical: ScrollIndicator {}
        }
        enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 100 } }
    }
}
