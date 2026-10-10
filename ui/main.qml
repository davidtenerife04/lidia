import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: root
    visible: true
    width: 1180
    height: 760
    minimumWidth: 860
    minimumHeight: 560
    color: Theme.bg
    title: currentTitle !== "" ? currentArtist + " — " + currentTitle : "Lidia"

    // ---- estado de reproducción ----
    property string currentTitle: ""
    property string currentArtist: ""
    property string currentAlbum: ""
    property string currentCover: ""
    property string currentPath: ""
    property real currentDuration: 0
    property real currentTime: 0
    property bool playing: false
    property bool shuffle: false
    property int repeatMode: 0
    property real volume: 80
    property real lastVolume: 80

    // ---- estado de navegación ----
    property int section: 0              // 0 canciones · 1 álbumes · 2 álbum · 3 favoritos · 4 lista · 5 artistas · 6 artista
    property string albumTitle: ""
    property string albumArtist: ""
    property string artistName: ""
    property int playlistId: -1
    property string playlistName: ""
    property int currentTrackId: -1
    property bool currentFav: false
    property bool scanning: false
    property int scanCount: 0
    property bool queueOpen: false
    property int sidebarWidth: 236
    readonly property bool wide: width - sidebarWidth - (queueOpen ? 340 : 0) > 814

    // ---- estado de la interfaz ----
    property bool lyricsOpen: false
    property bool dragOver: false
    property string toastText: ""
    property string sortValue: "default"
    readonly property string sortText: root.sortValue === "title" ? "Título"
        : root.sortValue === "artist" ? "Artista"
        : root.sortValue === "album" ? "Álbum"
        : root.sortValue === "added" ? "Fecha de añadido" : "Predeterminado"

    function formatTime(secs) {
        if (!secs || isNaN(secs) || secs < 0) return "0:00";
        var m = Math.floor(secs / 60);
        var s = Math.floor(secs % 60);
        return m + ":" + (s < 10 ? "0" : "") + s;
    }

    function plural(n, one, many) {
        return n + " " + (n === 1 ? one : many);
    }

    function goSongs() {
        backend.showAll();
        section = 0;
    }

    function goAlbums() {
        backend.showAll();
        section = 1;
    }

    function goSmart(kind, sec) {
        backend.showSmart(kind);
        section = sec;
    }

    function goFavorites() {
        backend.showFavorites();
        section = 3;
    }

    function openPlaylist(id, name) {
        playlistId = id;
        playlistName = name;
        backend.showPlaylist(id);
        section = 4;
    }

    function askName(mode, heading, confirm, initial, row) {
        namePopup.mode = mode;
        namePopup.heading = heading;
        namePopup.confirmText = confirm;
        namePopup.initialText = initial;
        namePopup.targetRow = row;
        namePopup.open();
    }

    function openAlbum(id, title, artist) {
        header.searchInput.text = "";
        backend.setQuery("");
        albumTitle = title;
        albumArtist = artist;
        backend.openAlbum(id);
        section = 2;
    }

    function goArtists() {
        backend.showAll();
        section = 5;
    }

    function openArtist(id, name) {
        header.searchInput.text = "";
        backend.setQuery("");
        artistName = name;
        backend.openArtist(id);
        section = 6;
    }

    function openArtistByName(name) {
        header.searchInput.text = "";
        backend.setQuery("");
        artistName = name;
        backend.openArtistByName(name);
        section = 6;
    }

    function artistClicked(item) {
        var parts = backend.splitArtists(root.currentArtist);
        if (parts.length <= 1) {
            root.openArtistByName(parts.length === 1 ? parts[0] : root.currentArtist);
            return;
        }
        artistMenu.parts = parts;
        artistMenu.popup(item, 0, -artistMenu.implicitHeight - 6);
    }

    function formatSleep(secs) {
        if (!secs || secs <= 0) return "";
        var m = Math.floor(secs / 60);
        var s = Math.floor(secs % 60);
        return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
    }

    Component.onCompleted: {
        volume = backend.getVolume();
        sortValue = backend.getSort();
        var ui = backend.loadUi();
        if (ui.width > 0 && ui.height > 0) {
            width = Math.max(minimumWidth, ui.width);
            height = Math.max(minimumHeight, ui.height);
        }
        queueOpen = ui.queueOpen;
        sidebarWidth = ui.sidebarWidth;
        Theme.dark = backend.getSettings().darkMode;
    }

    // Recuerda tamaño de ventana y panel de cola (con retardo para no escribir a cada píxel)
    Timer {
        id: saveUiTimer
        interval: 700
        onTriggered: backend.saveUi(root.width, root.height, root.queueOpen)
    }
    onWidthChanged: saveUiTimer.restart()
    onHeightChanged: saveUiTimer.restart()
    onQueueOpenChanged: saveUiTimer.restart()
    onClosing: function(close) {
        backend.saveUi(root.width, root.height, root.queueOpen);
        if (backend.closeToTray()) {
            close.accepted = false;
            root.hide();
        }
    }

    // Búsqueda con retardo: se consulta al backend 150 ms después de dejar de escribir
    Timer {
        id: searchDebounce
        interval: 150
        onTriggered: backend.setQuery(header.searchInput.text)
    }

    // Avisos temporales del backend
    Timer {
        id: toastTimer
        interval: 3200
        onTriggered: root.toastText = ""
    }

    // ---- atajos ----
    Shortcut { sequence: "Space"; enabled: !header.searchInput.activeFocus; onActivated: backend.togglePause() }
    Shortcut { sequence: "Ctrl+Right"; onActivated: backend.nextTrack() }
    Shortcut { sequence: "Ctrl+Left"; onActivated: backend.prevTrack() }
    Shortcut { sequence: "Ctrl+D"; onActivated: if (root.currentTrackId > 0) backend.toggleFavorite(root.currentTrackId) }
    Shortcut { sequence: "Ctrl+Q"; onActivated: root.queueOpen = !root.queueOpen }
    Shortcut { sequence: "Ctrl+F"; onActivated: header.searchInput.forceActiveFocus() }
    Shortcut {
        sequence: "Escape"
        enabled: header.searchInput.activeFocus
        onActivated: {
            header.searchInput.text = "";
            searchDebounce.stop();
            backend.setQuery("");
            root.contentItem.forceActiveFocus();
        }
    }

    // =====================================================================
    //  BARRA LATERAL
    // =====================================================================
    SideBar {
        id: sidebar
        root: root
        settingsPopup: settingsPopup
        anchors.bottom: playerBar.top
    }

    // =====================================================================
    //  CONTENIDO PRINCIPAL
    // =====================================================================
    Item {
        id: content
        anchors.left: sidebar.right
        anchors.right: queuePanel.left
        anchors.top: parent.top
        anchors.bottom: playerBar.top

        // ---- cabecera ----
        HeaderBar {
            id: header
            root: root
            searchDebounce: searchDebounce
            sortMenu: sortMenu
        }

        // ---- vistas ----
        StackLayout {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: header.bottom
            anchors.bottom: parent.bottom
            currentIndex: root.section === 1 ? 1 : (root.section === 5 ? 2 : 0)

            // ===================== LISTA DE CANCIONES =====================
            SongsView {
                root: root
                searchInput: header.searchInput
                addMenu: addMenu
                editTagsPopup: editTagsPopup
            }

            // ===================== CUADRÍCULA DE ÁLBUMES =====================
            AlbumsView {
                root: root
                searchInput: header.searchInput
            }

            // ===================== CUADRÍCULA DE ARTISTAS =====================
            ArtistsView {
                root: root
                searchInput: header.searchInput
            }
        }
    }

    // =====================================================================
    //  PANEL DE LETRAS
    // =====================================================================
    LyricsPanel {
        id: lyricsPanel
        root: root
        anchors.bottom: playerBar.top
    }

    // =====================================================================
    //  MENÚ «AÑADIR A LISTA» Y VENTANA DE NOMBRE
    // =====================================================================
    StyledMenu {
        id: artistMenu
        property var parts: []
        Repeater {
            model: artistMenu.parts
            delegate: StyledMenuItem {
                required property string modelData
                text: modelData
                onTriggered: root.openArtistByName(modelData)
            }
        }
    }

    StyledMenu {
        id: addMenu
        property int targetRow: -1

        StyledMenuItem {
            text: "Nueva lista…"
            onTriggered: root.askName("newWithTrack", "Nueva lista", "Crear y añadir", "", addMenu.targetRow)
        }
        MenuSeparator {
            contentItem: Rectangle { implicitHeight: 1; color: Theme.border }
        }
        Instantiator {
            model: playlistModel
            delegate: StyledMenuItem {
                required property int playlistId
                required property string name
                text: name
                onTriggered: backend.addRowToPlaylist(addMenu.targetRow, playlistId)
            }
            onObjectAdded: function(index, object) { addMenu.insertItem(index + 2, object) }
            onObjectRemoved: function(index, object) { addMenu.removeItem(object) }
        }
    }

    NamePopup {
        id: namePopup
        property string mode: ""
        property int targetRow: -1
        onAccepted: function(text) {
            if (mode === "new") {
                var id = backend.createPlaylistWithRow(text, -1);
                if (id >= 0) root.openPlaylist(id, backend.playlistName(id));
            } else if (mode === "newWithTrack") {
                backend.createPlaylistWithRow(text, targetRow);
            } else if (mode === "saveQueue") {
                backend.saveQueueAsPlaylist(text);
            } else if (mode === "rename") {
                backend.renamePlaylist(root.playlistId, text);
                root.playlistName = backend.playlistName(root.playlistId);
            }
        }
    }

    EditTagsPopup {
        id: editTagsPopup
        onSaved: function(title, artist, album) {
            backend.editTags(editTagsPopup.targetRow, title, artist, album);
        }
    }

    SettingsPopup {
        id: settingsPopup
        onSettingChanged: function(key, value) {
            backend.setSetting(key, value);
            if (key === "darkMode") Theme.dark = value;
            settingsPopup.setValues(backend.getSettings());
        }
        onRefreshRequested: settingsPopup.setValues(backend.getSettings())
        onCrossfadeChanged: function(seconds) {
            backend.setCrossfade(seconds);
        }
        onRemoveLibraryRequested: function(folder) {
            backend.removeLibrary(folder);
            settingsPopup.setValues(backend.getSettings());
        }
        onAddLibraryRequested: {
            backend.openFolderDialog();
            settingsPopup.setValues(backend.getSettings());
        }
    }

    EqualizerPopup {
        id: equalizerPopup
        onApplyRequested: function(values) {
            backend.setEqualizer(values);
        }
    }

    // Orden de la lista de canciones
    StyledMenu {
        id: sortMenu
        StyledMenuItem { text: "Predeterminado"; onTriggered: backend.setSort("default") }
        StyledMenuItem { text: "Título"; onTriggered: backend.setSort("title") }
        StyledMenuItem { text: "Artista"; onTriggered: backend.setSort("artist") }
        StyledMenuItem { text: "Álbum"; onTriggered: backend.setSort("album") }
        StyledMenuItem { text: "Fecha de añadido"; onTriggered: backend.setSort("added") }
    }

    // Temporizador de apagado
    StyledMenu {
        id: sleepMenu
        StyledMenuItem { text: "15 minutos"; onTriggered: backend.setSleepTimer(15) }
        StyledMenuItem { text: "30 minutos"; onTriggered: backend.setSleepTimer(30) }
        StyledMenuItem { text: "45 minutos"; onTriggered: backend.setSleepTimer(45) }
        StyledMenuItem { text: "60 minutos"; onTriggered: backend.setSleepTimer(60) }
        StyledMenuItem { text: "90 minutos"; onTriggered: backend.setSleepTimer(90) }
        MenuSeparator {
            contentItem: Rectangle { implicitHeight: 1; color: Theme.border }
        }
        StyledMenuItem { text: "Cancelar temporizador"; onTriggered: backend.setSleepTimer(0) }
    }

    // =====================================================================
    //  PANEL DE COLA
    // =====================================================================
    QueuePanel {
        id: queuePanel
        root: root
        anchors.bottom: playerBar.top
    }

    // =====================================================================
    //  BARRA DE REPRODUCCIÓN
    // =====================================================================
    PlayerBar {
        id: playerBar
        root: root
        equalizerPopup: equalizerPopup
        sleepMenu: sleepMenu
    }

    // =====================================================================
    //  SEÑALES DEL BACKEND
    // =====================================================================
    Connections {
        target: backend
        function onTrackChanged(title, artist, album, cover, path, trackId) {
            root.currentTrackId = trackId;
            root.currentFav = backend.isFavorite(trackId);
            root.currentTitle = title;
            root.currentArtist = artist;
            root.currentAlbum = album;
            root.currentCover = cover;
            root.currentPath = path;
            root.currentTime = 0;
            lyricsPanel.loadLyrics(path);
            if (queueModel.currentIndex >= 0)
                queuePanel.queueList.positionViewAtIndex(queueModel.currentIndex, ListView.Contain);
        }
        function onFavoriteChanged(trackId, favorite) {
            if (trackId === root.currentTrackId) root.currentFav = favorite;
        }
        function onDurationUpdated(seconds) { root.currentDuration = seconds; }
        function onTimeUpdated(seconds) {
            root.currentTime = seconds;
            lyricsPanel.updateLyric(seconds);
        }
        function onPlayingChanged(p) { root.playing = p; }
        function onShuffleChanged(enabled) { root.shuffle = enabled; }
        function onRepeatChanged(mode) { root.repeatMode = mode; }
        function onScanningChanged(s) { root.scanning = s; }
        function onScanProgress(files) { root.scanCount = files; }
        function onMessage(text) {
            root.toastText = text;
            toastTimer.restart();
        }
        function onSortChanged(s) { root.sortValue = s; }
    }

    // =====================================================================
    //  AVISOS TEMPORALES (TOAST)
    // =====================================================================
    Rectangle {
        id: toast
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 112
        z: 60
        visible: root.toastText !== ""
        width: Math.min(400, parent.width - 80)
        height: 46
        radius: 23
        color: Theme.elevated
        border.width: 1
        border.color: Theme.border

        Text {
            anchors.fill: parent
            anchors.leftMargin: 18
            anchors.rightMargin: 18
            text: root.toastText
            color: Theme.text
            font.pixelSize: 13
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            wrapMode: Text.Wrap
            maximumLineCount: 2
            elide: Text.ElideRight
        }
    }

    // =====================================================================
    //  ARRASTRAR Y SOLTAR CARPETAS
    // =====================================================================
    DropArea {
        id: dropArea
        anchors.fill: parent
        keys: ["text/uri-list"]
        z: 95
        onEntered: root.dragOver = true
        onExited: root.dragOver = false
        onDropped: function(drop) {
            root.dragOver = false;
            var urls = [];
            for (var i = 0; i < drop.urls.length; i++)
                urls.push(drop.urls[i].toString());
            backend.addFolders(urls);
            drop.acceptProposedAction();
        }
    }

    Rectangle {
        anchors.fill: parent
        visible: root.dragOver
        z: 90
        color: Theme.accentSoft
        border.width: 3
        border.color: Theme.accent

        Column {
            anchors.centerIn: parent
            spacing: 14

            Icon {
                anchors.horizontalCenter: parent.horizontalCenter
                width: 52; height: 52
                name: "songs"
                color: Theme.accent
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Suelta las carpetas para añadirlas\na tu biblioteca"
                color: Theme.accent
                font.pixelSize: 17
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                lineHeight: 1.3
            }
        }
    }
}
