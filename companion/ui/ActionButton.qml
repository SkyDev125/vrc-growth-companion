import QtQuick
import QtQuick.Controls.Basic

Button {
    id: control
    property bool primary: false
    property bool quiet: false
    property bool danger: false
    implicitHeight: 36
    implicitWidth: Math.max(36, label.implicitWidth + 26)
    padding: 12
    hoverEnabled: true
    font.pixelSize: 13
    font.weight: Font.DemiBold
    contentItem: Text {
        id: label
        text: control.text
        font: control.font
        color: !control.enabled ? "#66717d" : control.primary ? "#201d16" : control.danger ? "#f2a399" : "#dce3e9"
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        radius: 9
        color: control.primary ? (control.down ? "#c4aa72" : control.hovered ? "#f0d9a7" : "#e0c48c") : control.down ? "#303b48" : control.hovered ? "#27313d" : control.quiet ? "transparent" : "#1c2530"
        border.color: control.visualFocus ? "#e0c48c" : control.primary || control.quiet ? "transparent" : "#303c4a"
        Behavior on color { ColorAnimation { duration: 120 } }
    }
    Accessible.name: text
}
