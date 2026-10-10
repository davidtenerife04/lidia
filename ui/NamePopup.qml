import QtQuick
import QtQuick.Controls

// Ventana modal para pedir un nombre (nueva lista, renombrar, guardar cola)
Popup {
    id: popup
    property string heading: ""
    property string confirmText: "Aceptar"
    property string initialText: ""
    property bool wasAccepted: false
    signal accepted(string text)

    modal: true
    focus: true
    anchors.centerIn: Overlay.overlay
    width: 360
    padding: 22
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    onAboutToShow: {
        field.text = initialText;
        wasAccepted = false;
    }
    onOpened: {
        field.forceActiveFocus();
        field.selectAll();
    }

    function submit() {
        var t = field.text.trim();
        if (t === "") return;
        popup.accepted(t);
        popup.close();
    }

    Overlay.modal: Rectangle { color: "#99000000" }

    background: Rectangle {
        radius: 16
        color: Theme.elevated
        border.width: 1
        border.color: Theme.border
    }

    contentItem: Column {
        spacing: 16

        Text {
            text: popup.heading
            color: Theme.text
            font.pixelSize: 18
            font.bold: true
        }

        Rectangle {
            width: parent.width
            height: 42
            radius: 21
            color: Theme.surface
            border.width: 1
            border.color: field.activeFocus ? Theme.accent : Theme.border

            TextInput {
                id: field
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                verticalAlignment: TextInput.AlignVCenter
                color: Theme.text
                selectionColor: Theme.accent
                selectedTextColor: Theme.accentText
                font.pixelSize: 15
                clip: true
                selectByMouse: true
                maximumLength: 80
                onAccepted: popup.submit()
            }
        }

        Row {
            anchors.right: parent.right
            spacing: 10
            PillButton {
                text: "Cancelar"
                onClicked: popup.close()
            }
            PillButton {
                primary: true
                text: popup.confirmText
                onClicked: popup.submit()
            }
        }
    }
}
