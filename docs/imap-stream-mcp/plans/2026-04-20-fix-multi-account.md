# Fix multi-account: account parameter not wired through

## Problem

Multi-account infra on paikallaan (setup, keychain, session.py), mutta MCP-tool ei koskaan välitä `account`-parametria imap_client-funktioille. Kaikki operaatiot käyttävät aina default-accountia.

Kolme bugia:
1. `MailAction` (imap_stream_mcp.py:199) — puuttuu `account`-kenttä
2. `use_mail()` (imap_stream_mcp.py:~550-881) — ei välitä accountia mihinkään imap_client-kutsuun
3. `create_draft()` (imap_client.py:1042) ja `modify_draft()` (imap_client.py:1194) — `get_credentials()` ilman account-parametria → From-osoite aina default

## Goal

Kaikki imap-operaatiot toimivat oikealla tilillä kun `account` annetaan. Default-account toimii edelleen ilman `account`-parametria.

## Acceptance Criteria

- [ ] AC1: `MailAction` sisältää `account: str | None = None` kentän
- [ ] AC2: Kaikki imap_client-kutsut `use_mail()`-funktiossa välittävät `params.account`
  - `list_folders`, `list_messages`, `read_message`, `search_messages`, `edit_draft`, `create_draft`, `modify_draft`, `modify_flags`, `download_attachment`
- [ ] AC3: `create_draft()` ja `modify_draft()` kutsuvat `get_credentials(account)` eikä `get_credentials()`
- [ ] AC4: `accounts` help-teksti on linjassa toteutuksen kanssa
- [ ] AC5: Testit: account-parametrin välittyminen läpi ketjun

## Tasks

- [ ] 1. Lisää `account`-kenttä `MailAction`-luokkaan
- [ ] 2. Lisää `account=params.account` kaikkiin 9 imap_client-kutsuun `use_mail()`-funktiossa
- [ ] 3. Korjaa `get_credentials()` → `get_credentials(account)` kohdissa imap_client.py:1042 ja 1194
- [ ] 4. Kirjoita yksikkötestit: account-parametrin välittyminen (mock imap_client-funktiot, varmista account kulkee)
- [ ] 5. Aja testit: `uv run pytest`
- [ ] 6. Verify: manuaalinen testi kahdella tilillä

## Reflection

<!-- Written post-implementation by IMP -->
