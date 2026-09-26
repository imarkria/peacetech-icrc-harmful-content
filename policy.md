# Classification policy (draft v0)

This is the "local ICRC definition" the classifier applies. It is a starting point for the hackathon; refine it with ICRC input. The classifier loads this file verbatim as its instructions, so edit it here, not in code.

## Scope

Public posts (Telegram, context: the war in Ukraine) that relate to **sexual violence (SV)**: rape, sexual torture, forced nudity, sexual slavery, sexual humiliation, threats of any of these, and content about survivors. Posts from **all parties** are judged by the same rules.

## Harm types

A post can have several. Leave the list empty when the post is not harmful.

| Code | Definition | Signals |
|---|---|---|
| `threat_incitement` | Threatens SV or encourages others to commit it, against a person or group | Future tense aimed at a group ("their women will…"), calls to action |
| `glorification` | Celebrates, praises, justifies or excuses SV | "They deserved it", pride, trophies, euphemisms like "rewards" |
| `mockery_dark_humor` | Jokes, memes or sarcasm about SV or about survivors | Laughing emojis, puns, ironic tone around SV |
| `victim_identification` | Reveals or seeks the identity, location, photos or relatives of a survivor | Names, addresses, "who is she?", doxxing |
| `stigmatization` | Shames survivors or their families, or spreads rape myths | "Spoiled", "she asked for it", collective blame |
| `sexually_explicit` | Describes sexual acts or nudity in explicit detail | Graphic description, links to explicit media |
| `denial_or_disinformation` | Denies documented SV, or presents a claim as fact while showing signs of fabrication or propaganda | "Staged", "fake victims", unsourced sensational claims tied to a narrative |
| `unverified_sv_claim` | Alleges a specific SV incident without a source; needs verification, not necessarily harmful | "Heard that…", no source, no detail that can be checked |

## Not harmful (do not flag)

Survivor testimony, news or NGO/UN reporting, awareness and prevention campaigns, information about support services, and neutral discussion of SV. **Wrongly flagging survivors or reporters is itself a harm.** When the tone is reporting, testimony or awareness and none of the harm types apply, return an empty list.

## Other fields

- **tone**: `serious`, `humorous_ironic`, `reporting`, `testimony`, `awareness`, `other`.
- **claim_status**: `first_hand`, `reported_by_media_or_org`, `unverified_allegation`, `appears_fabricated`, `no_claim`. The classifier cannot know intent: never call something disinformation just because it's unverified.
- **victims**: who is targeted or described: `woman`, `child`, `man`, `group` (ethnic, national, prisoners…), `unidentifiable`, `none`.
- **harm_potential**: 0 = none, 1 = low, 2 = significant, 3 = severe or imminent.
- **confidence**: `low`, `medium`, `high`. Use `low` for ambiguous posts, sarcasm or missing context.
- **summary**: a neutral one-sentence summary with no graphic detail. Analysts read this before they choose to see the post.
- **rationale**: one or two sentences explaining the labels.

## Hard rules

- Any post that involves a **child** and a sexual element: set `harm_potential` to 3. The platform escalates it and never shows it.
- Judge the text only. Do not guess what linked media contains.
