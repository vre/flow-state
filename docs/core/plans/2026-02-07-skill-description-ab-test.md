# A/B Test: Skill Description Activation

## Context

Keskustelussa nousi esiin erimielisyys SKILL.md description-formaatista. `docs/writing-skills.md` (rivi 50) ja `CLAUDE.md` (rivi 50) molemmat määrittelevät:

> `"[Use when trigger]. [What it produces]."`

Mutta kumpikaan ei ota kantaa triggerin abstraktiotasoon. Testataan kahdella variantilla:

- **A (operaatio-pohjainen):** `"Use when creating, listing, or cleaning git worktrees for feature development"`
  - Listaa konkreettiset operaatiot — triggeröi kun käyttäjä puhuu worktreestä
  - Huom: rikkoo `validate_structure.py`:n WORKFLOW_VERBS-regexiä (creating, listing, cleaning)
- **B (tilanne-pohjainen):** `"Use when feature work needs branch isolation. Manages git worktrees via CLI."`
  - Kuvaa käyttötarpeen abstraktimmin
  - Noudattaa `writing-skills.md` formattia (trigger + output)

Olemassa olevissa skilleissä on molempia tyylejä:
- youtube-to-markdown: `"Use when user asks YouTube video extraction, get, fetch, transcripts..."` (operaatio-sanalista)
- project-builder: `"Use when user wants to create a new skill, MCP server, or CLI tool project."` (operaatio + konteksti)

## Goal

Mitata kumpi description-tyyli johtaa parempaan skill-aktivoitumiseen eri tyyppisillä käyttäjäpyynnöillä. Tuottaa datapohjainen suositus `docs/writing-skills.md` description-ohjeisiin.

## Design

### Testi-promptit (3 kategoriaa, 4 per kategoria = 12 promptia)

**Suorat (skill-spesifit)** — molemmat pitäisi triggeröidä:
1. "Create a new worktree for the auth feature"
2. "List my worktrees"
3. "Clean up merged worktrees"
4. "Show status of all worktrees"

**Epäsuorat (tilannepohjainen tarve)** — B:n pitäisi triggeröidä paremmin:
5. "I need to work on a feature without affecting main"
6. "How do I isolate my experimental changes?"
7. "Set up a separate workspace for this bugfix"
8. "I want to work on two features in parallel"

**Häiriö (ei pitäisi triggeröidä)** — kumpikaan ei saisi:
9. "Add a login button to the dashboard"
10. "Fix the test that's failing in CI"
11. "What does this function do?"
12. "Refactor the database module"

### Mittaus

Jokaiselle promptille:
- **Aktivoituiko skill?** (kyllä/ei) — `claude -p` outputista
- **Oliko aktivointi oikea?** (TP / FP / FN / TN)

### Testiympäristö

```
/tmp/claude/ab-test/
├── variant-a/
│   ├── .claude-plugin/plugin.json
│   ├── SKILL.md              # description A
│   └── scripts/manage_worktree.py
├── variant-b/
│   ├── .claude-plugin/plugin.json
│   ├── SKILL.md              # description B
│   └── scripts/manage_worktree.py
├── prompts/
│   ├── 01_direct_create.txt ... 12_noise_refactor.txt
├── run_ab_test.sh
└── results.yaml
```

### Ajoprotokolla

```bash
for variant in a b; do
  for prompt in prompts/*.txt; do
    for run in 1 2 3; do
      cd variant-${variant}
      claude -p "$(cat ../${prompt})" --allowedTools 'Bash,Read,Skill' \
        2>&1 | tee ../outputs/variant-${variant}/$(basename ${prompt} .txt)/run-${run}.txt
    done
  done
done
```

- **Malli:** sonnet (nopea, halpa, riittävä aktivoinnin mittaamiseen)
- **Toistokerrat:** 3 per prompti per variantti = 72 ajoa
- **Tulosten parsinta:** grep "worktree-manager\|manage_worktree\|Using.*skill"

### Tulosten formaatti

