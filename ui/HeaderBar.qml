import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    property var root
    property var searchDebounce
    property var sortMenu
    property alias searchInput: searchInput
    id: header
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.top: parent.top
    anchors.leftMargin: 32
    anchors.rightMargin: 32
    height: (root.section === 1 || root.section === 5) ? 104 : 150

    RowLayout {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.topMargin: 26
        spacing: 16

        IconButton {
            visible: root.section === 2 || root.section === 6
            icon: "back"
            iconSize: 18
            tip: root.section === 6 ? "Volver a artistas" : "Volver a álbumes"
            onClicked: root.section === 6 ? root.goArtists() : root.goAlbums()
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2

            Text {
                Layout.fillWidth: true
                text: root.section === 0 ? "Canciones"
                    : root.section === 1 ? "Álbumes"
                    : root.section === 2 ? root.albumTitle
                    : root.section === 3 ? "Favoritos"
                    : root.section === 5 ? "Artistas"
                    : root.section === 6 ? root.artistName
                    : root.section === 7 ? "Más escuchadas"
                    : root.section === 8 ? "Reproducidas hace poco"
                    : root.section === 9 ? "Añadidas recientemente" : root.playlistName
                color: Theme.text
                font.pixelSize: 30
                font.bold: true
                elide: Text.ElideRight
            }
            Text {
                Layout.fillWidth: true
                text: root.section === 0 ? root.plural(trackModel.count, "canción", "canciones")
                    : root.section === 1 ? root.plural(albumModel.count, "álbum", "álbumes")
                    : root.section === 2 ? root.albumArtist + "  ·  " + root.plural(trackModel.count, "canción", "canciones")
                    : root.section === 4 ? "Lista  ·  " + root.plural(trackModel.count, "canción", "canciones")
                    : root.section === 5 ? root.plural(artistModel.count, "artista", "artistas")
                    : root.section === 6 ? "Artista  ·  " + root.plural(trackModel.count, "canción", "canciones")
                    : root.section >= 7 ? "Automática  ·  " + root.plural(trackModel.count, "canción", "canciones")
                    : root.plural(trackModel.count, "canción", "canciones")
                color: Theme.textSecondary
                font.pixelSize: 14
                elide: Text.ElideRight
            }
        }

        IconButton {
            visible: root.section === 4
            icon: "edit"
            iconSize: 18
            tip: "Renombrar lista"
            onClicked: root.askName("rename", "Renombrar lista", "Guardar", root.playlistName, -1)
        }
        IconButton {
            id: deleteButton
            property bool armed: false
            visible: root.section === 4
            icon: "trash"
            iconSize: 18
            tint: armed ? "#ff6b6b" : Theme.textSecondary
            hoverTint: armed ? "#ff8a8a" : Theme.text
            tip: armed ? "Pulsa otra vez para eliminar la lista" : "Eliminar lista"
            onClicked: {
                if (armed) {
                    armed = false;
                    var id = root.playlistId;
                    root.goSongs();
                    backend.deletePlaylist(id);
                } else {
                    armed = true;
                    disarmTimer.restart();
                }
            }
            Timer { id: disarmTimer; interval: 3000; onTriggered: deleteButton.armed = false }
        }

        // Orden de la lista de canciones (solo vista «Canciones»)
        Rectangle {
            id: sortControl
            readonly property bool hovered: sortMouse.containsMouse
            visible: root.section === 0
            Layout.preferredWidth: sortRow.implicitWidth + 26
            Layout.preferredHeight: 40
            radius: 20
            color: Theme.elevated
            border.width: 1
            border.color: sortControl.hovered || sortMenu.opened ? Theme.accent : Theme.border
            Behavior on border.color { ColorAnimation { duration: 150 } }

            Row {
                id: sortRow
                anchors.centerIn: parent
                spacing: 8

                Text {
                    text: "Orden: " + root.sortText
                    color: Theme.text
                    font.pixelSize: 13
                }
                Icon {
                    width: 12; height: 12
                    anchors.verticalCenter: parent.verticalCenter
                    name: "chevronDown"
                    color: Theme.textSecondary
                }
            }
            MouseArea {
                id: sortMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: sortMenu.popup()
            }
        }

        // Buscador
        Rectangle {
            id: searchBox
            Layout.preferredWidth: 320
            Layout.preferredHeight: 40
            radius: 20
            color: Theme.elevated
            border.width: 1
            border.color: searchInput.activeFocus ? Theme.accent : Theme.border
            Behavior on border.color { ColorAnimation { duration: 150 } }

            Icon {
                x: 14
                anchors.verticalCenter: parent.verticalCenter
                width: 16; height: 16
                name: "search"
                color: Theme.textSecondary
            }

            TextInput {
                id: searchInput
                anchors.left: parent.left
                anchors.leftMargin: 40
                anchors.right: clearButton.left
                anchors.rightMargin: 4
                anchors.verticalCenter: parent.verticalCenter
                color: Theme.text
                selectionColor: Theme.accent
                selectedTextColor: Theme.accentText
                font.pixelSize: 14
                clip: true
                selectByMouse: true
                onTextEdited: searchDebounce.restart()

                Text {
                    visible: searchInput.text.length === 0
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Buscar canciones, artistas, álbumes…"
                    color: Theme.textTertiary
                    font.pixelSize: 14
                }
            }

            IconButton {
                id: clearButton
                anchors.right: parent.right
                anchors.rightMargin: 6
                anchors.verticalCenter: parent.verticalCenter
                size: 28
                iconSize: 12
                icon: "close"
                visible: searchInput.text.length > 0
                onClicked: {
                    searchInput.text = "";
                    searchDebounce.stop();
                    backend.setQuery("");
                }
            }
        }
    }

    RowLayout {
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 14
        spacing: 10
        visible: root.section !== 1 && root.section !== 5 && trackModel.count > 0

        PillButton {
            primary: true
            icon: "play"
            text: "Reproducir"
            onClicked: backend.playIndex(0)
        }
        PillButton {
            icon: "shuffle"
            text: "Aleatorio"
            onClicked: backend.playShuffled()
        }
    }
}
