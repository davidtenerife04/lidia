import QtQuick
import QtQuick.Controls

MenuItem {
    id: item
    implicitHeight: 38
    implicitWidth: 240

    contentItem: Text {
        text: item.text
        color: item.enabled ? Theme.text : Theme.textTertiary
        font.pixelSize: 14
        elide: Text.ElideRight
        verticalAlignment: Text.AlignVCenter
        leftPadding: 8
    }
    background: Rectangle {
        radius: 8
        color: item.highlighted ? Theme.hover : "transparent"
    }
}
