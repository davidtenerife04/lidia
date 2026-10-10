import QtQuick

Item {
    id: root
    property string text: ""
    property string icon: ""
    property bool primary: false
    signal clicked()

    implicitHeight: 40
    implicitWidth: row.implicitWidth + 36

    Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: root.primary ? (ma.containsMouse ? Theme.accentHover : Theme.accent)
                            : (ma.containsMouse ? Theme.hover : "transparent")
        border.width: root.primary ? 0 : 1
        border.color: Theme.border
        scale: ma.pressed ? 0.97 : 1.0
        Behavior on scale { NumberAnimation { duration: 90 } }
        Behavior on color { ColorAnimation { duration: 120 } }
    }

    Row {
        id: row
        anchors.centerIn: parent
        spacing: 8

        Icon {
            visible: root.icon !== ""
            width: 16; height: 16
            anchors.verticalCenter: parent.verticalCenter
            name: root.icon
            color: root.primary ? Theme.accentText : Theme.text
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.text
            font.pixelSize: 14
            font.bold: true
            color: root.primary ? Theme.accentText : Theme.text
        }
    }

    MouseArea {
        id: ma
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
