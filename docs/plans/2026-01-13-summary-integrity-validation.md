# Summary Integrity Validation

## Ongelma

`check_existing.py` tunnistaa vain v1 vs v2 formaatin (`detect_v1_summary`), mutta EI havaitse:
1. Tyhjää summaryä (vain `## Summary` otsikko ilman sisältöä)
2. Puuttuvia pakollisia elementtejä (TL;DR, metadata-kentät)
3. Epäonnistunutta prosessointia (keskeytetty, crashannut)

Seuraus: Käyttäjälle näytetään "v2.0 - Ajan tasalla" vaikka tiedosto on rikki.

## Ratkaisu

Lisätään `validate_summary_integrity()` -funktio joka tarkistaa onko tiedosto onnistuneesti käsitelty.

### Validoitavat elementit

**Summary-tiedosto** (`youtube - {title} ({VIDEO_ID}).md`):
```
PAKOLLINEN:
- ## Video -osio
  - **Title:** (ei tyhjä)
  - **Engagement:** (views, likes, comments)
  - **Published:** ja Extracted:
- ## Summary -osio
  - **TL;DR**: (vähintään 20 merkkiä)
  - Sisältöä otsikon jälkeen (vähintään 100 merkkiä)

VALINNAINEN:
- **Tags:**
- ## Hidden Gems
```

**Transcript-tiedosto** (`youtube - {title} - transcript ({VIDEO_ID}).md`):
```
PAKOLLINEN:
- ## Description -osio (voi olla tyhjä)
- ## Transcription -osio (vähintään 500 merkkiä)
```

**Comments-tiedosto** (`youtube - {title} - comments ({VIDEO_ID}).md`):
```
PAKOLLINEN:
- ## Comment Insights -osio (vähintään 100 merkkiä)
```

### Paluuarvo

`check_existing()` palauttaa laajennettuna:
```python
{
    "video_id": "xxx",
    "exists": true,
    "summary_file": "/path/to/file.md",
    "comment_file": null,
    "transcript_file": "/path/to/transcript.md",

    # Nykyiset
    "summary_v1": false,
    "comments_v1": null,
    "stored_metadata": {...},

    # UUDET
    "summary_valid": true,      # Kaikki pakolliset elementit OK
    "summary_issues": [],       # Lista puuttuvista/rikkinäisistä
    "transcript_valid": true,
    "transcript_issues": [],
    "comments_valid": null,     # null jos tiedostoa ei ole
    "comments_issues": null
}
```

## Toteutus

### Vaihe 1: Lisää validointifunktiot `check_existing.py`:iin

```python
def validate_summary_integrity(content: str) -> tuple[bool, list[str]]:
    """
    Validate that summary file has all required elements.
    Returns (is_valid, list_of_issues).
    """
    issues = []

    # Check ## Video section
    if "## Video" not in content:
        issues.append("missing_video_section")
    else:
        if "**Title:**" not in content or re.search(r'\*\*Title:\*\*\s*\n', content):
            issues.append("empty_title")
        if "**Engagement:**" not in content:
            issues.append("missing_engagement")
        if "**Published:**" not in content:
            issues.append("missing_published")

    # Check ## Summary section
    summary_match = re.search(r'## Summary\s*\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
    if not summary_match:
        issues.append("missing_summary_section")
    else:
        summary_text = summary_match.group(1).strip()
        if len(summary_text) < 100:
            issues.append("summary_too_short")
        if "**TL;DR**" not in summary_text:
            issues.append("missing_tldr")

    return (len(issues) == 0, issues)


def validate_transcript_integrity(content: str) -> tuple[bool, list[str]]:
    """Validate transcript file has required elements."""
    issues = []

    if "## Transcription" not in content:
        issues.append("missing_transcription_section")
    else:
        trans_match = re.search(r'## Transcription\s*\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
        if trans_match and len(trans_match.group(1).strip()) < 500:
            issues.append("transcription_too_short")

    return (len(issues) == 0, issues)


def validate_comments_integrity(content: str) -> tuple[bool, list[str]]:
    """Validate comments file has required elements."""
    issues = []

    if "## Comment Insights" not in content:
        issues.append("missing_insights_section")
    else:
        insights_match = re.search(r'## Comment Insights\s*\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
        if insights_match and len(insights_match.group(1).strip()) < 100:
            issues.append("insights_too_short")

    return (len(issues) == 0, issues)
```

### Vaihe 2: Laajenna `check_existing()` -funktiota

Lisää validointikutsut rivien 155-165 jälkeen:

```python
# Validate summary integrity
if files["summary_file"]:
    content = Path(files["summary_file"]).read_text()
    result["summary_v1"] = detect_v1_summary(content)
    result["stored_metadata"] = extract_metadata_from_file(content)
    # NEW: Integrity check
    valid, issues = validate_summary_integrity(content)
    result["summary_valid"] = valid
    result["summary_issues"] = issues

# Validate transcript integrity
if files["transcript_file"]:
    content = Path(files["transcript_file"]).read_text()
    valid, issues = validate_transcript_integrity(content)
    result["transcript_valid"] = valid
    result["transcript_issues"] = issues

# Validate comments integrity
if files["comment_file"]:
    content = Path(files["comment_file"]).read_text()
    result["comments_v1"] = detect_v1_comments(content)
    # NEW: Integrity check
    valid, issues = validate_comments_integrity(content)
    result["comments_valid"] = valid
    result["comments_issues"] = issues
```

### Vaihe 3: Päivitä SKILL.md käyttämään uusia kenttiä

Lisää Step 0 jälkeiseen logiikkaan:
```markdown
Jos `summary_valid: false`:
- Näytä issues-lista käyttäjälle
- Ehdota: "Tiedosto on epätäydellinen. Haluatko prosessoida uudelleen?"
```

## Tiedostot

| Tiedosto | Muutos |
|----------|--------|
| `check_existing.py` | +3 validointifunktiota, laajennettu check_existing() |
| `SKILL.md` | Päivitetty logiikka käsittelemään summary_valid/issues |

## Testaus

```bash
# Testataan tyhjällä summarylla
python3 check_existing.py "https://www.youtube.com/watch?v=Udc19q1o6Mg" "/Users/vre/Sync/Obsidian/Joplinpoplin"

# Odotettu tulos:
{
  "video_id": "Udc19q1o6Mg",
  "exists": true,
  "summary_valid": false,
  "summary_issues": ["summary_too_short", "missing_tldr"],
  ...
}
```
