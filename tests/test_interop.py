"""Exercise the actual CLIs in both directions, including adversarial packets."""

import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
import secret_exchange as protocol


class InteroperabilityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.work = Path(self.directory.name)

    def run_cli(self, language, *args, succeeds=True):
        command = (
            [sys.executable, str(ROOT / "python/secret_exchange.py")]
            if language == "python"
            else ["node", "--import", "tsx", str(ROOT / "typescript/cli.ts")]
        )
        result = subprocess.run(
            [*command, *args], cwd=ROOT, capture_output=True, timeout=20
        )
        self.assertEqual(result.returncode == 0, succeeds, result.stderr)
        if not succeeds:
            self.assertEqual(result.stdout, b"")
        return result.stdout.decode("utf-8").removesuffix("\n")

    def make_key(self, language):
        key = self.work / f"{language}.key"
        public = self.run_cli(language, "keygen", "--key", str(key))
        self.assertEqual(len(key.read_bytes()), 32)
        self.assertEqual(len(protocol.decode(public)), 32)
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(key.stat().st_mode), 0o600)
        original = key.read_bytes()
        self.run_cli(language, "keygen", "--key", str(key), succeeds=False)
        self.assertEqual(key.read_bytes(), original)
        return key, public

    def test_cross_language_and_same_language_round_trips(self):
        for recipient in ("python", "typescript"):
            key, public = self.make_key(recipient)
            for sender in ("python", "typescript"):
                for message in ("", "person@example.com", "秘密 🔐\nTiếng Việt\n", "first\r\nsecond\rthird", "\ufeffBOM is content"):
                    with self.subTest(recipient=recipient, sender=sender, message=message):
                        file = self.work / "message.txt"
                        file.write_bytes(message.encode("utf-8"))
                        packet = self.run_cli(sender, "encrypt", "--message-file", str(file), "--", public)
                        self.assertEqual(
                            self.run_cli(recipient, "decrypt", "--key", str(key), "--", packet), message
                        )

    def test_public_key_starting_with_hyphen(self):
        # Public test material only: this key reliably exercises option parsing.
        private = bytes.fromhex("3802000000000000000000000000000000000000000000000000000000000000")
        public = protocol.encode(
            protocol.X25519PrivateKey.from_private_bytes(private).public_key().public_bytes_raw()
        )
        self.assertTrue(public.startswith("-"))
        key = self.work / "hyphen.key"
        key.write_bytes(private)
        file = self.work / "message.txt"
        file.write_text("hyphen key")
        for sender in ("python", "typescript"):
            packet = self.run_cli(sender, "encrypt", "--message-file", str(file), "--", public)
            for recipient in ("python", "typescript"):
                with self.subTest(sender=sender, recipient=recipient):
                    self.assertEqual(
                        self.run_cli(recipient, "decrypt", "--key", str(key), "--", packet),
                        "hyphen key",
                    )

    def test_fixed_protocol_vector(self):
        vector = json.loads((ROOT / "tests/vector.json").read_text())
        key = self.work / "vector.key"
        key.write_bytes(bytes.fromhex(vector["privateKeyHex"]))
        for language in ("python", "typescript"):
            with self.subTest(language=language):
                self.assertEqual(self.run_cli(language, "decrypt", "--key", str(key), "--", vector["packet"]), vector["plaintext"])

    def test_rejects_wrong_keys_tampering_and_malformed_packets(self):
        private, public = protocol.generate_keys()
        key = self.work / "recipient.key"
        key.write_bytes(private)
        valid = protocol.encrypt(public, "secret@example.com")
        fields = json.loads(protocol.decode(valid))
        cases = ["!", protocol.encode(b"not json"), protocol.encode(b"{}")]
        for field in ("epk", "nonce", "ct"):
            changed = dict(fields)
            data = bytearray(protocol.decode(changed[field]))
            data[0] ^= 1
            changed[field] = protocol.encode(data)
            cases.append(protocol.encode(json.dumps(changed).encode()))
            changed[field] = protocol.encode(b"short")
            cases.append(protocol.encode(json.dumps(changed).encode()))
        changed = dict(fields, epk=protocol.encode(bytes(32)))
        cases.append(protocol.encode(json.dumps(changed).encode()))
        cases.append(protocol.encrypt(protocol.generate_keys()[1], "other recipient"))
        for language in ("python", "typescript"):
            for index, packet in enumerate(cases):
                with self.subTest(language=language, case=index):
                    self.run_cli(language, "decrypt", "--key", str(key), "--", packet, succeeds=False)

    def test_encryption_is_fresh_and_invalid_public_keys_fail(self):
        _, public = protocol.generate_keys()
        file = self.work / "message.txt"
        file.write_text("same message")
        for language in ("python", "typescript"):
            a = self.run_cli(language, "encrypt", "--message-file", str(file), "--", public)
            b = self.run_cli(language, "encrypt", "--message-file", str(file), "--", public)
            self.assertNotEqual(a, b)
            self.assertNotEqual(json.loads(protocol.decode(a))["epk"], json.loads(protocol.decode(b))["epk"])
            for bad in ("!", protocol.encode(b"short"), protocol.encode(bytes(32))):
                self.run_cli(language, "encrypt", "--message-file", str(file), "--", bad, succeeds=False)

    def test_rejects_invalid_utf8_at_each_boundary(self):
        private, public = protocol.generate_keys()
        key = self.work / "recipient.key"
        key.write_bytes(private)
        message = self.work / "message.txt"
        for invalid in (b"\xff", b"\xc0\xaf", b"\xe2\x82", b"\xed\xa0\x80"):
            message.write_bytes(invalid)
            ephemeral = protocol.X25519PrivateKey.generate()
            recipient = protocol.X25519PublicKey.from_public_bytes(protocol.decode(public))
            shared_key = protocol.derive_key(ephemeral.exchange(recipient))
            nonce = os.urandom(12)
            fields = {
                "epk": protocol.encode(ephemeral.public_key().public_bytes_raw()),
                "nonce": protocol.encode(nonce),
                "ct": protocol.encode(protocol.AESGCM(shared_key).encrypt(nonce, invalid, None)),
            }
            packet = protocol.encode(json.dumps(fields).encode("utf-8"))
            invalid_json_utf8 = protocol.encode(
                json.dumps(dict(fields, extra="MARKER")).encode().replace(b"MARKER", invalid)
            )
            for language in ("python", "typescript"):
                with self.subTest(language=language, invalid=invalid.hex()):
                    self.run_cli(language, "encrypt", "--message-file", str(message), "--", public, succeeds=False)
                    self.run_cli(language, "decrypt", "--key", str(key), "--", packet, succeeds=False)
                    self.run_cli(language, "decrypt", "--key", str(key), "--", invalid_json_utf8, succeeds=False)


if __name__ == "__main__":
    unittest.main()
