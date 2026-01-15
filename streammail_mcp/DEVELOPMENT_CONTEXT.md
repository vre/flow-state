# Streammail MCP - Kehityskonteksti

## Projektin tausta

Streammail on kevyt IMAP MCP-serveri Claudelle, inspiroitu Jesse Vincentin MCP-suunnittelufilosofiasta:
- https://blog.fsck.com/2025/10/19/mcps-are-not-like-other-apis/
- https://blog.fsck.com/2025/12/27/streamlinear/

**Pääperiaatteet:**
- Token-tehokkuus: ~500 tokenia vs tyypilliset 15,000+
- Yksi `use_mail` työkalu action-dispatcherilla (ei 25 erillistä työkalua)
- Self-documenting `help`-action
- Postel's Law: hyväksy joustavasti, ole tarkka outputissa

## Arkkitehtuuri

```
streammail_mcp/
├── pyproject.toml      # uv-projekti, riippuvuudet
├── streammail_mcp.py   # MCP server (FastMCP), yksi use_mail työkalu
├── imap_client.py      # IMAP-logiikka (imapclient-kirjasto)
├── setup.py            # Keychain-konfigurointi
├── debug_imap.py       # Debug-työkalu yhteysongelmiin
└── README.md           # Käyttöohjeet
```

## Toiminnot

```
use_mail(action, folder?, payload?, limit?)

Actions:
- list     - Listaa viestit kansiosta
- read     - Lue yksittäinen viesti (payload=msg_id)
- search   - Etsi viestejä (payload=query)
- draft    - Luo draft-vastaus (payload=JSON{to,subject,body,in_reply_to?})
- folders  - Listaa kansiot
- help     - Ohje (payload=topic)
```

## Turvallisuus

- Tunnukset macOS Keychainissa (ei tiedostoissa)
- Salasana haetaan vain IMAP-yhteyden avauksen yhteydessä
- Salasana ei koskaan näy lokeissa/outputissa

## Käyttöönotto

```bash
cd /Users/vre/work/streammail_mcp
uv sync
uv run python setup.py          # Konfiguroi IMAP
uv run python imap_client.py    # Testaa yhteys

# Claude Code:
claude mcp add streammail -- uv --directory /Users/vre/work/streammail_mcp run streammail
```

## Korjatut bugit

### TypeError: string pattern on bytes-like object
- **Ongelma:** IMAPClient palauttaa monia kenttiä `bytes`-tyyppisinä
- **Ratkaisu:** Lisätty `to_str()` helper ja korjattu `decode_header_value()` käsittelemään bytes

## Käyttäjän IMAP-asetukset

- Palvelin: mail.vre.iki.fi:993 (SSL/TLS)
- Käyttäjä: vre
- Kansiomuoto: `INBOX/Puljut/PLoP/Springer` (/-erotin)

## Seuraavat kehitysideat

1. **Attachment-tuki** - Liitteiden listaus ja lataus
2. **Useampi tili** - Tuki monelle IMAP-tilille
3. **Välimuisti** - Kansiolistaus/viestien cachetus
4. **Hakuoperaattorit** - Monimutkaisemmat hakukriteerit (AND/OR)
5. **Flag-hallinta** - Viestien merkitseminen luetuksi/tärkeäksi

## Hyödyllisiä komentoja

```bash
# Testaa MCP suoraan
uv run python streammail_mcp.py

# Debug IMAP-yhteys
uv run python debug_imap.py
uv run python debug_imap.py --debug  # Täysi protokollatrace

# Keychain-hallinta
uv run python setup.py --show   # Näytä config
uv run python setup.py --clear  # Poista tunnukset
```
