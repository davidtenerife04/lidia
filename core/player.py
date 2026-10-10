import threading
import time

import mpv

EQ_FREQUENCIES = (31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)
FADE_STEP = 0.05


class AudioPlayer:
    """Envoltorio de mpv. Los callbacks se ejecutan en el hilo de eventos de mpv.

    Para el crossfade se usan dos instancias de mpv: `self.player` es la activa y
    la otra queda en reposo hasta que hay que mezclar con la pista siguiente.
    """

    def __init__(self, on_time_update=None, on_track_end=None,
                 on_duration_update=None, on_playing_change=None,
                 on_auto_advance=None):
        self.on_time_update = on_time_update
        self.on_track_end = on_track_end
        self.on_duration_update = on_duration_update
        self.on_playing_change = on_playing_change
        self.on_auto_advance = on_auto_advance

        self._eof_triggered = False
        self._preloaded = None
        self._volume = 100.0
        self._replaygain = "track"
        self._af = ""
        self._duration = 0.0

        self._xf_secs = 0.0
        self._xf_path = None
        self._xf_started = False
        self._fade_id = 0
        self._fade_old = None
        self._gain_active = 1.0
        self._gain_old = 0.0

        self.player = None
        self._spare = None
        self.player = self._make_player()
        self._spare = self._make_player()

    def _make_player(self):
        # keep_open: al terminar el archivo mpv se queda parado al final y pone
        # eof-reached=True, que es la señal fiable de "pista terminada".
        p = mpv.MPV(video=False, ytdl=False, keep_open="yes",
                    audio_display="no", gapless_audio="yes",
                    replaygain=self._replaygain, replaygain_fallback="-6")

        @p.property_observer('path')
        def _path(_name, value):
            if p is not self.player:
                return
            # mpv pasó solo a la pista precargada (reproducción sin pausa)
            if value is not None and self._preloaded is not None and value == self._preloaded:
                self._preloaded = None
                self._eof_triggered = False
                if self.on_auto_advance:
                    self.on_auto_advance()

        @p.property_observer('time-pos')
        def _time(_name, value):
            if p is not self.player or value is None:
                return
            if self.on_time_update:
                self.on_time_update(float(value))
            self._check_crossfade(float(value))

        @p.property_observer('duration')
        def _duration(_name, value):
            if p is not self.player or value is None:
                return
            self._duration = float(value)
            if self.on_duration_update:
                self.on_duration_update(float(value))

        @p.property_observer('eof-reached')
        def _eof(_name, value):
            if p is not self.player:
                return
            if value and not self._eof_triggered and self._preloaded is None:
                self._eof_triggered = True
                if self.on_track_end:
                    self.on_track_end()

        @p.property_observer('pause')
        def _pause(_name, value):
            if p is not self.player:
                return
            if value is not None and self.on_playing_change:
                self.on_playing_change(not value)

        return p

    def preload(self, filepath):
        """Encola la siguiente pista para que mpv enlace sin hueco al terminar la actual."""
        if filepath == self._preloaded:
            return
        try:
            self.player.command("playlist-clear")
            self._preloaded = filepath
            if filepath:
                self.player.command("loadfile", filepath, "append")
            else:
                self._preloaded = None
        except Exception as e:
            self._preloaded = None
            print(f"Error precargando la siguiente pista: {e}")

    def clear_preload(self):
        self.preload(None)

    def set_crossfade(self, seconds):
        self._xf_secs = max(0.0, min(10.0, float(seconds or 0)))

    def set_crossfade_next(self, filepath):
        """Pista con la que se mezclará la actual cuando falten `crossfade` segundos."""
        self._xf_path = filepath
        self._xf_started = False

    def _check_crossfade(self, pos):
        if (self._xf_secs <= 0 or not self._xf_path or self._xf_started
                or self._duration <= 0):
            return
        fade = min(self._xf_secs, self._duration / 2)
        if self._duration - pos <= fade:
            self._start_crossfade(self._xf_path, fade)

    def _start_crossfade(self, filepath, seconds):
        self._xf_started = True
        self._xf_path = None
        old, new = self.player, self._spare
        self._cancel_fade()
        try:
            new.af = self._af
            new.pause = False
            self._gain_active, self._gain_old = 0.0, 1.0
            self._apply_volume(new, 0.0)
            self._duration = 0.0
            self._eof_triggered = False
            self._preloaded = None
            self._fade_old = old
            self.player, self._spare = new, old
            new.play(filepath)
            new.pause = False
        except Exception as e:
            print(f"Error iniciando el crossfade: {e}")
            return
        if self.on_auto_advance:
            self.on_auto_advance()
        fade_id = self._fade_id
        threading.Thread(target=self._run_fade, args=(fade_id, new, old, seconds),
                         daemon=True).start()

    def _run_fade(self, fade_id, new, old, seconds):
        steps = max(1, int(seconds / FADE_STEP))
        for i in range(1, steps + 1):
            time.sleep(FADE_STEP)
            if fade_id != self._fade_id:
                return
            f = i / steps
            self._gain_active, self._gain_old = f, 1.0 - f
            self._apply_volume(new, self._gain_active)
            self._apply_volume(old, self._gain_old)
        if fade_id == self._fade_id:
            self._finish_fade(old)

    def _finish_fade(self, old):
        self._gain_active, self._gain_old = 1.0, 0.0
        self._fade_old = None
        try:
            old.stop()
            self._apply_volume(old, 1.0)
        except Exception:
            pass

    def _cancel_fade(self):
        """Interrumpe una mezcla en curso dejando la pista activa a volumen completo."""
        self._fade_id += 1
        old, self._fade_old = self._fade_old, None
        self._gain_active, self._gain_old = 1.0, 0.0
        if old is not None:
            try:
                old.stop()
                self._apply_volume(old, 1.0)
            except Exception:
                pass
        self._apply_volume(self.player, 1.0)

    def _apply_volume(self, p, gain):
        try:
            p.volume = max(0.0, min(100.0, self._volume)) * gain
        except Exception:
            pass

    def set_replaygain(self, enabled):
        self._replaygain = "track" if enabled else "no"
        for p in (self.player, self._spare):
            try:
                p.replaygain = self._replaygain
            except Exception as e:
                print(f"Error cambiando ReplayGain: {e}")

    def play(self, filepath, start=0.0, paused=False):
        self._preloaded = None
        self._eof_triggered = False
        self._xf_started = False
        self._duration = 0.0
        self._cancel_fade()
        # keep-open deja el player pausado tras el EOF, así que se fija siempre
        # (antes y después de cargar, porque mpv puede conservar la pausa del EOF)
        self.player.pause = bool(paused)
        if start and start > 0:
            self.player.loadfile(filepath, start=f"{start:.3f}")
        else:
            self.player.play(filepath)
        self.player.pause = bool(paused)

    def set_pause(self, paused):
        if self.player.path is not None:
            self.player.pause = bool(paused)
            if self._fade_old is not None:
                self._fade_old.pause = bool(paused)

    def toggle_pause(self):
        if self.player.path is not None:
            self.set_pause(not self.player.pause)

    def stop(self):
        self._preloaded = None
        self._xf_started = True
        self._cancel_fade()
        self.player.stop()

    def set_volume(self, volume):
        self._volume = max(0, min(100, volume))
        self._apply_volume(self.player, self._gain_active)
        if self._fade_old is not None:
            self._apply_volume(self._fade_old, self._gain_old)

    def set_equalizer(self, gains):
        """Aplica ganancias (dB) en 10 bandas encadenando filtros `equalizer` de mpv."""
        filters = []
        for freq, gain in zip(EQ_FREQUENCIES, gains):
            if gain:
                filters.append(f"equalizer=f={freq}:t=o:w=1:g={gain:g}")
        self._af = ",".join(filters)  # cadena vacía si todas las bandas son 0
        for p in (self.player, self._spare):
            try:
                p.af = self._af
            except Exception as e:
                print(f"Error aplicando el ecualizador: {e}")

    def seek(self, seconds, absolute=True):
        try:
            if self.player.path is None:
                return
            self._eof_triggered = False  # permite volver a detectar el final
            self.player.seek(max(0.0, seconds),
                             reference="absolute" if absolute else "relative")
        except Exception:
            pass

    def terminate(self):
        self._fade_id += 1
        for p in (self.player, self._spare):
            try:
                p.terminate()
            except Exception:
                pass

    @property
    def is_playing(self):
        return not self.player.pause and self.player.path is not None
