import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    property var root
    property var searchInput
    GridView {
        id: albumGrid
        anchors.fill: parent
        anchors.leftMargin: 22
        anchors.rightMargin: 22
        model: albumModel
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: StyledScrollBar {}
        topMargin: 4
        bottomMargin: 20

        readonly property int columns: Math.max(2, Math.floor(width / 190))
        cellWidth: Math.floor(width / columns)
        cellHeight: cellWidth + 62

        delegate: Item {
            id: card
            required property int index
            required property int albumId
            required property string title
            required property string artist
            required property string cover
            required property int trackCount

            width: albumGrid.cellWidth
            height: albumGrid.cellHeight

            Rectangle {
                anchors.fill: parent
                anchors.margins: 6
                radius: 14
                color: cardMouse.containsMouse ? Theme.elevated : "transparent"
                Behavior on color { ColorAnimation { duration: 140 } }
            }

            Column {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 12

                Item {
                    width: parent.width
                    height: width

                    CoverArt {
                        anchors.fill: parent
                        radiusRatio: 0.06
                        decodeSize: 360
                        source: card.cover
                    }

                    IconButton {
                        id: playOverlay
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        anchors.margins: 10
                        size: 44
                        iconSize: 18
                        filled: true
                        icon: "play"
                        opacity: cardMouse.containsMouse ? 1 : 0
                        y: cardMouse.containsMouse ? 0 : 6
                        Behavior on opacity { NumberAnimation { duration: 160 } }
                        onClicked: backend.playAlbum(card.albumId)
                    }
                }

                Column {
                    width: parent.width
                    spacing: 3
                    Text {
                        width: parent.width
                        text: card.title
                        color: Theme.text
                        font.pixelSize: 14
                        font.bold: true
                        elide: Text.ElideRight
                    }
                    Text {
                        width: parent.width
                        text: card.artist
                        color: Theme.textSecondary
                        font.pixelSize: 12
                        elide: Text.ElideRight
                    }
                }
            }

            // Debajo del botón de play para que éste reciba sus clics
            MouseArea {
                id: cardMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                z: -1
                onClicked: root.openAlbum(card.albumId, card.title, card.artist)
            }
        }
    }

    Text {
        anchors.centerIn: parent
        visible: albumModel.count === 0 && !root.scanning
        text: searchInput.text !== "" ? "Sin resultados" : "Aún no hay álbumes"
        color: Theme.textSecondary
        font.pixelSize: 16
    }
}
