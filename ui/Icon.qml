import QtQuick

// Iconos vectoriales dibujados en un lienzo de 24x24, sin depender de fuentes.
Canvas {
    id: c
    property string name: ""
    property color color: "white"
    property real lineWidth: 2

    implicitWidth: 24
    implicitHeight: 24

    onNameChanged: requestPaint()
    onColorChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()

    function tri(ctx, x1, y1, x2, y2, x3, y3) {
        ctx.beginPath();
        ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.lineTo(x3, y3);
        ctx.closePath();
        ctx.fill();
    }
    function line(ctx, x1, y1, x2, y2) {
        ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
    }

    onPaint: {
        var ctx = getContext("2d");
        ctx.reset();
        if (width <= 0 || height <= 0) return;
        var s = Math.min(width, height) / 24;
        ctx.scale(s, s);
        ctx.fillStyle = c.color;
        ctx.strokeStyle = c.color;
        ctx.lineWidth = c.lineWidth;
        ctx.lineCap = "round";
        ctx.lineJoin = "round";

        switch (c.name) {
        case "play":
            tri(ctx, 7, 4, 20, 12, 7, 20);
            break;
        case "pause":
            ctx.fillRect(6, 4, 4.2, 16);
            ctx.fillRect(13.8, 4, 4.2, 16);
            break;
        case "next":
            tri(ctx, 5, 5, 16, 12, 5, 19);
            ctx.fillRect(17.5, 5, 2.5, 14);
            break;
        case "prev":
            tri(ctx, 19, 5, 8, 12, 19, 19);
            ctx.fillRect(4, 5, 2.5, 14);
            break;
        case "shuffle":
            ctx.beginPath(); ctx.moveTo(3, 7); ctx.lineTo(7, 7);
            ctx.bezierCurveTo(14, 7, 10, 17, 17, 17); ctx.lineTo(19, 17); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(3, 17); ctx.lineTo(7, 17);
            ctx.bezierCurveTo(9, 17, 10, 16, 11, 14.8); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(13, 9.2);
            ctx.bezierCurveTo(14, 8, 15, 7, 17, 7); ctx.lineTo(19, 7); ctx.stroke();
            tri(ctx, 17, 4, 21.5, 7, 17, 10);
            tri(ctx, 17, 14, 21.5, 17, 17, 20);
            break;
        case "repeat":
        case "repeat1":
            ctx.beginPath(); ctx.moveTo(5, 12); ctx.lineTo(5, 10);
            ctx.quadraticCurveTo(5, 7, 8, 7); ctx.lineTo(17, 7); ctx.stroke();
            tri(ctx, 16.5, 4, 21, 7, 16.5, 10);
            ctx.beginPath(); ctx.moveTo(19, 12); ctx.lineTo(19, 14);
            ctx.quadraticCurveTo(19, 17, 16, 17); ctx.lineTo(7, 17); ctx.stroke();
            tri(ctx, 7.5, 14, 3, 17, 7.5, 20);
            if (c.name === "repeat1") {
                ctx.font = "bold 9px sans-serif";
                ctx.textAlign = "center";
                ctx.fillText("1", 12, 15);
            }
            break;
        case "volume":
        case "muted":
            ctx.beginPath();
            ctx.moveTo(3, 9); ctx.lineTo(7, 9); ctx.lineTo(12, 4.5);
            ctx.lineTo(12, 19.5); ctx.lineTo(7, 15); ctx.lineTo(3, 15);
            ctx.closePath(); ctx.fill();
            if (c.name === "volume") {
                ctx.beginPath(); ctx.arc(12, 12, 5, -0.9, 0.9); ctx.stroke();
                ctx.beginPath(); ctx.arc(12, 12, 9, -0.8, 0.8); ctx.stroke();
            } else {
                line(ctx, 16, 9, 21, 15);
                line(ctx, 21, 9, 16, 15);
            }
            break;
        case "search":
            ctx.beginPath(); ctx.arc(10.5, 10.5, 6, 0, Math.PI * 2); ctx.stroke();
            line(ctx, 15, 15, 20, 20);
            break;
        case "close":
            line(ctx, 6, 6, 18, 18);
            line(ctx, 18, 6, 6, 18);
            break;
        case "songs":
            ctx.beginPath(); ctx.arc(8, 17, 3.2, 0, Math.PI * 2); ctx.fill();
            ctx.fillRect(10.2, 5, 2, 12);
            tri(ctx, 12, 5, 19, 8.5, 12, 11.5);
            break;
        case "albums":
            ctx.beginPath(); ctx.arc(12, 12, 8.5, 0, Math.PI * 2); ctx.stroke();
            ctx.beginPath(); ctx.arc(12, 12, 2.6, 0, Math.PI * 2); ctx.fill();
            break;
        case "plus":
            line(ctx, 12, 5, 12, 19);
            line(ctx, 5, 12, 19, 12);
            break;
        case "refresh":
            ctx.beginPath(); ctx.arc(12, 12, 7.5, 0.6, Math.PI * 2 - 0.9); ctx.stroke();
            tri(ctx, 19.5, 3.5, 20, 11, 13, 8.5);
            break;
        case "queue":
            line(ctx, 3, 6, 15, 6);
            line(ctx, 3, 12, 15, 12);
            line(ctx, 3, 18, 10, 18);
            tri(ctx, 16, 13.5, 22, 17.5, 16, 21.5);
            break;
        case "queueAdd":
            line(ctx, 3, 6, 15, 6);
            line(ctx, 3, 12, 15, 12);
            line(ctx, 3, 18, 9, 18);
            line(ctx, 18, 14.5, 18, 21.5);
            line(ctx, 14.5, 18, 21.5, 18);
            break;
        case "grip":
            for (var gx = 9; gx <= 15; gx += 6)
                for (var gy = 6; gy <= 18; gy += 6) {
                    ctx.beginPath(); ctx.arc(gx, gy, 1.7, 0, Math.PI * 2); ctx.fill();
                }
            break;
        case "heart":
        case "heartOutline":
            ctx.beginPath();
            ctx.moveTo(12, 20.5);
            ctx.bezierCurveTo(5, 15, 2.5, 11.5, 2.5, 8);
            ctx.bezierCurveTo(2.5, 5.2, 4.6, 3.2, 7, 3.2);
            ctx.bezierCurveTo(9.2, 3.2, 11, 4.4, 12, 6.4);
            ctx.bezierCurveTo(13, 4.4, 14.8, 3.2, 17, 3.2);
            ctx.bezierCurveTo(19.4, 3.2, 21.5, 5.2, 21.5, 8);
            ctx.bezierCurveTo(21.5, 11.5, 19, 15, 12, 20.5);
            ctx.closePath();
            if (c.name === "heart") ctx.fill(); else ctx.stroke();
            break;
        case "playlist":
            line(ctx, 3, 6, 14, 6);
            line(ctx, 3, 11, 14, 11);
            line(ctx, 3, 16, 9, 16);
            ctx.beginPath(); ctx.arc(16.5, 17.5, 2.6, 0, Math.PI * 2); ctx.fill();
            line(ctx, 19, 17.5, 19, 7);
            break;
        case "trash":
            line(ctx, 4, 7, 20, 7);
            ctx.beginPath(); ctx.moveTo(6, 7); ctx.lineTo(7, 20); ctx.lineTo(17, 20); ctx.lineTo(18, 7); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(9.5, 7); ctx.lineTo(9.5, 4); ctx.lineTo(14.5, 4); ctx.lineTo(14.5, 7); ctx.stroke();
            line(ctx, 10, 11, 10, 16);
            line(ctx, 14, 11, 14, 16);
            break;
        case "edit":
            ctx.beginPath();
            ctx.moveTo(4.5, 19.5); ctx.lineTo(5.5, 14.5); ctx.lineTo(16, 4); ctx.lineTo(20, 8);
            ctx.lineTo(9.5, 18.5); ctx.closePath(); ctx.stroke();
            break;
        case "back":
            ctx.beginPath(); ctx.moveTo(15, 5); ctx.lineTo(8, 12); ctx.lineTo(15, 19); ctx.stroke();
            break;
        case "chevronDown":
            ctx.beginPath(); ctx.moveTo(5.5, 9); ctx.lineTo(12, 15.5); ctx.lineTo(18.5, 9); ctx.stroke();
            break;
        case "artist":
            ctx.beginPath(); ctx.arc(12, 8.3, 3.4, 0, Math.PI * 2); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(5, 20); ctx.bezierCurveTo(5, 14.6, 19, 14.6, 19, 20); ctx.stroke();
            break;
        case "lyrics":
            line(ctx, 3, 7, 16, 7);
            line(ctx, 3, 12, 16, 12);
            line(ctx, 3, 17, 12, 17);
            ctx.beginPath(); ctx.arc(15.9, 15, 2, 0, Math.PI * 2); ctx.fill();
            line(ctx, 17.9, 15.7, 17.9, 10);
            break;
        case "equalizer":
            ctx.fillRect(5, 11, 4, 8);
            ctx.fillRect(10, 6, 4, 13);
            ctx.fillRect(15, 8, 4, 11);
            break;
        case "settings":
            ctx.beginPath(); ctx.arc(12, 12, 3.2, 0, Math.PI * 2); ctx.stroke();
            for (var k = 0; k < 8; k++) {
                var a = k * Math.PI / 4;
                line(ctx, 12 + Math.cos(a) * 6.6, 12 + Math.sin(a) * 6.6,
                     12 + Math.cos(a) * 9.4, 12 + Math.sin(a) * 9.4);
            }
            ctx.beginPath(); ctx.arc(12, 12, 6.8, 0, Math.PI * 2); ctx.stroke();
            break;
        case "clock":
            ctx.beginPath(); ctx.arc(12, 12, 8, 0, Math.PI * 2); ctx.stroke();
            line(ctx, 12, 12, 12, 7.2);
            line(ctx, 12, 12, 15.2, 13.6);
            break;
        }
    }
}
