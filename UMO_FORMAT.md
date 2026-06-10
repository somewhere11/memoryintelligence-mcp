# `.umo` binary format — v1.0 (`0x0100`)

The canonical on-disk format for a Unified Memory Object. `src/mi_mcp/umo_format.py`
is the **executable reference** (producer + reader); the server-side serializer
(Path A / W1) MUST emit byte-identical files. Source: FEAT-0051 §5 (`umo-format-spec-public.html`).

## File layout (big-endian)

| Offset | Size | Field | Notes |
|---|---|---|---|
| `0x0000` | 4 | `magic` | `0x554D4F21` (`"UMO!"`) |
| `0x0004` | 2 | `format_version` | uint16 — `0x0100` |
| `0x0006` | 4 | `metadata_len` | uint32 |
| `0x000A` | n | `public_metadata` | UTF-8 JSON, **plaintext** |
| — | 2 | `key_slot_count` | uint16 |
| — | n | `key_slots[]` | one per reader (see below) |
| — | 12 | `gcm_iv` | AES-256-GCM nonce, plaintext |
| — | 4 | `payload_len` | uint32 |
| — | n | `encrypted_payload` | AES-256-GCM ciphertext (semantic+temporal+provenance) |
| — | 16 | `gcm_auth_tag` | GCM tag |
| `EOF-64` | 64 | `mi_signature` | Ed25519 over **all preceding bytes** |

`public_metadata` (plaintext, never encrypted): `umo_id` (ULID), `schema_version`,
`format_version`, `owner_did`, `content_type`, `created_at`, `source_count`,
`batch_id`, `mi_key_id`, `continuity_hash`.

## Key slot encoding (binary)

FEAT-0051 names the slot fields but not their byte framing; this is the canonical
encoding (one slot per authorized reader):

| Size | Field | Notes |
|---|---|---|
| 1 | `slot_id_len` | uint8 |
| n | `slot_id` | UTF-8 — e.g. `"owner"` or a delegation id |
| 1 | `scope_flags` | bitmask: `0x01`=semantic `0x02`=temporal `0x04`=provenance `0x08`=sources `0xFF`=all |
| 8 | `expires_at` | uint64 unix ts — `0` = no expiry |
| 32 | `owner_ephemeral_pubkey` | X25519 raw — the ECDH ephemeral public key |
| 2 | `wrapped_cek_len` | uint16 |
| m | `wrapped_cek` | AES-256-KW–wrapped content key (40 bytes for a 32-byte CEK) |

## Crypto

- **Payload:** AES-256-GCM under a per-UMO Content Encryption Key (CEK).
- **CEK wrap:** X25519 ECDH(ephemeral, recipient) → HKDF-SHA256(salt=`umo_id`,
  info=`umo-cek-wrap-v1`) → AES-256 key-wrap. One wrapped copy per slot.
- **Signature:** Ed25519 over all bytes before the signature, with MI's signing
  key (clients pin the public key by `mi_key_id`). Verifiable offline, no decryption.

## Owner key on Path A (important)

FEAT-0051's *owner* path uses a symmetric Master Key (Argon2id from a passphrase)
to wrap the CEK directly. That only works **client-side** (the owner's device holds
the key). For **Path A (server-side capture)** the server can only wrap for a
**public** key it's handed — so the **owner slot uses the X25519 ECDH path** (the
slot's `owner_ephemeral_pubkey`), i.e. the owner is "a reader of their own data."
The owner's X25519 private key lives in their Keychain; MI only ever sees the
public key (sent on capture) and therefore **cannot decrypt** the result.

(Client-side production — Path B / local-canonical — may additionally use the
symmetric Master-Key owner path; both are valid slot types.)

## Verification (offline)
1. Confirm magic `0x554D4F21`.
2. Read `public_metadata` → `mi_key_id`, `umo_id`, `continuity_hash`.
3. Resolve MI public key by `mi_key_id` (pinned in the client; no network).
4. Verify the Ed25519 signature over all bytes preceding it.
