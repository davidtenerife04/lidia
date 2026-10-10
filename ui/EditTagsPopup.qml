import QtQuick
import QtQuick.Controls

// Diálogo para editar título, artista y álbum de una pista
Popup {
    id: popup
    property int targetRow: -1
    property var tags: ({title: "", artist: "", album: ""})
    signal saved(string title, string artist, string album)

    modal: true
    focus: true
    anchors.centerIn: Overlay.overlay
    width: 380
    padding: 22
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    onAboutToShow: {
        titleField.text = tags.title;
        artistField.text = tags.artist;
        albumField.text = tags.album;
    }
    onOpened: titleField.forceActiveFocus()

    function submit() {
        popup.saved(titleField.text, artistField.text, albumField.text);
        popup.close();
    }

    Overlay.modal: Rectangle { color: "#99000000" }

    background: Rectangle {
        radius: 16
        color: Theme.elevated
        border.width: 1
        border.color: Theme.border
    }

    component Field: Column {
        id: field
        property string label: ""
        property alias text: input.text
        spacing: 6
        width: parent ? parent.width : 0

        Text {
            text: field.label
            color: Theme.textSecondary
            font.pixelSize: 12
            font.bold: true
        }
        Rectangle {
            width: parent.width
            height: 40
            radius: 20
            color: Theme.surface
            border.width: 1
            border.color: input.activeFocus ? Theme.accent : Theme.border

            TextInput {
                id: input
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 14
                verticalAlignment: TextInput.AlignVCenter
                color: Theme.text
                selectionColor: Theme.accent
                selectedTextColor: Theme.accentText
                font.pixelSize: 14
                clip: true
                selectByMouse: true
            }
        }
    }

    contentItem: Column {
        width: popup.availableWidth
        spacing: 14

        Text {
            text: "Editar etiquetas"
            color: Theme.text
            font.pixelSize: 18
            font.bold: true
        }

        Field { id: titleField; label: "Título" }
        Field { id: artistField; label: "Artista" }
        Field { id: albumField; label: "Álbum" }

        Row {
            anchors.right: parent.right
            spacing: 10
            PillButton {
                text: "Cancelar"
                onClicked: popup.close()
            }
            PillButton {
                primary: true
                text: "Guardar"
                onClicked: popup.submit()
            }
        }
    }
}
