import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    property var root
    property var equalizerPopup
    property var sleepMenu
    id: playerBar
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.bottom: parent.bottom
    height: 96
    color: Theme.surface

    Rectangle {
        anchors.top: parent.top
        width: parent.width
        height: 1
        color: Theme.border
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 20
        anchors.rightMargin: 24
        spacing: 24

        // Ahora suena
        RowLayout {
            Layout.preferredWidth: 300
            Layout.maximumWidth: 300
            spacing: 14

            CoverArt {
                Layout.preferredWidth: 62
                Layout.preferredHeight: 62
                radiusRatio: 0.13
                decodeSize: 160
                source: root.currentCover
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3

                Text {
                    Layout.fillWidth: true
                    text: root.currentTitle !== "" ? root.currentTitle : "Nada en reproducción"
                    color: root.currentTitle !== "" ? Theme.text : Theme.textSecondary
                    font.pixelSize: 15
                    font.bold: true
                    elide: Text.ElideRight
                }
                Text {
                    id: artistLabel
                    Layout.fillWidth: true
                    visible: root.currentArtist !== ""
                    text: root.currentArtist
                    color: artistArea.containsMouse ? Theme.text : Theme.textSecondary
                    font.pixelSize: 13
                    font.underline: artistArea.containsMouse
                    elide: Text.ElideRight

                    MouseArea {
                        id: artistArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.artistClicked(artistLabel)
                    }
                }
            }

            IconButton {
                visible: root.currentTrackId > 0
                size: 34
                iconSize: 18
                icon: root.currentFav ? "heart" : "heartOutline"
                tint: root.currentFav ? Theme.accent : Theme.textSecondary
                hoverTint: root.currentFav ? Theme.accentHover : Theme.text
                tip: root.currentFav ? "Quitar de favoritos (Ctrl+D)" : "Añadir a favoritos (Ctrl+D)"
                onClicked: backend.toggleFavorite(root.currentTrackId)
            }
        }

        // Controles centrales
        ColumnLayout {
            Layout.fillWidth: true
            Layout.maximumWidth: 640
            Layout.alignment: Qt.AlignHCenter
            spacing: 6

            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                spacing: 10

                IconButton {
                    icon: "shuffle"
                    iconSize: 18
                    tint: root.shuffle ? Theme.accent : Theme.textSecondary
                    hoverTint: root.shuffle ? Theme.accentHover : Theme.text
                    tip: root.shuffle ? "Aleatorio: activado" : "Aleatorio: desactivado"
                    onClicked: backend.toggleShuffle()
                }
                IconButton {
                    icon: "prev"
                    iconSize: 20
                    hoverTint: Theme.text
                    tint: Theme.text
                    tip: "Anterior"
                    onClicked: backend.prevTrack()
                }
                IconButton {
                    size: 46
                    iconSize: 20
                    filled: true
                    icon: root.playing ? "pause" : "play"
                    onClicked: backend.togglePause()
                }
                IconButton {
                    icon: "next"
                    iconSize: 20
                    hoverTint: Theme.text
                    tint: Theme.text
                    tip: "Siguiente"
                    onClicked: backend.nextTrack()
                }
                IconButton {
                    icon: root.repeatMode === 2 ? "repeat1" : "repeat"
                    iconSize: 18
                    tint: root.repeatMode !== 0 ? Theme.accent : Theme.textSecondary
                    hoverTint: root.repeatMode !== 0 ? Theme.accentHover : Theme.text
                    tip: root.repeatMode === 0 ? "Repetir: desactivado"
                       : root.repeatMode === 1 ? "Repetir: toda la cola" : "Repetir: una canción"
                    onClicked: backend.cycleRepeat()
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Text {
                    text: root.formatTime(progress.pressed ? progress.value : root.currentTime)
                    color: Theme.textSecondary
                    font.pixelSize: 12
                    font.family: "monospace"
                    Layout.minimumWidth: 38
                    horizontalAlignment: Text.AlignRight
                }

                StyledSlider {
                    id: progress
                    Layout.fillWidth: true
                    from: 0
                    to: root.currentDuration > 0 ? root.currentDuration : 1
                    enabled: root.currentPath !== ""
                    // Buscamos al soltar para no saturar a mpv con seeks
                    onPressedChanged: if (!pressed) backend.seek(value)
                }
                Binding {
                    target: progress
                    property: "value"
                    value: root.currentTime
                    when: !progress.pressed
                }

                Text {
                    text: root.formatTime(root.currentDuration)
                    color: Theme.textSecondary
                    font.pixelSize: 12
                    font.family: "monospace"
                    Layout.minimumWidth: 38
                }
            }
        }

        // Utilidades: letras, ecualizador y temporizador de apagado
        RowLayout {
            Layout.alignment: Qt.AlignVCenter
            spacing: 2

            IconButton {
                icon: "lyrics"
                iconSize: 18
                size: 34
                tint: root.lyricsOpen ? Theme.accent : Theme.textSecondary
                hoverTint: root.lyricsOpen ? Theme.accentHover : Theme.text
                tip: root.lyricsOpen ? "Ocultar letra" : "Mostrar letra"
                onClicked: root.lyricsOpen = !root.lyricsOpen
            }
            IconButton {
                icon: "equalizer"
                iconSize: 18
                size: 34
                tip: "Ecualizador"
                onClicked: {
                    equalizerPopup.setGains(backend.getEqualizer());
                    equalizerPopup.open();
                }
            }
            IconButton {
                icon: "clock"
                iconSize: 18
                size: 34
                tint: backend.sleepRemaining > 0 ? Theme.accent : Theme.textSecondary
                hoverTint: backend.sleepRemaining > 0 ? Theme.accentHover : Theme.text
                tip: backend.sleepRemaining > 0 ? "Temporizador de apagado activo" : "Temporizador de apagado"
                onClicked: sleepMenu.popup()
            }
            Text {
                visible: backend.sleepRemaining > 0
                text: root.formatSleep(backend.sleepRemaining)
                color: Theme.textSecondary
                font.pixelSize: 12
                font.family: "monospace"
                Layout.leftMargin: 6
            }
        }

        // Volumen
        RowLayout {
            Layout.preferredWidth: 240
            Layout.maximumWidth: 240
            Layout.alignment: Qt.AlignVCenter
            spacing: 6

            IconButton {
                icon: "queue"
                iconSize: 18
                size: 34
                tint: root.queueOpen ? Theme.accent : Theme.textSecondary
                hoverTint: root.queueOpen ? Theme.accentHover : Theme.text
                tip: root.queueOpen ? "Ocultar cola" : "Mostrar cola"
                onClicked: root.queueOpen = !root.queueOpen
            }

            IconButton {
                icon: root.volume <= 0 ? "muted" : "volume"
                iconSize: 18
                size: 34
                tip: root.volume <= 0 ? "Quitar silencio" : "Silenciar"
                onClicked: {
                    if (root.volume > 0) {
                        root.lastVolume = root.volume;
                        root.volume = 0;
                    } else {
                        root.volume = root.lastVolume > 0 ? root.lastVolume : 80;
                    }
                    backend.setVolume(root.volume);
                }
            }
            StyledSlider {
                id: volumeSlider
                Layout.fillWidth: true
                from: 0
                to: 100
                value: root.volume
                onMoved: {
                    root.volume = value;
                    backend.setVolume(value);
                }
            }
        }
    }
}
