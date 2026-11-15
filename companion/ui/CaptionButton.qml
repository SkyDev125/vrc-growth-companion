import QtQuick
import QtQuick.Controls.Basic

Button {
    id: control
    property string captionAction: "minimize"
    property bool maximized: false
    implicitWidth: 44
    implicitHeight: 32
    padding: 0
    hoverEnabled: true
    onCaptionActionChanged: symbol.requestPaint()
    onMaximizedChanged: symbol.requestPaint()
    onHoveredChanged: symbol.requestPaint()
    Accessible.name: captionAction === "close" ? "Close companion" : captionAction === "minimize" ? "Minimize" : maximized ? "Restore window" : "Maximize window"
    ToolTip.visible: hovered
    ToolTip.delay: 700
    ToolTip.text: Accessible.name
    contentItem: Item {
        Canvas {
            id: symbol
            objectName: "captionSymbol"
            anchors.centerIn: parent
            width: 12; height: 12
            onPaint: {
                var ctx = getContext("2d")
                ctx.clearRect(0, 0, width, height)
                ctx.strokeStyle = control.captionAction === "close" && control.hovered ? "#ffffff" : "#c2ccd8"
                ctx.lineWidth = 1.2
                ctx.lineCap = "square"
                ctx.lineJoin = "miter"
                ctx.beginPath()
                if (control.captionAction === "minimize") {
                    ctx.moveTo(1, 6.5); ctx.lineTo(11, 6.5)
                } else if (control.captionAction === "close") {
                    ctx.moveTo(2, 2); ctx.lineTo(10, 10)
                    ctx.moveTo(10, 2); ctx.lineTo(2, 10)
                } else if (control.maximized) {
                    ctx.moveTo(4.5, 1.5); ctx.lineTo(10.5, 1.5); ctx.lineTo(10.5, 7.5)
                    ctx.rect(1.5, 4.5, 6, 6)
                } else {
                    ctx.rect(1.5, 1.5, 9, 9)
                }
                ctx.stroke()
            }
        }
    }
    background: Rectangle {
        radius: 3
        color: control.down ? (control.captionAction === "close" ? "#a82d39" : "#354252") : control.hovered ? (control.captionAction === "close" ? "#c84350" : "#263342") : "transparent"
        border.width: control.visualFocus ? 1 : 0
        border.color: "#e0c48c"
        Behavior on color { ColorAnimation { duration: 90 } }
    }
}
