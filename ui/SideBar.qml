import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    property var root
    property var settingsPopup
    property var audioLabPopup
    id: sidebar
    clip: true
    anchors.left: parent.left
    anchors.top: parent.top
    width: root.sidebarWidth
    readonly property bool compact: width < 140
    color: Theme.sidebar

    Rectangle {
        anchors.right: parent.right
        width: 1
        height: parent.height
        color: Theme.border
    }

    MouseArea {
        z: 10
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: 8
        hoverEnabled: true
        cursorShape: Qt.SizeHorCursor
        onPositionChanged: function(mouse) {
            if (!pressed) return;
            var x = mapToItem(sidebar.parent, mouse.x, 0).x;
            root.sidebarWidth = Math.max(64, Math.min(420, Math.round(x)));
        }
        onReleased: {
            if (root.sidebarWidth < 140) root.sidebarWidth = 64;
            else if (root.sidebarWidth < 180) root.sidebarWidth = 180;
            backend.saveSidebarWidth(root.sidebarWidth);
        }
        onDoubleClicked: {
            root.sidebarWidth = 236;
            backend.saveSidebarWidth(236);
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: sidebar.compact ? 10 : 18
        spacing: 6

        // Logo
        RowLayout {
            Layout.topMargin: 6
            Layout.bottomMargin: 22
            Layout.alignment: sidebar.compact ? Qt.AlignHCenter : Qt.AlignLeft
            spacing: 12

            Image {
                Layout.preferredWidth: 36
                Layout.preferredHeight: 36
                source: Theme.logo
                sourceSize: Qt.size(72, 72)
                fillMode: Image.PreserveAspectFit
                smooth: true
            }
            Text {
                visible: !sidebar.compact
                text: "Lidia"
                color: Theme.text
                font.pixelSize: 19
                font.bold: true
            }
        }

        Text {
            visible: !sidebar.compact
            text: "BIBLIOTECA"
            color: Theme.textTertiary
            font.pixelSize: 11
            font.bold: true
            font.letterSpacing: 1.2
            Layout.leftMargin: 6
            Layout.bottomMargin: 4
        }

        NavItem {
            Layout.fillWidth: true
            compact: sidebar.compact
            icon: "songs"
            text: "Canciones"
            active: root.section === 0
            onClicked: root.goSongs()
        }
        NavItem {
            Layout.fillWidth: true
            compact: sidebar.compact
            icon: "albums"
            text: "Álbumes"
            active: root.section === 1 || root.section === 2
            onClicked: root.goAlbums()
        }
        NavItem {
            Layout.fillWidth: true
            compact: sidebar.compact
            icon: "artist"
            text: "Artistas"
            active: root.section === 5 || root.section === 6
            onClicked: root.goArtists()
        }

        NavItem {
            Layout.fillWidth: true
            compact: sidebar.compact
            icon: "heart"
            text: "Favoritos"
            active: root.section === 3
            onClicked: root.goFavorites()
        }
        NavItem {
            Layout.fillWidth: true
            compact: sidebar.compact
            icon: "songs"
            text: "Más escuchadas"
            active: root.section === 7
            onClicked: root.goSmart("top", 7)
        }
        NavItem {
            Layout.fillWidth: true
            compact: sidebar.compact
            icon: "clock"
            text: "Reproducidas hace poco"
            active: root.section === 8
            onClicked: root.goSmart("played", 8)
        }
        NavItem {
            Layout.fillWidth: true
            compact: sidebar.compact
            icon: "albums"
            text: "Añadidas recientemente"
            active: root.section === 9
            onClicked: root.goSmart("added", 9)
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 18
            Layout.leftMargin: sidebar.compact ? 0 : 6

            Text {
                visible: !sidebar.compact
                Layout.fillWidth: true
                text: "LISTAS"
                color: Theme.textTertiary
                font.pixelSize: 11
                font.bold: true
                font.letterSpacing: 1.2
            }
            IconButton {
                Layout.alignment: Qt.AlignHCenter
                Layout.fillWidth: sidebar.compact
                size: 26
                iconSize: 14
                icon: "plus"
                tip: "Nueva lista"
                onClicked: root.askName("new", "Nueva lista", "Crear", "", -1)
            }
        }

        ListView {
            id: playlistList
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: playlistModel
            clip: true
            spacing: 2
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: StyledScrollBar {}

            delegate: NavItem {
                id: pl
                required property int playlistId
                required property string name
                required property int trackCount
                width: ListView.view.width
                compact: sidebar.compact
                icon: "playlist"
                text: pl.name
                active: root.section === 4 && root.playlistId === pl.playlistId
                onClicked: root.openPlaylist(pl.playlistId, pl.name)
            }

            Text {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.leftMargin: 6
                visible: playlistModel.count === 0 && !sidebar.compact
                text: "Aún no tienes listas."
                color: Theme.textTertiary
                font.pixelSize: 12
            }
        }

        // Estado del escaneo
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 62
            visible: root.scanning && !sidebar.compact
            radius: 12
            color: Theme.elevated

            Column {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 6

                Text {
                    text: "Escaneando biblioteca…"
                    color: Theme.text
                    font.pixelSize: 13
                    font.bold: true
                }
                Text {
                    text: root.plural(root.scanCount, "archivo revisado", "archivos revisados")
                    color: Theme.textSecondary
                    font.pixelSize: 12
                }
                Rectangle {
                    width: parent.width
                    height: 3
                    radius: 2
                    color: Theme.track
                    clip: true

                    Rectangle {
                        id: scanBar
                        width: parent.width * 0.35
                        height: parent.height
                        radius: 2
                        color: Theme.accent
                        SequentialAnimation on x {
                            running: root.scanning
                            loops: Animation.Infinite
                            NumberAnimation { from: -scanBar.width; to: scanBar.parent.width; duration: 1100; easing.type: Easing.InOutQuad }
                        }
                    }
                }
            }
        }

        IconButton {
            visible: sidebar.compact
            Layout.alignment: Qt.AlignHCenter
            icon: "plus"
            iconSize: 18
            tip: "Añadir carpeta"
            onClicked: backend.openFolderDialog()
        }
        IconButton {
            visible: sidebar.compact
            Layout.alignment: Qt.AlignHCenter
            icon: "refresh"
            iconSize: 18
            tip: "Actualizar"
            enabled: !root.scanning
            opacity: enabled ? 1 : 0.5
            onClicked: backend.rescan()
        }
        PillButton {
            visible: !sidebar.compact
            Layout.fillWidth: true
            primary: true
            icon: "plus"
            text: "Añadir carpeta"
            onClicked: backend.openFolderDialog()
        }
        PillButton {
            visible: !sidebar.compact
            Layout.fillWidth: true
            icon: "refresh"
            text: "Actualizar"
            enabled: !root.scanning
            opacity: enabled ? 1 : 0.5
            onClicked: backend.rescan()
        }
        IconButton {
            visible: sidebar.compact
            Layout.alignment: Qt.AlignHCenter
            icon: "equalizer"
            iconSize: 18
            tip: "Laboratorio de audio"
            onClicked: audioLabPopup.open()
        }
        PillButton {
            visible: !sidebar.compact
            Layout.fillWidth: true
            icon: "equalizer"
            text: "Laboratorio"
            onClicked: audioLabPopup.open()
        }
        IconButton {
            visible: sidebar.compact
            Layout.alignment: Qt.AlignHCenter
            icon: "settings"
            iconSize: 18
            tip: "Ajustes"
            onClicked: {
                settingsPopup.setValues(backend.getSettings());
                settingsPopup.open();
            }
        }
        PillButton {
            visible: !sidebar.compact
            Layout.fillWidth: true
            text: "Ajustes"
            onClicked: {
                settingsPopup.setValues(backend.getSettings());
                settingsPopup.open();
            }
        }
    }
}
