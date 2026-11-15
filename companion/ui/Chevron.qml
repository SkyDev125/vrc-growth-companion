import QtQuick

// Draw a centered path, independent of font metrics and platform glyphs.
Canvas {
    id: chevron
    implicitWidth: 12
    implicitHeight: 8
    property color color: "#b7c3d0"
    property bool expanded: false
    rotation: expanded ? 180 : 0
    onColorChanged: requestPaint()
    onPaint: {
        var ctx = getContext("2d")
        ctx.clearRect(0, 0, width, height)
        ctx.strokeStyle = color
        ctx.lineWidth = 1.5
        ctx.lineCap = "round"
        ctx.lineJoin = "round"
        ctx.beginPath()
        ctx.moveTo(1, 1.5)
        ctx.lineTo(6, 6.5)
        ctx.lineTo(11, 1.5)
        ctx.stroke()
    }
    Behavior on rotation { NumberAnimation { duration: 110; easing.type: Easing.OutCubic } }
}
