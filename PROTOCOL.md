# Secret exchange protocol, version 1

This document is normative for both implementations. It retains the earlier chat's `youtube-email-exchange-v1` construction. It is a small hybrid encryption format, not HPKE, a signature scheme, or a full messaging protocol.

## Key material

The recipient generates an X25519 key pair using the library's secure key-generation facility. The private-key file contains exactly 32 raw private-key bytes. The public key is exactly 32 raw public-key bytes, encoded with Base64URL.

Private-key creation must be exclusive (fail if the target exists), with owner-only read/write permissions requested where the operating system supports them. Never publish the private key.

## Encryption

1. Decode and validate the recipient's 32-byte public key.
2. Generate a fresh ephemeral X25519 key pair for this message.
3. Compute X25519(ephemeral private key, recipient public key). Reject invalid agreement inputs, including an all-zero shared secret, using the cryptographic library.
4. Derive a 32-byte key with HKDF-SHA256:
   - input keying material: the X25519 shared secret;
   - salt: 32 zero bytes;
   - info: UTF-8 bytes of `youtube-email-exchange-v1`;
   - output length: 32 bytes.
5. Generate a cryptographically random 12-byte nonce.
6. Encrypt the UTF-8 message with AES-256-GCM, a 128-bit authentication tag, and empty additional authenticated data. Store ciphertext followed immediately by the 16-byte tag.
7. Encode this JSON object, using Base64URL for every binary field:

   ```json
   {"epk":"EPHEMERAL_PUBLIC_KEY","nonce":"NONCE","ct":"CIPHERTEXT_AND_TAG"}
   ```

8. Encode the UTF-8 JSON bytes with Base64URL. This single line is the public encrypted message.

JSON whitespace and field order are not cryptographic inputs and need not be identical between encoders. Encoders use compact JSON. No secret or private-key material is included in the packet.

## Base64URL

Use the URL-safe alphabet (`A-Z`, `a-z`, `0-9`, `-`, `_`). Encoders include standard trailing `=` padding. Decoders accept both padded and unpadded encodings. Copy only the printed line; do not insert spaces or line breaks. Malformed encodings must fail rather than being silently stripped of invalid characters.

## Decryption

Decode the outer Base64URL and parse the JSON. Require string fields `epk`, `nonce`, and `ct`. Unknown fields may be ignored. Require a 32-byte ephemeral public key, a 12-byte nonce, and ciphertext of at least 16 bytes. Require a 32-byte recipient private key.

Compute X25519(recipient private key, ephemeral public key), derive the same HKDF key, and authenticate/decrypt AES-GCM. Do not release unauthenticated plaintext. Wrong keys and modified packets must fail. Decode the authenticated plaintext as UTF-8. Implementations must not include key bytes or message contents in error output.

## Limits of the construction

Public-key distribution and sender identity are external to this format. There are no signatures, replay protection, expiry, traffic-analysis protection, or forward secrecy against later compromise of the recipient key. The protocol is meant for short contact details conveyed over an observable public forum. Implementations should not be used to process arbitrarily large untrusted packets as a public service.

## Compatibility fixture

`tests/vector.json` contains fixed public test keys, nonce, plaintext, and packet. These values are only for testing. Both implementations decrypt the fixture, and end-to-end tests generate fresh messages in both directions. Never use fixture keys or a fixed nonce for a real exchange.
