import { isUtf8 } from "node:buffer"
import { Effect, Layer, Schema, SchemaGetter } from "effect"
import { Aead, Kdf, KeyAgreement, SecureRandom } from "effect/crypto"

export const Utf8 = Schema.Uint8Array.check(
  Schema.makeFilter((bytes) => isUtf8(bytes), { expected: "valid UTF-8 bytes" })
).pipe(Schema.decodeTo(Schema.String, {
  decode: SchemaGetter.transform((bytes) => new TextDecoder("utf-8", { ignoreBOM: true }).decode(bytes)),
  encode: SchemaGetter.transform((text) => new TextEncoder().encode(text))
}))

const bytes32 = Schema.Uint8Array.check(Schema.isBetweenLength(32, 32))
export const PublicKey = Schema.Uint8ArrayFromBase64Url.pipe(Schema.decodeTo(bytes32))
export const PrivateKey = bytes32
const Nonce = Schema.Uint8ArrayFromBase64Url.pipe(
  Schema.decodeTo(Schema.Uint8Array.check(Schema.isBetweenLength(12, 12)))
)
const Ciphertext = Schema.Uint8ArrayFromBase64Url.pipe(
  Schema.decodeTo(Schema.Uint8Array.check(Schema.isMinLength(16)))
)
export const Packet = Schema.Uint8ArrayFromBase64Url.pipe(
  Schema.decodeTo(Utf8),
  Schema.decodeTo(Schema.fromJsonString(Schema.Struct({
    epk: PublicKey,
    nonce: Nonce,
    ct: Ciphertext
  })))
)

const info = new TextEncoder().encode("youtube-email-exchange-v1")
const deriveKey = Effect.fnUntraced(function*(shared: Uint8Array) {
  const kdf = yield* Kdf.Kdf
  const bytes = yield* kdf.derive(Kdf.hkdfSha256, shared, {
    salt: new Uint8Array(32), info, length: 32
  })
  return yield* Aead.key(Aead.aes256Gcm, bytes)
})

export const generateKeys = Effect.fnUntraced(function*() {
  const agreement = yield* KeyAgreement.KeyAgreement
  const pair = yield* agreement.generateKeyPair(KeyAgreement.x25519)
  return {
    privateKey: yield* KeyAgreement.toBytes(pair.privateKey),
    publicKey: yield* Schema.encodeEffect(PublicKey)(yield* KeyAgreement.toBytes(pair.publicKey))
  }
})

export const encrypt = Effect.fnUntraced(function*(publicKey: string, plaintext: string) {
  const agreement = yield* KeyAgreement.KeyAgreement
  const aead = yield* Aead.Aead
  const random = yield* SecureRandom.SecureRandom
  const recipient = yield* KeyAgreement.publicKey(
    KeyAgreement.x25519, yield* Schema.decodeUnknownEffect(PublicKey)(publicKey)
  )
  const ephemeral = yield* agreement.generateKeyPair(KeyAgreement.x25519)
  const shared = yield* agreement.deriveSharedSecret(ephemeral.privateKey, recipient)
  const key = yield* deriveKey(shared)
  const nonce = yield* random.randomBytes(12)
  const ct = yield* aead.encrypt(key, new TextEncoder().encode(plaintext), { nonce })
  return yield* Schema.encodeEffect(Packet)({
    epk: yield* KeyAgreement.toBytes(ephemeral.publicKey), nonce, ct
  })
})

export const decrypt = Effect.fnUntraced(function*(privateBytes: Uint8Array, text: string) {
  const agreement = yield* KeyAgreement.KeyAgreement
  const aead = yield* Aead.Aead
  const packet = yield* Schema.decodeUnknownEffect(Packet)(text)
  const privateKey = yield* KeyAgreement.privateKey(
    KeyAgreement.x25519, yield* Schema.decodeUnknownEffect(PrivateKey)(privateBytes)
  )
  const ephemeral = yield* KeyAgreement.publicKey(KeyAgreement.x25519, packet.epk)
  const shared = yield* agreement.deriveSharedSecret(privateKey, ephemeral)
  const key = yield* deriveKey(shared)
  const plaintext = yield* aead.decrypt(key, packet.ct, { nonce: packet.nonce })
  return yield* Schema.decodeUnknownEffect(Utf8)(plaintext)
})

export const CryptoLive = Layer.mergeAll(
  KeyAgreement.layerWebCrypto, Kdf.layerWebCrypto, Aead.layerWebCrypto
).pipe(Layer.provideMerge(SecureRandom.layerWebCrypto))
