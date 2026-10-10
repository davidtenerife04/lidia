import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    property var root
    id: lyricsPanel
    anchors.right: parent.right
    anchors.top: parent.top
    z: 40
    width: root.lyricsOpen ? 360 : 0
    clip: true
    color: Theme.surface
    Behavior on width { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

    Rectangle {
        anchors.left: parent.left
        width: 1
        height: parent.height
        color: Theme.border
    }

    ListModel { id: lyricModel }

    Item {
        width: 360
        height: parent.height

        Item {
            id: lyricsHeader
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: 68

            Column {
                anchors.left: parent.left
                anchors.leftMargin: 22
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2
                Text {
                    text: "Letra"
                    color: Theme.text
                    font.pixelSize: 20
                    font.bold: true
                }
                Text {
                    width: 250
                    text: root.currentTitle
                    color: Theme.textSecondary
                    font.pixelSize: 12
                    elide: Text.ElideRight
                }
            }
            IconButton {
                anchors.right: parent.right
                anchors.rightMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                icon: "close"
                iconSize: 14
                size: 32
                tip: "Cerrar"
                onClicked: root.lyricsOpen = false
            }
            Rectangle {
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                height: 1
                color: Theme.border
            }
        }

        Column {
            anchors.centerIn: lyricList
            visible: lyricModel.count === 0
            spacing: 12

            Icon {
                anchors.horizontalCenter: parent.horizontalCenter
                width: 44; height: 44
                name: "lyrics"
                color: Theme.textTertiary
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Sin letra"
                color: Theme.textSecondary
                font.pixelSize: 15
            }
        }

        ListView {
            id: lyricList
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: lyricsHeader.bottom
            anchors.bottom: parent.bottom
            model: lyricModel
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: StyledScrollBar {}
            currentIndex: -1
            highlightFollowsCurrentItem: false
            spacing: 2
            topMargin: 8
            bottomMargin: 24

            onCurrentIndexChanged: {
                if (currentIndex >= 0)
                    positionViewAtIndex(currentIndex, ListView.Contain);
            }

            delegate: Item {
                id: lyricRow
                required property int index
                required property string text
                width: lyricList.width
                height: lineText.height + 8

                Text {
                    id: lineText
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.leftMargin: 24
                    anchors.rightMargin: 40
                    anchors.verticalCenter: parent.verticalCenter
                    text: lyricRow.text
                    color: lyricRow.index === lyricList.currentIndex ? Theme.accent : Theme.textSecondary
                    font.pixelSize: 15
                    font.bold: lyricRow.index === lyricList.currentIndex
                    lineHeight: 1.35
                    wrapMode: Text.Wrap
                }
            }
        }
    }

    function loadLyrics(path) {
        lyricModel.clear();
        lyricList.currentIndex = -1;
        if (!path) return;
        var rows = backend.lyrics(path);
        for (var i = 0; i < rows.length; i++)
            lyricModel.append({ time: rows[i].time, text: rows[i].text });
        updateLyric(root.currentTime);
    }

    function updateLyric(t) {
        var idx = -1;
        for (var i = 0; i < lyricModel.count; i++) {
            if (lyricModel.get(i).time <= t) idx = i;
            else break;
        }
        if (idx !== lyricList.currentIndex) {
            lyricList.currentIndex = idx;
            if (idx >= 0)
                lyricList.positionViewAtIndex(idx, ListView.Contain);
        }
    }
}
