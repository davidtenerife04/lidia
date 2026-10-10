import QtQuick
import QtQuick.Controls

Item {
    id: root
    property string icon: ""
    property color tint: Theme.textSecondary
    property color hoverTint: Theme.text
    property real iconSize: 20
    property real size: 36
    property bool filled: false      // círculo de color de acento (botón principal)
    property string tip: ""
    readonly property bool hovered: ma.containsMouse
    signal clicked()

    implicitWidth: size
    implicitHeight: size

    Rectangle {
        anchors.fill: parent
        radius: width / 2
        color: root.filled ? (ma.containsMouse ? Theme.accentHover : Theme.accent)
                           : (ma.containsMouse ? Theme.hover : "transparent")
        scale: ma.pressed ? 0.92 : 1.0
        Behavior on scale { NumberAnimation { duration: 90 } }
        Behavior on color { ColorAnimation { duration: 120 } }
    }

    Icon {
        anchors.centerIn: parent
        width: root.iconSize
        height: root.iconSize
        name: root.icon
        color: root.filled ? Theme.accentText : (ma.containsMouse ? root.hoverTint : root.tint)
    }

    MouseArea {
        id: ma
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }

    ToolTip.visible: ma.containsMouse && root.tip !== ""
    ToolTip.text: root.tip
    ToolTip.delay: 600
}
