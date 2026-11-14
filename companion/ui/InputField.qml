import QtQuick
import QtQuick.Controls.Basic
TextField {
    id: field
    implicitHeight: 40
    color: "#e5ebf0"
    placeholderTextColor: "#72808f"
    selectionColor: "#46546a"
    selectedTextColor: "#ffffff"
    font.pixelSize: 13
    leftPadding: 12
    rightPadding: 12
    background: Rectangle {
        radius: 9
        color: field.activeFocus ? "#1c2733" : "#161e28"
        border.color: field.activeFocus ? "#ceb37f" : "#303b49"
        Behavior on border.color { ColorAnimation { duration: 120 } }
    }
}