```yaml
# Seuraa create-pr-review-skill.yaml mallia
name: skill-description-ab-test
type: activation-comparison
hypothesis: "B triggeröi paremmin epäsuorilla pyynnöillä ilman tappiota suorilla"

results:
  - prompt: "Create a new worktree for the auth feature"
    category: direct
    variant_a: {activated: true, correct: true, runs: [true, true, true]}
    variant_b: {activated: true, correct: true, runs: [true, true, true]}
```

### Metriikat

| Kategoria | Odotettu tulos |
|-----------|---------------|
| Suorat (4) | A ja B molemmat ~100% aktivointi |
| Epäsuorat (4) | B > A |
| Häiriö (4) | Molemmat ~0% (false positive) |
| Kokonaispistemäärä | (TP - FP) / total |

## Tasks

### Task 1: Testiympäristö

- Luo hakemistorakenne molemmille varianteille
- Kopioi `manage_worktree.py` (lähde: `/tmp/claude/worktree-mgr/worktree-manager/scripts/manage_worktree.py`)
- Kirjoita SKILL.md + plugin.json molemmille
- Kirjoita 12 promptitiedostoa

### Task 2: Ajoskripti

- `run_ab_test.sh` — iteroi promptit x variantit x toistot
- Parsii aktivoituminen outputeista
- Tuottaa `results.yaml`

### Task 3: Ajo ja analyysi

- Aja testit
- Analysoi tulokset
- Kirjoita observations

### Task 4: Dokumentoi ja päätä

- Tallenna scenario `.worktrees/cli-tool-builder/skill-builder/scenarios/`
- Päivitä `docs/writing-skills.md` jos data tukee muutosta
- TAI perustele miksi ei päivitetä

## Acceptance Criteria

- [x] 72 ajoa suoritettu (2026-02-10, haiku, ~20min)
- [x] results.yaml sisältää: activated, correct, category per ajo
- [x] Aggregaatti per variantti per kategoria
- [x] Johtopäätös: kumpi voitti ja marginaali
- [x] `docs/writing-skills.md` ei päivitetä — perusteltu alla

## Tulokset (2026-02-10)

| Kategoria | A (operaatio) | B (tilanne) | Voittaja |
|-----------|:---:|:---:|:---:|
| Suorat (12 ajoa) | 0% aktivointi | 0% aktivointi | TIE |
| Epäsuorat (12 ajoa) | 42% aktivointi | 50% aktivointi | B marginaalisesti |
| Häiriö (12 ajoa) | 0% FP | 0% FP | TIE |

Täydet tulokset: `skill-builder/scenarios/skill-description-ab-test.yaml`
Raakaoutputit: `/tmp/claude/ab-test/outputs/`

## Johtopäätös

Hypoteesi ei vahvistunut merkittävästi. Molemmat variantit toimivat käytännössä samoin.

**Syy:** Claude ohittaa skillin kokonaan kun osaa hoitaa asian natiivisti (`git worktree list/add`). Suorilla prompteilla kumpikaan description ei triggeröi skilliä — Claude tekee työn itse. Descriptionin vaikutus rajoittuu epäsuoriin pyyntöihin, joissa ero on 1 ajo 12:sta.

**Sekoittava tekijä:** Testirepo sisälsi manage_worktree.py -skriptin, joten Claude näki kontekstista mitä repo tekee. Oikeassa käytössä repo ei ole worktree-peli — description vaikuttaisi enemmän.

**Päätös:** Ei muutosta `docs/writing-skills.md`:iin. Molemmat tyylit hyväksyttäviä. Tilanne-pohjainen (B) on formaatin mukainen mutta data ei vaadi sitä.

## Constraints

- `claude -p` vaatii skillin asennettuna `.claude/skills/` -symlinkkillä
- `.claude-plugin/plugin.json` ei yksinään riitä skillin löytymiseen
- Kaikki lokaalia, ei internet-riippuvuuksia
- n=3 per combo ei ole tilastollisesti vahva — suuntaa-antava
