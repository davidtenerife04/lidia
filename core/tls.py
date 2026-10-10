"""Certificado TLS autofirmado para el servidor.

Se genera una vez y se guarda en `cert_dir`. Los clientes no confían en una CA:
fijan la huella SHA-256 que la aplicación muestra en Ajustes.
"""
import datetime
import hashlib
import os
import socket
import ssl
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

CERT_NAME = "server.crt"
KEY_NAME = "server.key"
VALID_DAYS = 3650


def _generate(cert_path, key_path):
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Lidia")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(name).issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=VALID_DAYS))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("lidia.local"),
                                                        x509.DNSName(socket.gethostname())]), critical=False)
            .sign(key, hashes.SHA256()))
    key_bytes = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption())
    fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(key_bytes)
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def ensure_certificate(cert_dir):
    """Devuelve (ruta_cert, ruta_clave), creándolos si no existen o están incompletos."""
    cert_dir = Path(cert_dir)
    cert_dir.mkdir(parents=True, exist_ok=True)
    cert_path, key_path = cert_dir / CERT_NAME, cert_dir / KEY_NAME
    if not (cert_path.is_file() and key_path.is_file()):
        _generate(cert_path, key_path)
    return cert_path, key_path


def fingerprint(cert_path):
    """Huella SHA-256 del certificado en formato AA:BB:CC..."""
    der = ssl.PEM_cert_to_DER_cert(Path(cert_path).read_text())
    digest = hashlib.sha256(der).hexdigest().upper()
    return ":".join(digest[i:i + 2] for i in range(0, len(digest), 2))


def server_context(cert_path, key_path):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(cert_path, key_path)
    return ctx
