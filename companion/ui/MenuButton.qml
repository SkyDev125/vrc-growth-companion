import QtQuick
import QtQuick.Layouts

ActionButton {
    id: control
    property bool expanded: false
    implicitWidth: Math.max(36, caption.implicitWidth + 46)
    contentItem: RowLayout {
        spacing: 8
        Text {
            id: caption
            text: control.text
            color: control.enabled ? "#dce3e9" : "#66717d"
            font: control.font
            verticalAlignment: Text.AlignVCenter
        }
        Chevron { expanded: control.expanded; Layout.alignment: Qt.AlignVCenter }
    }
}
