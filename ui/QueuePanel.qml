import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    property var root
    property alias queueList: queueList
    id: queuePanel
    anchors.right: parent.right
    anchors.top: parent.top
    width: root.queueOpen ? 340 : 0
    clip: true
    color: Theme.surface
    Behavior on width { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

    Rectangle { width: 1; height: parent.height; color: Theme.border }

    Item {
        width: 340
        height: parent.height

        // Cabecera
        Item {
            id: queueHeader
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: 78

            Column {
                anchors.left: parent.left
                anchors.leftMargin: 22
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2
                Text {
                    text: "Cola"
                    color: Theme.text
                    font.pixelSize: 20
                    font.bold: true
                }
                Text {
                    text: root.plural(queueModel.count, "canción", "canciones")
                          + (root.shuffle ? "  ·  aleatorio" : "")
                    color: Theme.textSecondary
                    font.pixelSize: 12
                }
            }
            Row {
                anchors.right: parent.right
                anchors.rightMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2
                IconButton {
                    visible: queueModel.count > 0
                    icon: "playlist"
                    iconSize: 17
                    size: 32
                    tip: "Guardar cola como lista"
                    onClicked: root.askName("saveQueue", "Guardar cola como lista", "Guardar", "", -1)
                }
                PillButton {
                    visible: queueModel.count > 1
                    implicitHeight: 32
                    text: "Vaciar"
                    onClicked: backend.queueClear()
                }
                IconButton {
                    icon: "close"
                    iconSize: 14
                    size: 32
                    tip: "Cerrar"
                    onClicked: root.queueOpen = false
                }
            }
            Rectangle {
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                height: 1
                color: Theme.border
            }
        }

        ListView {
            id: queueList
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: queueHeader.bottom
            anchors.bottom: parent.bottom
            model: queueModel
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: StyledScrollBar {}
            topMargin: 6
            bottomMargin: 12
            // Al reordenar, los demás elementos se desplazan con suavidad
            moveDisplaced: Transition { NumberAnimation { properties: "y"; duration: 150 } }

            delegate: Item {
                id: qrow
                required property int index
                required property string title
                required property string artist
                required property string cover
                required property int duration
                required property bool isCurrent

                width: ListView.view.width
                height: 58

                Rectangle {
                    id: qbody
                    width: parent.width
                    height: parent.height
                    color: "transparent"

                    Rectangle {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        radius: 10
                        color: qrow.isCurrent ? Theme.accentSoft
                             : (qHover.hovered ? Theme.hover : "transparent")
                    }

                    // El resto de pistas ya reproducidas se atenúan
                    opacity: (queueModel.currentIndex >= 0 && qrow.index < queueModel.currentIndex) ? 0.5 : 1

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (qrow.isCurrent) backend.togglePause();
                            else backend.queueJump(qrow.index);
                        }
                    }
                    HoverHandler { id: qHover }

                    CoverArt {
                        id: qcover
                        anchors.left: parent.left
                        anchors.leftMargin: 20
                        anchors.verticalCenter: parent.verticalCenter
                        width: 40; height: 40
                        radiusRatio: 0.17
                        decodeSize: 96
                        source: qrow.cover

                        EqBars {
                            anchors.centerIn: parent
                            visible: qrow.isCurrent && root.playing
                            color: Theme.text
                        }
                    }

                    Column {
                        anchors.left: qcover.right
                        anchors.leftMargin: 12
                        anchors.right: qActions.left
                        anchors.rightMargin: 6
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 2
                        Text {
                            width: parent.width
                            text: qrow.title
                            color: qrow.isCurrent ? Theme.accent : Theme.text
                            font.pixelSize: 14
                            font.bold: true
                            elide: Text.ElideRight
                        }
                        Text {
                            width: parent.width
                            text: qrow.artist
                            color: Theme.textSecondary
                            font.pixelSize: 12
                            elide: Text.ElideRight
                        }
                    }

                    Row {
                        id: qActions
                        anchors.right: parent.right
                        anchors.rightMargin: 14
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 0

                        IconButton {
                            visible: !qrow.isCurrent && qHover.hovered
                            size: 28
                            iconSize: 12
                            icon: "close"
                            tip: "Quitar de la cola"
                            onClicked: backend.queueRemove(qrow.index)
                        }

                        // Asa para arrastrar y reordenar
                        Item {
                            width: 28
                            height: 28
                            opacity: qHover.hovered || grip.drag.active ? 1 : 0.35

                            Icon {
                                anchors.centerIn: parent
                                width: 16; height: 16
                                name: "grip"
                                color: Theme.textSecondary
                            }
                            MouseArea {
                                id: grip
                                anchors.fill: parent
                                cursorShape: Qt.SizeVerCursor
                                drag.target: qbody
                                drag.axis: Drag.YAxis
                                drag.minimumY: -qrow.y
                                drag.maximumY: queueList.contentHeight - qrow.y - qrow.height
                                onPressed: qrow.z = 10
                                onReleased: {
                                    var to = Math.round((qrow.y + qbody.y) / qrow.height);
                                    to = Math.max(0, Math.min(queueModel.count - 1, to));
                                    qbody.y = 0;
                                    qrow.z = 0;
                                    if (to !== qrow.index) backend.queueMove(qrow.index, to);
                                }
                            }
                        }
                    }
                }
            }

            Text {
                anchors.centerIn: parent
                visible: queueModel.count === 0
                horizontalAlignment: Text.AlignHCenter
                text: "La cola está vacía.\nUsa los botones que aparecen\nal pasar el ratón por una canción."
                color: Theme.textSecondary
                font.pixelSize: 13
                lineHeight: 1.3
            }
        }
    }
}
