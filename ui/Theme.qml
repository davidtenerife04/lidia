pragma Singleton
import QtQuick

QtObject {
    property bool dark: true

    readonly property color bg: dark ? "#0c0c0f" : "#f6f6f8"
    readonly property color sidebar: dark ? "#09090b" : "#ececf0"
    readonly property color surface: dark ? "#131317" : "#ffffff"
    readonly property color elevated: dark ? "#1d1d23" : "#ffffff"
    readonly property color hover: dark ? "#14ffffff" : "#12000000"
    readonly property color border: dark ? "#1cffffff" : "#1c000000"
    readonly property color track: dark ? "#2e2e36" : "#d9d9e0"

    readonly property color text: dark ? "#f4f4f6" : "#16161a"
    readonly property color textSecondary: dark ? "#a1a1ab" : "#55555f"
    readonly property color textTertiary: dark ? "#62626d" : "#8a8a95"

    readonly property color accent: dark ? "#8b7bff" : "#6a58f0"
    readonly property color accentHover: dark ? "#a295ff" : "#5543d8"
    readonly property color accentSoft: dark ? "#228b7bff" : "#226a58f0"
    readonly property color accentText: dark ? "#0c0c0f" : "#ffffff"

    readonly property string logo: dark ? "logo-white-64.png" : "logo-64.png"
}
