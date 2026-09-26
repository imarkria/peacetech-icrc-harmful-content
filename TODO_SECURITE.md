# TODO sécurité (à corriger après le classement des modèles)

Relevé le 2026-09-26 pendant la construction du benchmark `sv_images_v1` (revue humaine de 265 candidats).
Ces trous n'ont pas eu d'effet sur le benchmark : tous les cas ont été écartés à la main. Ils touchent la chaîne automatique.

## 1. Indicateurs d'âge CH-2 (`harmwatch/lexicon.py`, `policy/children.md`)

Cas ratés par `age_indicators` :

- [ ] âge sans unité : « I'm only 12 », « she's 15 », « мне 13 » (la regex exige years / лет / років) ;
- [ ] âge de nourrisson : « one-month-old », « 38-day-old », « 6 month old », « newborn », « infant », « baby » ;
- [ ] âges en toutes lettres : « twelve », « fifteen-year-old », « двенадцать лет », « п'ятнадцять років » ;
- [ ] mots de parenté désignant un enfant : « daughter », « son » + contexte d'âge (à discuter : trop large seuls) ;
- [ ] **visuel** : dessins, personnages de dessin animé ou de jeu d'apparence enfantine, bébés en photo. Le lexique ne peut pas les voir. Il faut soit une consigne explicite au juge image, soit un classifieur d'âge apparent (jamais de reconnaissance de personne, B1-3). Cas de référence : `b6da7941` (BD russe enfant + blague sexuelle ; Qwen3.5-9B n'a pas levé possible_minor et l'a envoyée en standard_review).
- [ ] Tests (texte neutre uniquement, CH-5) pour chaque forme ci-dessus, positifs et négatifs (« 12 items », « top 15 », « 1990s »).

## 2. Filtre NSFW (`scripts/eval_images.py`, `scripts/build_sv_benchmark.py`)

`Falconsai/nsfw_image_detection` à 0,3 a laissé passer 10 images explicites (nudité partielle, actes simulés, légende pornographique, capture de site pornographique). Toutes ont été écartées à la revue : candidats c044, c066, c085, c094, c102, c133, c144, c147, c197, c211 (hash dans `data/benchmarks/sv_images_v1_candidates.jsonl`).

- [ ] mesurer le score Falconsai de ces 10 cas et le seuil qui les aurait attrapés, avec le taux de faux positifs sur les 161 images gardées ;
- [ ] tester un 2e classifieur open source (p. ex. un détecteur de nudité par régions, ou un classifieur CLIP zero-shot « explicit / suggestive / safe ») et la combinaison OU des deux ;
- [ ] le texte incrusté compte aussi : une légende pornographique sur une image anodine (c144) doit être mise en quarantaine → ajouter un filtre texte ;
- [ ] tests : les 10 hash doivent être bloqués ; un échantillon d'images gardées ne doit pas l'être (sans jamais stocker ni afficher les images dans les tests : scores précalculés).

## 3. Autres

- [ ] Juge image : `possible_minor` sur-déclenché (14/240 au premier test, sur des enfants sans élément sexuel ou sur des adultes) → consigne « mineur ET élément sexuel » + exemple few-shot (CH-1b).
