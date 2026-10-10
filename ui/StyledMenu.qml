import QtQuick
import QtQuick.Controls

Menu {
    id: menu
    implicitWidth: 240
    padding: 6

    background: Rectangle {
        implicitWidth: 240
        radius: 12
        color: Theme.elevated
        border.width: 1
        border.color: Theme.border
    }
}
