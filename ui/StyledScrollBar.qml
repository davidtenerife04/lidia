import QtQuick
import QtQuick.Controls

ScrollBar {
    id: c
    policy: ScrollBar.AsNeeded
    implicitWidth: 12

    contentItem: Rectangle {
        implicitWidth: 6
        radius: 3
        color: c.pressed ? Theme.textSecondary : Theme.textTertiary
        opacity: (c.active || c.hovered) ? 0.9 : 0
        Behavior on opacity { NumberAnimation { duration: 200 } }
    }
    background: Item {}
}
