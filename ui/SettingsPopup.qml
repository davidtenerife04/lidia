import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: popup
    property var values: ({darkMode: true, replayGain: true, gapless: true, crossfade: 0, closeToTray: true, trayAvailable: false, libraries: [], serverEnabled: false, serverLan: false, serverRunning: false, serverPin: "", serverAddress: "", serverFingerprint: "", artistPhotos: true, allowDownloads: true, allowUploads: false, requestsPerMinute: 600})
    signal settingChanged(string key, bool value)
    signal crossfadeChanged(int seconds)
    signal requestsChanged(int value)
    signal removeLibraryRequested(string folder)
    signal addLibraryRequested()
    signal refreshRequested()

    modal: true
    focus: true
    anchors.centerIn: Overlay.overlay
    width: 460
    height: Math.min(settingsColumn.implicitHeight + topPadding + bottomPadding,
                     (Overlay.overlay ? Overlay.overlay.height : 800) - 64)
    padding: 22
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    function setValues(v) { values = v; }

    Timer {
        interval: 2000
        repeat: true
        running: popup.visible && popup.values.serverRunning
        onTriggered: popup.refreshRequested()
    }

    Overlay.modal: Rectangle { color: "#99000000" }

    background: Rectangle {
        radius: 16
        color: Theme.elevated
        border.width: 1
        border.color: Theme.border
    }

    component Option: RowLayout {
        id: opt
        property string title: ""
        property string hint: ""
        property bool checked: false
        signal toggled(bool value)
        Layout.fillWidth: true
        spacing: 12

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2
            Text {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: opt.title
                color: Theme.text
                font.pixelSize: 14
                font.bold: true
            }
            Text {
                Layout.fillWidth: true
                text: opt.hint
                color: Theme.textSecondary
                font.pixelSize: 12
                wrapMode: Text.WordWrap
            }
        }
        Switch {
            checked: opt.checked
            onToggled: opt.toggled(checked)
        }
    }

    contentItem: Flickable {
        id: flick
        clip: true
        contentWidth: width
        contentHeight: settingsColumn.implicitHeight
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: StyledScrollBar {}

    ColumnLayout {
        id: settingsColumn
        width: flick.width - (flick.contentHeight > flick.height ? 14 : 0)
        spacing: 14

        Text {
            text: "Ajustes"
            color: Theme.text
            font.pixelSize: 18
            font.bold: true
        }

        Option {
            title: "Reproducción sin pausa"
            hint: "Enlaza las pistas sin hueco entre ellas."
            checked: popup.values.gapless
            onToggled: function(v) { popup.settingChanged("gapless", v) }
        }
        Option {
            title: popup.values.darkMode ? "Modo oscuro" : "Modo día"
            hint: "Cambia entre el tema oscuro y el tema claro."
            checked: popup.values.darkMode
            onToggled: function(v) { popup.settingChanged("darkMode", v) }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: "Crossfade: " + (xfSlider.value === 0 ? "desactivado" : xfSlider.value + " s")
                    color: Theme.text
                    font.pixelSize: 14
                    font.bold: true
                }
                Text {
                    Layout.fillWidth: true
                    text: "Mezcla el final de una pista con el inicio de la siguiente (0 a 10 s)."
                    color: Theme.textSecondary
                    font.pixelSize: 12
                    wrapMode: Text.WordWrap
                }
            }
            Slider {
                id: xfSlider
                from: 0
                to: 10
                stepSize: 1
                snapMode: Slider.SnapAlways
                Layout.preferredWidth: 140
                Layout.maximumWidth: 140
                Layout.alignment: Qt.AlignVCenter
                value: popup.values.crossfade
                onMoved: popup.crossfadeChanged(Math.round(value))
            }
        }
        Option {
            title: "Normalizar volumen (ReplayGain)"
            hint: "Iguala el volumen entre álbumes si los archivos traen la etiqueta."
            checked: popup.values.replayGain
            onToggled: function(v) { popup.settingChanged("replayGain", v) }
        }
        Option {
            title: "Fotos de artistas"
            hint: "Descarga la foto de cada artista de Deezer (se envía su nombre). Desactivado, se usa una portada de su álbum."
            checked: popup.values.artistPhotos
            onToggled: function(v) { popup.settingChanged("artistPhotos", v) }
        }
        Option {
            visible: popup.values.trayAvailable
            title: "Cerrar a la bandeja"
            hint: "Al cerrar la ventana la música sigue sonando en la bandeja del sistema."
            checked: popup.values.closeToTray
            onToggled: function(v) { popup.settingChanged("closeToTray", v) }
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }

        Option {
            title: "Servidor para otros dispositivos"
            hint: "Permite controlar Lidia y acceder a tu biblioteca desde otra app (p. ej. Android)."
            checked: popup.values.serverEnabled
            onToggled: function(v) { popup.settingChanged("serverEnabled", v) }
        }
        Option {
            visible: popup.values.serverEnabled
            title: "Permitir acceso desde la red local"
            hint: "Las conexiones van cifradas (HTTPS). Desactivado, solo este equipo puede conectarse."
            checked: popup.values.serverLan
            onToggled: function(v) { popup.settingChanged("serverLan", v) }
        }
        Option {
            visible: popup.values.serverEnabled
            title: "Permitir descargas"
            hint: "Los dispositivos emparejados pueden descargar canciones, álbumes o la biblioteca entera."
            checked: popup.values.allowDownloads
            onToggled: function(v) { popup.settingChanged("allowDownloads", v) }
        }
        Option {
            visible: popup.values.serverEnabled
            title: "Permitir subidas"
            hint: "Los dispositivos emparejados pueden subir música a la carpeta Música/Lidia (máx. 1 GB por archivo y 20 GB en total)."
            checked: popup.values.allowUploads
            onToggled: function(v) { popup.settingChanged("allowUploads", v) }
        }
        RowLayout {
            visible: popup.values.serverEnabled
            Layout.fillWidth: true
            spacing: 12
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: "Peticiones por minuto: " + (reqSlider.value === 0 ? "sin límite" : reqSlider.value)
                    color: Theme.text
                    font.pixelSize: 14
                    font.bold: true
                }
                Text {
                    Layout.fillWidth: true
                    text: "Por dispositivo. Al superarlo, recibe un aviso y debe esperar."
                    color: Theme.textSecondary
                    font.pixelSize: 12
                    wrapMode: Text.WordWrap
                }
            }
            Slider {
                id: reqSlider
                from: 0
                to: 1800
                stepSize: 60
                snapMode: Slider.SnapAlways
                Layout.preferredWidth: 140
                Layout.maximumWidth: 140
                Layout.alignment: Qt.AlignVCenter
                value: popup.values.requestsPerMinute
                onMoved: popup.requestsChanged(Math.round(value))
            }
        }
        ColumnLayout {
            visible: popup.values.serverRunning
            Layout.fillWidth: true
            spacing: 4
            Text {
                Layout.fillWidth: true
                text: "Dirección: https://" + popup.values.serverAddress
                color: Theme.textSecondary
                font.pixelSize: 13
                wrapMode: Text.WrapAnywhere
            }
            Text {
                Layout.fillWidth: true
                text: "PIN de emparejamiento: " + popup.values.serverPin
                color: Theme.textSecondary
                font.pixelSize: 13
                wrapMode: Text.WrapAnywhere
            }
            Text {
                Layout.fillWidth: true
                text: "Huella del certificado (SHA-256), compárala en el otro dispositivo al emparejar:"
                color: Theme.textSecondary
                font.pixelSize: 13
                wrapMode: Text.WordWrap
            }
            TextEdit {
                Layout.fillWidth: true
                readOnly: true
                selectByMouse: true
                text: (popup.values.serverFingerprint.match(/(?:[0-9A-Fa-f]{2}:?){1,16}/g) || []).join("\n")
                color: Theme.textSecondary
                selectionColor: Theme.accent
                font.pixelSize: 12
                font.family: "monospace"
                wrapMode: TextEdit.WrapAnywhere
            }
        }
        Text {
            visible: popup.values.serverEnabled && !popup.values.serverRunning
            text: "No se pudo iniciar el servidor (¿puerto ocupado?)."
            color: Theme.textSecondary
            font.pixelSize: 12
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }

        Text {
            text: "Carpetas de la biblioteca"
            color: Theme.text
            font.pixelSize: 14
            font.bold: true
        }
        Text {
            visible: popup.values.libraries.length === 0
            text: "No hay carpetas añadidas."
            color: Theme.textSecondary
            font.pixelSize: 12
        }
        Repeater {
            model: popup.values.libraries
            delegate: RowLayout {
                required property string modelData
                Layout.fillWidth: true
                spacing: 8
                Text {
                    Layout.fillWidth: true
                    text: modelData
                    color: Theme.textSecondary
                    font.pixelSize: 13
                    elide: Text.ElideMiddle
                }
                PillButton {
                    text: "Quitar"
                    onClicked: popup.removeLibraryRequested(modelData)
                }
            }
        }

        RowLayout {
            Layout.alignment: Qt.AlignRight
            spacing: 10
            PillButton {
                text: "Añadir carpeta"
                onClicked: popup.addLibraryRequested()
            }
            PillButton {
                primary: true
                text: "Cerrar"
                onClicked: popup.close()
            }
        }
    }
    }
}
