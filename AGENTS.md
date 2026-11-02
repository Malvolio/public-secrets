# Project conventions

Read `node_modules/effect/AGENTS.md` completely before writing Effect code, and follow its relevant references. Use the installed source to resolve API questions.

TypeScript is strictly Effect-first: Schema for boundaries and JSON, Effect crypto services, Effect filesystem and CLI services. Do not introduce JavaScript try/catch, Effect.try/tryPromise, or catch combinators without first discussing the need with the user. Use native typed effects and match at the application boundary.

Keep both implementations small and inspectable. No network requests, telemetry, custom cryptographic primitives, or secret logging. Preserve PROTOCOL.md and cross-language compatibility.
