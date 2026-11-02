import { NodeRuntime, NodeServices } from "@effect/platform-node"
import { Console, Effect, FileSystem, Schema } from "effect"
import { Argument, Command, Flag } from "effect/cli"
import { CryptoLive, decrypt, encrypt, generateKeys, Utf8 } from "./protocol.js"

const keyFile = Flag.String("key").pipe(Flag.withDefault("private.key"))
const keygen = Command.make("keygen", { key: keyFile }, Effect.fnUntraced(function*({ key }) {
  const fs = yield* FileSystem.FileSystem
  const pair = yield* generateKeys()
  yield* fs.writeFile(key, pair.privateKey, { flag: "wx", mode: 0o600 })
  yield* Console.log(pair.publicKey)
}))

const seal = Command.make("encrypt", {
  publicKey: Argument.String("public-key"),
  messageFile: Flag.String("message-file")
}, Effect.fnUntraced(function*({ publicKey, messageFile }) {
  const fs = yield* FileSystem.FileSystem
  const message = yield* Schema.decodeUnknownEffect(Utf8)(yield* fs.readFile(messageFile))
  yield* Console.log(yield* encrypt(publicKey, message))
}))

const open = Command.make("decrypt", {
  packet: Argument.String("packet"), key: keyFile
}, Effect.fnUntraced(function*({ key, packet }) {
  const fs = yield* FileSystem.FileSystem
  yield* Console.log(yield* decrypt(yield* fs.readFile(key), packet))
}))

Command.make("public-secrets").pipe(
  Command.withSubcommands([keygen, seal, open]),
  Command.run({ version: "1.0.0" }),
  Effect.provide(CryptoLive),
  Effect.provide(NodeServices.layer),
  Effect.matchEffect({
    onFailure: () => Console.error("Operation failed. Check the command, files, key, and encrypted message.").pipe(
      Effect.andThen(Effect.sync(() => { process.exitCode = 1 }))
    ),
    onSuccess: () => Effect.void
  }),
  NodeRuntime.runMain
)
