# TODO sécurité

Relevé le 2026-09-26 pendant la construction du benchmark `sv_images_v1` (revue humaine de 265 candidats), mis à jour le même jour après les mesures.

## 1. Indicateurs d'âge CH-2 (texte) — FAIT (core v1.3, commit 332c43d)

- [x] âge sans unité (« I'm only 12 », « she's 15 », « мне 13 »), avec l'apostrophe typographique ;
- [x] âges de nourrisson (« one-month-old », « 38-day-old », « 6 month old », newborn, infant, baby) ;
- [x] âges en toutes lettres (en, ru, uk), dans les `age_terms` des profils de région ;
- [x] négatifs : « only 15 minutes », « top 12 items », « the 1990s », « I'm 34 », « 12 years ago », « a 5-year plan » ;
- [ ] mots de parenté (« daughter », « son ») : laissés de côté volontairement, trop larges seuls.

## 2. Filtre d'images explicites — MESURÉ, seuils à décider

Mesures sur les 10 images explicites trouvées à la revue (c044, c066, c085, c094, c102, c133, c144, c147, c197, c211), toutes ratées par Falconsai à 0,3, et sur les 255 autres candidats de sv_images_v1 (non explicites à la revue) :

| filtre | seuil | explicites rattrapées | autres bloquées (dont items du benchmark v1) |
|---|---|---|---|
| Falconsai seul | 0,3 → 0,02 | 0 → 1 / 10 | 0 → 7 / 255 |
| AdamCodd ViT | 0,7 / 0,1 | 2 / 6 sur 10 | 5 / 22 sur 255 |
| LukeJacob2023 (porn+hentai+sexy) | 0,5 | 2 / 10 | 20 (9) |
| giacomoarienti (porn+hentai) | 0,5 | 1 / 10 | 0 |
| CLIP ViT-L/14 zero-shot | 0,9 | 8 / 10 | 32 (15) |
| CLIP zero-shot | 0,8 | 9 / 10 | 58 (26) |
| **OR(CLIP ≥ 0,9, AdamCodd ≥ 0,7, Falconsai ≥ 0,3)** (défaut proposé) | | **8 / 10** | **36 (≈ 14 %)** |
| OR(CLIP ≥ 0,8, AdamCodd ≥ 0,7, Falconsai ≥ 0,3) | | 9 / 10 | 61 (≈ 24 %) |

- Code : `harmwatch/safety.py` (cascade OR, seuils configurables), tests dans `tests/test_safety.py` (scores précalculés dans `data/`, jamais d'image dans le dépôt).
- **Limite majeure :** CLIP lit le texte incrusté. 26 des 32 images bloquées à tort au seuil 0,9 sont des positifs confirmés (mèmes qui PARLENT de sexe ou de viol). Un seuil strict affame donc le benchmark en positifs et le biaise vers les mèmes au texte neutre.
- Les seuils ont été choisis sur 10 cas seulement : c'est optimiste. À revérifier sur les nouveaux candidats de sv_images_v2.
- [ ] c094 (0,85) et c144 (légende pornographique sur une image anodine, 0,34) restent ratés au défaut. **Filtre sur le texte** pour les légendes pornographiques : non fait (un filtre par mots-clés bloquerait aussi les positifs SH ; à discuter).
- [ ] **Décision à prendre :** seuil CLIP 0,9 (plus de mèmes gardés) ou 0,8 (plus sûr), ou deux niveaux (« explicite » en quarantaine, « suggestif » montré flouté aux humains).

## 3. Apparence enfantine (images) — MESURÉ, insuffisant

Mesures sur les 25 candidats exclus pour « mineur possible » à la revue, plus b6da7941 (BD : enfant + blague sexuelle), contre les 161 candidats gardés (adultes) :

- **CLIP zero-shot « enfant » vs « adulte »** : au seuil 0,7 → 5/26 repérés (dont b6da7941 à 0,76), 1/161 fausse alerte ; au seuil 0,3 → 12/26, 15/161. Il rate les dessins animés (c118), les illustrations (c151) et les acteurs connus qui étaient mineurs.
- **Juge Qwen3.5-9B avec sv_prompt_v3** (children.md v1.3 mentionne les dessins) :
  - 9 sur 18 cas « mineur + élément sexuel » ont levé `possible_minor`, **dont b6da7941, raté par la v1** ;
  - mais 5 sur 8 cas « enfant sans élément sexuel » l'ont aussi levé, à tort (CH-1b).
- Code : signal `child_visual` dans `harmwatch/safety.py` et règle « apparence enfantine + élément sexuel → possible_minor » (`restricted_reason = "rule_visual"`) dans `sv_scores.finalize_scores`. Elle ne fait que relever, jamais bloquer seule, et n'est pas encore branchée dans les runs d'évaluation.
- [ ] Rappel combiné (juge OU CLIP) encore loin de la cible de 100 % (CH-5). Les cas ratés, ce sont des acteurs mineurs connus ou des personnages de dessins animés, sont impossibles à voir sans identifier la personne (interdit, B1-3). **La protection principale reste l'exclusion à la revue humaine et la règle « quand on doute, restreindre ».**

## 4. Autres

- [ ] Juge image : `possible_minor` sur-déclenché sur des enfants sans élément sexuel (5/8 ci-dessus) et sur « girl » (Qwen3.5-4B). Piste : un exemple few-shot CH-1b (enfant, contenu non sexuel → false), à évaluer sur un jeu tenu à l'écart.
