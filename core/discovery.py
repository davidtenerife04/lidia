"""Anuncio del servidor en la red local mediante mDNS (servicio `_lidia._tcp`).

Usa `zeroconf`; si no está instalado, `Announcer.start()` devuelve False y la app sigue igual.
El PIN no se publica nunca.
"""
import socket

try:
    from zeroconf import ServiceInfo, Zeroconf
except ImportError:
    Zeroconf = None

SERVICE_TYPE = "_lidia._tcp.local."


def available():
    return Zeroconf is not None


class Announcer:
    def __init__(self, name, address, port, api=1):
        self.name, self.address, self.port, self.api = name, address, port, api
        self._zc = None
        self._info = None

    def start(self):
        if Zeroconf is None:
            return False
        try:
            self._info = ServiceInfo(
                SERVICE_TYPE,
                f"{self.name}.{SERVICE_TYPE}",
                addresses=[socket.inet_aton(self.address)],
                port=self.port,
                properties={"api": str(self.api), "app": "lidia", "tls": "1"},
            )
            self._zc = Zeroconf()
            self._zc.register_service(self._info)
            return True
        except Exception as e:
            print(f"No se pudo anunciar el servicio mDNS: {e}")
            self.stop()
            return False

    def stop(self):
        zc, self._zc = self._zc, None
        if zc is not None:
            try:
                if self._info is not None:
                    zc.unregister_service(self._info)
            finally:
                zc.close()
