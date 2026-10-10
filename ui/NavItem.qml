import QtQuick
import QtQuick.Controls

Item {
    id: root
    property string icon: ""
    property string text: ""
    property bool active: false
    property bool compact: false
    signal clicked()

    implicitHeight: 42

    Rectangle {
        anchors.fill: parent
        radius: 10
        color: root.active ? Theme.accentSoft : (ma.containsMouse ? Theme.hover : "transparent")
        Behavior on color { ColorAnimation { duration: 120 } }
    }

    Rectangle {
        visible: root.active
        width: 3; height: 18; radius: 2
        anchors.verticalCenter: parent.verticalCenter
        x: 0
        color: Theme.accent
    }

    Row {
        anchors.verticalCenter: parent.verticalCenter
        x: root.compact ? Math.round((root.width - 18) / 2) : 16
        spacing: 12
        Icon {
            width: 18; height: 18
            anchors.verticalCenter: parent.verticalCenter
            name: root.icon
            color: root.active ? Theme.accent : Theme.textSecondary
        }
        Text {
            visible: !root.compact
            anchors.verticalCenter: parent.verticalCenter
            text: root.text
            font.pixelSize: 14
            font.bold: root.active
            color: root.active ? Theme.text : Theme.textSecondary
        }
    }

    MouseArea {
        id: ma
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }

    ToolTip.visible: root.compact && ma.containsMouse
    ToolTip.text: root.text
    ToolTip.delay: 500
}
