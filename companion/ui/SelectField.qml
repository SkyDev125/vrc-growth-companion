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
    indicator: Item {
        x: control.width - 36; y: 0; width: 36; height: control.height
        Chevron { anchors.centerIn: parent; expanded: control.popup.visible }
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
        width: ListView.view ? ListView.view.width : control.width - 12; height: 36
        leftPadding: 10; rightPadding: 10; topPadding: 6; bottomPadding: 6; hoverEnabled: true
        highlighted: control.highlightedIndex === index
        contentItem: Text { text: entry.modelData.label; color: "#e5ebf0"; font.pixelSize: 13; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
        background: Rectangle { radius: 6; color: entry.highlighted || entry.hovered ? "#2b394a" : "transparent" }
    }
    popup: Popup {
        y: control.height + 5; width: control.width; padding: 6; margins: 8
        clip: true
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
