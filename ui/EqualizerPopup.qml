import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Popup con las 10 bandas del ecualizador (-12..+12 dB)
Popup {
    id: popup
    property var gains: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    readonly property var freqs: ["31", "62", "125", "250", "500", "1k", "2k", "4k", "8k", "16k"]
    signal applyRequested(var values)

    modal: false
    focus: true
    anchors.centerIn: Overlay.overlay
    width: 560
    padding: 20
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    function setGains(list) {
        if (!list || list.length < 10) return;
        for (var i = 0; i < 10; i++) popup.gains[i] = list[i];
    }

    function scheduleApply() { applyTimer.restart() }
    function applyNow() {
        var list = [];
        for (var i = 0; i < 10; i++) list.push(popup.gains[i]);
        popup.applyRequested(list);
    }
    function reset() {
        for (var i = 0; i < 10; i++) popup.gains[i] = 0;
        applyNow();
    }

    Timer { id: applyTimer; interval: 60; onTriggered: popup.applyNow() }

    Overlay.modal: Rectangle { color: "#99000000" }

    background: Rectangle {
        radius: 16
        color: Theme.elevated
        border.width: 1
        border.color: Theme.border
    }

    contentItem: Column {
        spacing: 18

        RowLayout {
            width: parent.width
            Text {
                text: "Ecualizador"
                color: Theme.text
                font.pixelSize: 18
                font.bold: true
            }
            Item { Layout.fillWidth: true }
            IconButton {
                icon: "close"
                iconSize: 14
                size: 30
                tip: "Cerrar"
                onClicked: popup.close()
            }
        }

        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 6

            Repeater {
                model: 10
                Column {
                    required property int index
                    width: 42
                    spacing: 6

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: (band.value >= 0 ? "+" : "") + Math.round(band.value)
                        color: Theme.textSecondary
                        font.pixelSize: 11
                        font.family: "monospace"
                    }
                    Slider {
                        id: band
                        padding: 0
                        from: -12
                        to: 12
                        stepSize: 1
                        snapMode: Slider.SnapOnRelease
                        orientation: Qt.Vertical
                        width: 36
                        height: 170
                        anchors.horizontalCenter: parent.horizontalCenter

                        Binding { target: band; property: "value"; value: popup.gains[index] }

                        onValueChanged: {
                            if (popup.gains[index] !== value) {
                                popup.gains[index] = value;
                                popup.scheduleApply();
                            }
                        }

                        background: Item {
                            anchors.fill: parent

                            Rectangle {
                                anchors.horizontalCenter: parent.horizontalCenter
                                y: 6
                                width: 4
                                height: parent.height - 12
                                radius: 2
                                color: Theme.track
                            }
                            Rectangle {
                                anchors.horizontalCenter: parent.horizontalCenter
                                width: 4
                                radius: 2
                                color: Theme.accent
                                y: Math.min(knob.y + knob.height / 2, parent.height / 2)
                                height: Math.max(1, Math.abs(knob.y + knob.height / 2 - parent.height / 2))
                            }
                        }
                        handle: Rectangle {
                            id: knob
                            width: 18
                            height: 18
                            radius: 9
                            color: band.pressed ? Theme.accentHover
                                 : band.hovered ? Theme.text : Theme.textSecondary
                            x: band.leftPadding + (band.availableWidth - width) / 2
                            y: band.topPadding + band.visualPosition * (band.availableHeight - height)
                        }
                    }
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: popup.freqs[index]
                        color: Theme.textTertiary
                        font.pixelSize: 11
                    }
                }
            }
        }

        Row {
            anchors.right: parent.right
            spacing: 10
            PillButton {
                text: "Restablecer"
                onClicked: popup.reset()
            }
            PillButton {
                primary: true
                text: "Cerrar"
                onClicked: popup.close()
            }
        }
    }
}
