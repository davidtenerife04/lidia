import QtQuick

// Portada cuadrada con esquinas redondeadas y placeholder.
// La miniatura (recorte, escalado y redondeo) la genera core/covers.py.
Item {
    id: root
    property string source: ""
    property real radiusRatio: 0.15          // radio relativo al lado (0..0.5)
    readonly property real radius: radiusRatio * width
    property int decodeSize: 160             // lado en píxeles de la miniatura
    readonly property bool ready: img.status === Image.Ready

    Rectangle {
        anchors.fill: parent
        radius: root.radius
        gradient: Gradient {
            GradientStop { position: 0.0; color: Theme.elevated }
            GradientStop { position: 1.0; color: Theme.surface }
        }
        Icon {
            anchors.centerIn: parent
            width: parent.width * 0.38
            height: width
            name: "songs"
            color: Theme.textTertiary
            visible: !root.ready
        }
    }

    Image {
        id: img
        anchors.fill: parent
        source: root.source !== ""
                ? "image://covers/" + root.decodeSize + ";" + root.radiusRatio + ";"
                  + encodeURIComponent(root.source)
                : ""
        fillMode: Image.Stretch
        asynchronous: true
        smooth: true
        mipmap: true
    }
}
