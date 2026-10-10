import QtQuick

// Ecualizador animado para la pista en reproducción
Item {
    id: root
    property bool running: true
    property color color: Theme.accent
    width: 16
    height: 14

    Row {
        anchors.fill: parent
        spacing: 2
        Repeater {
            model: 3
            Item {
                id: slot
                required property int index
                width: 3.5
                height: root.height
                Rectangle {
                    id: bar
                    width: parent.width
                    height: 5
                    radius: 1.5
                    color: root.color
                    anchors.bottom: parent.bottom
                    SequentialAnimation on height {
                        running: root.running
                        loops: Animation.Infinite
                        NumberAnimation { to: root.height; duration: 320 + slot.index * 110; easing.type: Easing.InOutSine }
                        NumberAnimation { to: 3; duration: 300 + slot.index * 90; easing.type: Easing.InOutSine }
                    }
                }
            }
        }
    }
}
