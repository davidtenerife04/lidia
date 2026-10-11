import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    property var root
    property var searchInput
    property var addMenu
    property var editTagsPopup
    readonly property int qualityW: 96
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Cabecera de columnas
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 34
            visible: trackModel.count > 0

            Row {
                anchors.fill: parent
                anchors.leftMargin: 28
                anchors.rightMargin: 28

                Text {
                    width: 44
                    height: parent.height
                    verticalAlignment: Text.AlignVCenter
                    horizontalAlignment: Text.AlignHCenter
                    text: "#"
                    color: Theme.textTertiary
                    font.pixelSize: 12
                    font.bold: true
                }
                Text {
                    width: parent.width - 44 - 70 - 40 - qualityW - (root.wide ? 240 : 0)
                    height: parent.height
                    leftPadding: 66
                    verticalAlignment: Text.AlignVCenter
                    text: "TÍTULO"
                    color: Theme.textTertiary
                    font.pixelSize: 12
                    font.bold: true
                    font.letterSpacing: 1
                }
                Text {
                    visible: root.wide
                    width: 240
                    height: parent.height
                    verticalAlignment: Text.AlignVCenter
                    text: "ÁLBUM"
                    color: Theme.textTertiary
                    font.pixelSize: 12
                    font.bold: true
                    font.letterSpacing: 1
                }
                Item { width: 40; height: parent.height }
                Text {
                    width: 70
                    height: parent.height
                    verticalAlignment: Text.AlignVCenter
                    horizontalAlignment: Text.AlignRight
                    text: "DURACIÓN"
                    color: Theme.textTertiary
                    font.pixelSize: 11
                    font.bold: true
                }
                Text {
                    width: qualityW
                    height: parent.height
                    verticalAlignment: Text.AlignVCenter
                    horizontalAlignment: Text.AlignRight
                    text: "CALIDAD"
                    color: Theme.textTertiary
                    font.pixelSize: 11
                    font.bold: true
                }
            }
            Rectangle {
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.leftMargin: 28
                anchors.rightMargin: 28
                height: 1
                color: Theme.border
            }
        }

        ListView {
            id: trackList
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: trackModel
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: StyledScrollBar {}
            footer: Item { height: 20 }
            topMargin: 6

            delegate: Item {
                id: row
                required property int index
                required property string title
                required property string artist
                required property string album
                required property string path
                required property string cover
                required property int duration
                required property int bitrate
                required property string format
                required property bool favorite
                readonly property bool isCurrent: root.currentPath === row.path
                readonly property bool hovered: rowHover.hovered

                width: ListView.view.width
                height: 58

                Rectangle {
                    anchors.fill: parent
                    anchors.leftMargin: 16
                    anchors.rightMargin: 16
                    radius: 10
                    color: row.hovered ? Theme.hover
                         : (row.isCurrent ? Theme.accentSoft : "transparent")
                    Behavior on color { ColorAnimation { duration: 100 } }
                }

                Row {
                    anchors.fill: parent
                    anchors.leftMargin: 28
                    anchors.rightMargin: 28
                    spacing: 0

                    // Nº / indicador
                    Item {
                        width: 44
                        height: parent.height

                        Text {
                            anchors.centerIn: parent
                            visible: !row.isCurrent && !row.hovered
                            text: row.index + 1
                            color: Theme.textTertiary
                            font.pixelSize: 13
                        }
                        Icon {
                            anchors.centerIn: parent
                            width: 16; height: 16
                            visible: row.hovered && !(row.isCurrent && root.playing)
                            name: "play"
                            color: Theme.text
                        }
                        EqBars {
                            anchors.centerIn: parent
                            visible: row.isCurrent && !row.hovered
                            running: root.playing
                        }
                    }

                    // Portada + título/artista
                    Item {
                        width: parent.width - 44 - 70 - 40 - qualityW - (root.wide ? 240 : 0)
                        height: parent.height

                        CoverArt {
                            id: rowCover
                            anchors.verticalCenter: parent.verticalCenter
                            width: 42; height: 42
                            radiusRatio: 0.17
                            decodeSize: 96
                            source: row.cover
                        }
                        Column {
                            anchors.left: rowCover.right
                            anchors.leftMargin: 14
                            anchors.right: parent.right
                            anchors.rightMargin: 12
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 3

                            Text {
                                width: parent.width
                                text: row.title
                                color: row.isCurrent ? Theme.accent : Theme.text
                                font.pixelSize: 15
                                font.bold: true
                                elide: Text.ElideRight
                            }
                            Text {
                                width: parent.width
                                text: row.artist
                                color: Theme.textSecondary
                                font.pixelSize: 13
                                elide: Text.ElideRight
                            }
                        }
                    }

                    Item {
                        visible: root.wide
                        width: 240
                        height: parent.height
                        Text {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.rightMargin: 16
                            anchors.verticalCenter: parent.verticalCenter
                            text: row.album
                            color: Theme.textSecondary
                            font.pixelSize: 13
                            elide: Text.ElideRight
                        }
                    }

                    Item {
                        width: 40
                        height: parent.height
                        IconButton {
                            anchors.centerIn: parent
                            size: 32
                            iconSize: 17
                            visible: row.favorite || row.hovered
                            icon: row.favorite ? "heart" : "heartOutline"
                            tint: row.favorite ? Theme.accent : Theme.textSecondary
                            hoverTint: row.favorite ? Theme.accentHover : Theme.text
                            tip: row.favorite ? "Quitar de favoritos" : "Añadir a favoritos"
                            onClicked: backend.toggleFavoriteAtRow(row.index)
                        }
                    }

                    Item {
                        width: 70
                        height: parent.height
                        Text {
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            text: root.formatTime(row.duration)
                            color: Theme.textSecondary
                            font.pixelSize: 13
                        }
                    }

                    Item {
                        width: qualityW
                        height: parent.height
                        Column {
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 2
                            Text {
                                anchors.right: parent.right
                                text: row.format
                                color: Theme.textSecondary
                                font.pixelSize: 12
                                font.bold: true
                            }
                            Text {
                                anchors.right: parent.right
                                visible: row.bitrate > 0
                                text: row.bitrate + " kbps"
                                color: Theme.textTertiary
                                font.pixelSize: 11
                            }
                        }
                    }
                }

                MouseArea {
                    id: rowMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    z: -1   // queda por debajo del Row y botones para que reciban hover y clics
                    onClicked: {
                        if (row.isCurrent) backend.togglePause();
                        else backend.playIndex(row.index);
                    }
                }

                HoverHandler { id: rowHover }

                Rectangle {
                    visible: row.hovered
                    anchors.right: parent.right
                    anchors.rightMargin: 28 + 70 + 40 + qualityW + (root.wide ? 240 : 0) + 6
                    anchors.verticalCenter: parent.verticalCenter
                    width: actionsRow.width + 10
                    height: 36
                    radius: 18
                    color: Theme.elevated

                    Row {
                        id: actionsRow
                        anchors.centerIn: parent
                        spacing: 0
                        IconButton {
                            size: 32
                            iconSize: 17
                            icon: "queue"
                            tip: "Reproducir a continuación"
                            onClicked: backend.playNext(row.index)
                        }
                        IconButton {
                            size: 32
                            iconSize: 17
                            icon: "queueAdd"
                            tip: "Añadir al final de la cola"
                            onClicked: backend.addToQueue(row.index)
                        }
                        IconButton {
                            size: 32
                            iconSize: 17
                            icon: "playlist"
                            tip: "Añadir a una lista…"
                            onClicked: {
                                addMenu.targetRow = row.index;
                                addMenu.popup();
                            }
                        }
                        IconButton {
                            size: 32
                            iconSize: 16
                            icon: "edit"
                            tip: "Editar etiquetas…"
                            onClicked: {
                                editTagsPopup.targetRow = row.index;
                                editTagsPopup.tags = backend.trackTags(row.index);
                                editTagsPopup.open();
                            }
                        }
                        IconButton {
                            visible: root.section === 4
                            size: 32
                            iconSize: 15
                            icon: "close"
                            tip: "Quitar de esta lista"
                            onClicked: backend.removeRowFromPlaylist(row.index)
                        }
                    }
                }
            }
        }
    }

    // Estado vacío
    ColumnLayout {
        anchors.centerIn: parent
        visible: trackModel.count === 0 && !root.scanning
        spacing: 14

        Icon {
            Layout.alignment: Qt.AlignHCenter
            width: 56; height: 56
            name: searchInput.text !== "" ? "search" : root.section === 3 ? "heartOutline" : root.section === 4 ? "playlist" : "songs"
            color: Theme.textTertiary
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: searchInput.text !== "" ? "Sin resultados"
                : root.section === 3 ? "Aún no tienes favoritos"
                : root.section === 4 ? "Esta lista está vacía"
                : root.section >= 7 ? "Aún no hay nada aquí" : "Tu biblioteca está vacía"
            color: Theme.text
            font.pixelSize: 20
            font.bold: true
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: searchInput.text !== "" ? "Prueba con otro título, artista o álbum."
                : root.section === 3 ? "Pulsa el corazón de una canción para guardarla aquí."
                : root.section === 4 ? "Usa el botón de lista que aparece al pasar el ratón por una canción."
                : root.section >= 7 ? "Se llena según lo que escuches y añadas."
                : "Añade una carpeta con tu música para empezar."
            color: Theme.textSecondary
            font.pixelSize: 14
        }
        PillButton {
            Layout.alignment: Qt.AlignHCenter
            visible: searchInput.text === "" && root.section < 3
            primary: true
            icon: "plus"
            text: "Añadir carpeta de música"
            onClicked: backend.openFolderDialog()
        }
    }
}
