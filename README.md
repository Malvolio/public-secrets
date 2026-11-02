# Public Secrets

Exchange a private contact address through a public comment thread. One person posts a public key; the other posts an encrypted message. Only the holder of the private key can decrypt it.

## Choose your language

**You only need one language: Python or TypeScript. The choice is up to each user.** Choose whichever you prefer, follow only its setup instructions, and use only its commands below. You do not need to install or run both.

Participants can choose independently: one person can use Python while the other uses TypeScript. Both use the same protocol. The optional **LLM-assisted route** also uses that protocol.

| Your preference | Start here | Where secrets are processed |
| --- | --- | --- |
| Python | [Python setup](#python) | Your computer |
| TypeScript / Effect | [TypeScript setup](#typescript) | Your computer |
| An LLM that can execute Python | [LLM-assisted instructions](LLM-GUIDE.md) | The model's execution environment; usually the provider's servers |

The local tools run without an application server and make no network requests after dependency installation. The LLM route trades local-only privacy for convenience. ChatGPT and Anthropic's Claude are examples of assistants you might use, **if your particular session can actually execute Python with the required library**. A frontier model without execution tools cannot do this reliably.

## The conversation

### You want someone to send you a secret

Generate a key first using the instructions below. Post your public key and a link to this repo together:

> You can send me your email address privately using this repo: https://github.com/Malvolio/public-secrets. My public key is PUBLIC_KEY. Follow its setup and sender instructions, then reply here with the encrypted output. Keep your original message private.

Replace `PUBLIC_KEY` with the printed public key. The other person encrypts their address locally and posts the output. You decrypt their reply locally. This needs **two public posts**: your key and invitation, then their encrypted reply.

### You want to send someone a secret

If the other person has not already published a key, first ask them to create one:

> I'd like to send you my email address privately. This repo explains how: https://github.com/Malvolio/public-secrets. Please follow its setup and recipient instructions, then reply here with your public key. Keep the private-key file to yourself. I'll encrypt my address for your public key and post the encrypted reply here.

After they post their public key, copy it from their actual account, encrypt your address locally, and post the encrypted output. They decrypt it locally. This needs **three public posts**: your request, their key, then your encrypted reply. If they already published a suitable key, you can encrypt to it immediately.

The recipient generates the key, keeps the private-key file, and publishes only the public key. To exchange secrets in both directions, repeat with the roles reversed.

## Set up once

Download this repository using GitHub's **Code → Download ZIP**, extract it, and open a terminal in the extracted folder. Or clone it with Git. Complete **only one** of the two setup sections below, according to your choice.

### Python

Requires Python 3.10 or newer. The only direct dependency is the established [cryptography library](https://cryptography.io/).

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows use `py -3` instead of `python3` to create the environment, then `.venv\Scripts\Activate.ps1` in PowerShell to activate it.

### TypeScript

Requires Node.js 22.19 or newer and npm. Uses Effect 4.1.1 and its Node platform services; `tsx` runs the source directly.

```sh
npm ci
```

## Recipient: create a key

Run **only the command for your chosen language**:

**Python:**

```sh
python python/secret_exchange.py keygen
```

**TypeScript:**

```sh
npm run --silent secret -- keygen
```

The command prints your **public key**. Post that entire line in the public conversation.

It also creates `private.key` in your current folder. **Keep this file private. Never post, send, or commit it.** The command refuses to overwrite an existing file. For a separate exchange, use `keygen --key another-private.key` and remember which key belongs to which conversation.

## Sender: encrypt your secret

Use a local text editor to create a UTF-8 file named `message.txt` containing your email address or other short message. Replace `PUBLIC_KEY` below with the recipient's public key, keeping the quotes. Run **only the command for your chosen language**.

**Python:**

```sh
python python/secret_exchange.py encrypt "PUBLIC_KEY" --message-file message.txt
```

**TypeScript:**

```sh
npm run --silent secret -- encrypt "PUBLIC_KEY" --message-file message.txt
```

Post the entire printed line as your public reply. **Do not post the original text file.** Reading the secret from a file keeps it out of command history and process arguments. The local file still contains the secret; store or remove it according to your needs.

## Recipient: decrypt the reply

Replace `ENCRYPTED_MESSAGE` with the entire encrypted reply. In the folder containing your private key, run **only the command for your chosen language**:

**Python:**

```sh
python python/secret_exchange.py decrypt "ENCRYPTED_MESSAGE"
```

**TypeScript:**

```sh
npm run --silent secret -- decrypt "ENCRYPTED_MESSAGE"
```

The secret appears in your terminal. If you chose another key filename, add `--key another-private.key`. Keep terminal output private too.

## How the encryption works

The tools use **X25519, an elliptic-curve Diffie–Hellman key agreement**. The sender creates a fresh temporary key pair and combines its private key with the recipient's public key to compute a shared secret. The recipient computes the same secret using their private key and the sender's temporary public key, which travels with the encrypted message. The private keys and shared secret are never posted.

HKDF-SHA256 derives an encryption key from that shared secret. AES-256-GCM then encrypts the message and detects changes to the encrypted data. Diffie–Hellman provides the key agreement; AES-GCM protects the message. This does not prove the sender's identity, and you must obtain the recipient's public key from the right person.

See [PROTOCOL.md](PROTOCOL.md) for the exact format and algorithms.

## What you are trusting

Read [the Python code](python/secret_exchange.py) or [the TypeScript protocol](typescript/protocol.ts) and [CLI](typescript/cli.ts). The visible flow is: load a key, use library crypto, encode or decode a packet, print the result. There are no network clients, analytics, accounts, application servers, or custom encryption primitives. Dependency installation does contact package registries. You still trust your computer, runtime, installed dependencies, and the source you run.

- **Verify the public key's source.** Encryption does not establish identity. Use the intended person's actual account; a substituted key lets its owner read what you encrypt.
- **Anyone can encrypt to a public key.** Successful decryption authenticates the ciphertext's integrity, not the sender's identity. Replies and later emails can be impersonated; verify identities separately when needed.
- **Public posts remain public.** Message length, account names, timing, and the existence of the exchange are visible. The forum can remove or alter posts. Altered ciphertext will fail authentication, but a valid old message can be replayed.
- **Protect the private key.** It is stored unencrypted. Owner-only creation permissions are requested on POSIX systems; Windows users should check folder permissions. A later private-key compromise exposes previously recorded messages for that key. Fresh sender keys do not provide forward secrecy against recipient-key compromise.
- **This exchanges a secret, not an ongoing secure chat.** Prefer a suitable private messaging service for the conversation that follows. Disposable public inboxes are not private mailboxes.

The code and tests are inspectable, but this project has not received an independent security audit.

## For contributors

[PROTOCOL.md](PROTOCOL.md) defines the wire format. Cross-language compatibility must stay intact. The TypeScript API returns Effects directly; JSON and Base64URL go through Schema, crypto comes from Effect services, and file operations use Effect FileSystem. Only the CLI supplies live layers and runs the program.

After Python setup and `npm ci`:

```sh
npm run typecheck
python -m unittest discover -s tests -v
```

The suite runs the actual CLIs in both directions and in each language, including empty and Unicode messages, mixed line endings, and a leading byte-order mark. It checks a fixed public test vector, tampering, malformed packets, invalid UTF-8, invalid public keys, wrong recipient keys, fresh encryption, key permissions, and refusal to overwrite keys. The tests use temporary files and need no network access.

## Support this project

If you find this project useful, you can [buy me a coffee](https://buymeacoffee.com/michaellorton).
