import QtQuick
import QtQuick.Controls

Slider {
    id: c
    hoverEnabled: true
    implicitHeight: 20

    background: Item {
        x: c.leftPadding
        y: c.topPadding
        width: c.availableWidth
        height: c.availableHeight

        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width
            height: 4
            radius: 2
            color: Theme.track

            Rectangle {
                width: c.visualPosition * parent.width
                height: parent.height
                radius: 2
                color: (c.hovered || c.pressed) ? Theme.accent : Theme.text
                Behavior on color { ColorAnimation { duration: 120 } }
            }
        }
    }

    handle: Rectangle {
        x: c.leftPadding + c.visualPosition * (c.availableWidth - width)
        y: c.topPadding + c.availableHeight / 2 - height / 2
        width: 12
        height: 12
        radius: 6
        color: Theme.text
        opacity: (c.hovered || c.pressed) ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 120 } }
    }
}
