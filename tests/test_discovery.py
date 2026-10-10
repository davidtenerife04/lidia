import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import discovery

pytestmark = pytest.mark.skipif(not discovery.available(), reason="zeroconf no instalado")


def test_announce_and_find():
    from zeroconf import Zeroconf
    a = discovery.Announcer("Lidia test", "127.0.0.1", 8765)
    assert a.start()
    zc = Zeroconf()
    try:
        info = None
        for _ in range(10):
            info = zc.get_service_info(discovery.SERVICE_TYPE, f"Lidia test.{discovery.SERVICE_TYPE}", timeout=1000)
            if info:
                break
            time.sleep(0.2)
        assert info is not None
        assert info.port == 8765
        assert info.properties[b"app"] == b"lidia"
        assert b"pin" not in info.properties
    finally:
        zc.close()
        a.stop()
