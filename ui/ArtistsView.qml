import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    property var root
    property var searchInput
    GridView {
        id: artistGrid
        anchors.fill: parent
        anchors.leftMargin: 22
        anchors.rightMargin: 22
        model: artistModel
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: StyledScrollBar {}
        topMargin: 4
        bottomMargin: 20

        readonly property int columns: Math.max(2, Math.floor(width / 190))
        cellWidth: Math.floor(width / columns)
        cellHeight: cellWidth + 58

        delegate: Item {
            id: artistCard
            required property int index
            required property int artistId
            required property string name
            required property int albumCount
            required property int trackCount

            width: artistGrid.cellWidth
            height: artistGrid.cellHeight

            Rectangle {
                anchors.fill: parent
                anchors.margins: 6
                radius: 14
                color: artistMouse.containsMouse ? Theme.elevated : "transparent"
                Behavior on color { ColorAnimation { duration: 140 } }
            }

            Column {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 10

                Rectangle {
                    width: parent.width
                    height: width
                    radius: 12
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: Theme.elevated }
                        GradientStop { position: 1.0; color: Theme.surface }
                    }
                    Icon {
                        anchors.centerIn: parent
                        width: parent.width * 0.36
                        height: width
                        name: "artist"
                        color: Theme.textTertiary
                    }
                }

                Column {
                    width: parent.width
                    spacing: 3
                    Text {
                        width: parent.width
                        text: artistCard.name
                        color: Theme.text
                        font.pixelSize: 14
                        font.bold: true
                        elide: Text.ElideRight
                    }
                    Text {
                        width: parent.width
                        text: root.plural(artistCard.albumCount, "álbum", "álbumes")
                              + "  ·  " + root.plural(artistCard.trackCount, "canción", "canciones")
                        color: Theme.textSecondary
                        font.pixelSize: 12
                        elide: Text.ElideRight
                    }
                }
            }

            MouseArea {
                id: artistMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                z: -1
                onClicked: root.openArtist(artistCard.artistId, artistCard.name)
            }
        }
    }

    Text {
        anchors.centerIn: parent
        visible: artistModel.count === 0 && !root.scanning
        text: searchInput.text !== "" ? "Sin resultados" : "Aún no hay artistas"
        color: Theme.textSecondary
        font.pixelSize: 16
    }
}
