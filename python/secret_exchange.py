"""Local-only implementation of PROTOCOL.md; cryptography supplies all primitives."""

import argparse
import base64
import binascii
import json
import os
import re
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

INFO = b"youtube-email-exchange-v1"


def encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii")


def decode(text: str) -> bytes:
    if not re.fullmatch(r"[A-Za-z0-9_-]*={0,2}", text):
        raise ValueError("Invalid Base64URL")
    return base64.b64decode(text + "=" * (-len(text) % 4), altchars=b"-_", validate=True)


def sized(data: bytes, length: int) -> bytes:
    if len(data) != length:
        raise ValueError("Invalid key or nonce length")
    return data


def derive_key(shared: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(), length=32, salt=bytes(32), info=INFO
    ).derive(shared)


def generate_keys() -> tuple[bytes, str]:
    private = X25519PrivateKey.generate()
    return private.private_bytes_raw(), encode(private.public_key().public_bytes_raw())


def encrypt(public_key: str, plaintext: str) -> str:
    recipient = X25519PublicKey.from_public_bytes(sized(decode(public_key), 32))
    ephemeral = X25519PrivateKey.generate()
    key = derive_key(ephemeral.exchange(recipient))
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    packet = {
        "epk": encode(ephemeral.public_key().public_bytes_raw()),
        "nonce": encode(nonce),
        "ct": encode(ciphertext),
    }
    return encode(json.dumps(packet, separators=(",", ":")).encode("utf-8"))


def decrypt(private_bytes: bytes, encoded_packet: str) -> str:
    packet = json.loads(decode(encoded_packet).decode("utf-8"))
    if not isinstance(packet, dict) or not all(
        isinstance(packet.get(name), str) for name in ("epk", "nonce", "ct")
    ):
        raise ValueError("Invalid packet")
    private = X25519PrivateKey.from_private_bytes(sized(private_bytes, 32))
    ephemeral = X25519PublicKey.from_public_bytes(sized(decode(packet["epk"]), 32))
    key = derive_key(private.exchange(ephemeral))
    nonce = sized(decode(packet["nonce"]), 12)
    ciphertext = decode(packet["ct"])
    if len(ciphertext) < 16:
        raise ValueError("Missing authentication tag")
    return AESGCM(key).decrypt(nonce, ciphertext, None).decode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    keygen = commands.add_parser("keygen", help="Create a private key; print the public key")
    keygen.add_argument("--key", default="private.key")
    seal = commands.add_parser("encrypt", help="Encrypt a UTF-8 file for a public key")
    seal.add_argument("public_key")
    seal.add_argument("--message-file", required=True)
    open_packet = commands.add_parser("decrypt", help="Decrypt a packet locally")
    open_packet.add_argument("packet")
    open_packet.add_argument("--key", default="private.key")
    args = parser.parse_args()
    try:
        if args.command == "keygen":
            private, public = generate_keys()
            descriptor = os.open(args.key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as file:
                file.write(private)
            print(public)
        elif args.command == "encrypt":
            print(encrypt(args.public_key, Path(args.message_file).read_bytes().decode("utf-8")))
        else:
            print(decrypt(Path(args.key).read_bytes(), args.packet))
    except (OSError, ValueError, InvalidTag, binascii.Error):
        parser.exit(1, "Operation failed. Check the command, files, key, and encrypted message.\n")


if __name__ == "__main__":
    main()
