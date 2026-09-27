# Policy layers

The classifier's instructions are assembled from these files by `harmwatch/policy_loader.py`. The code is the same for every country; only the region profile changes.

```
core.md                      definitions, flag rule, priority, barriers B1-B6        (highest precedence)
children.md                  minors: hard stop B1-1, TYPES of age indicators CH-2 (no word lists)
modalities.md                how each format is read (text, image, meme, video, audio)
platforms/telegram.md        Telegram layers TG-L1..L8, reach, evasion
regions/<code>.yaml          region profile: languages, age terms, groups, slurs, SV terms, actors, places, narratives, priority rules
regions/<code>_examples.jsonl  annotated few-shot examples for that region               (lowest precedence)
regions/<code>_filter.yaml    search patterns to extract candidates from a corpus (never evidence for a label)
```

**Precedence:** core > platform > region. A lower layer can only *add* meaning (terms, actors, places) or *raise* priority. It never removes, narrows or overrides a higher layer (B3). The children rules and the barriers can't be relaxed by any layer.

**Approval:** only region entries with `status: approved` are loaded, and the loader refuses to run when a profile has none. Entries are written as `proposed` (by people or by the model, B5) and approved by a human:

```bash
python scripts/approve_region.py ru_ua --list
python scripts/approve_region.py ru_ua --by <name>                 # one by one
python scripts/approve_region.py ru_ua --by <name> --approve-all   # bulk, with confirmation
```

Every entry has a `review_by` date.

**The core is universal** (core v1.3): `core.md`, `children.md`, `modalities.md` and the general judge instructions contain no country, language, local term, place or actor (enforced by `tests/test_core_universal.py`). Everything local lives in `regions/<code>.*`.

**Age words** (CH-2) are in the `age_terms` block of each region profile (words, units, ages in letters, stated-age phrases, school grades, institutions, and what makes a number NOT an age). `harmwatch/lexicon.py` merges the generic profile (`global.yaml`, English) with the selected region; age terms can only add indicators, never remove one.

## Selecting a region

```bash
REGION=ru_ua python -m harmwatch.seed            # or --region ru_ua: harmwatch.analyze, social, screen, and the scripts
```

## Adding a country

1. Copy `regions/ru_ua.yaml` to `regions/<code>.yaml` and replace the header (languages, time window, heightened-risk groups, owner), the `age_terms` for each local language, and the entries. Keep the entry format; set every entry to `status: proposed`.
2. Copy `regions/ru_ua_examples.jsonl` to `regions/<code>_examples.jsonl` and write synthetic, non-graphic examples in the local languages. Test cases involving minors stay abstract placeholders (`<SV term> + <age indicator>`), never realistic text.
3. Optional, for corpus extraction: copy `regions/ru_ua_filter.yaml` to `regions/<code>_filter.yaml` and write patterns for the local languages (`scripts/extract_sv.py`).
4. Approve the entries with `scripts/approve_region.py <code>`.

Nothing else changes: no code, no prompt.

## Profile status

| Region | Version | Status |
|---|---|---|
| `ru_ua` | 0.1 | 65/65 entries approved by gmikou for the hackathon (2026-09-26). **To be validated by the ICRC / a local partner** before any operational use. |

Separate topic layers (e.g. racism, used to test the video pipeline) live in `policy/topics/`: they never load or change the sexual-violence core.
