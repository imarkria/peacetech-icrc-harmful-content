# Classement — détection du caractère sexuel dans des images (sv_images_v1)

2026-09-26 · V100 32 Go · llama.cpp (Q8_0 + mmproj F16 pour tous) · 8 requêtes parallèles · température 0.
- Benchmark figé : 120 images (60 positifs / 30 pièges / 30 neutres), sha256 `f8477c9e…`.
- Prompt figé : `sv_prompt_v1` (core v1.2 + SH-DEF, exemples G03 G05 G06 G09), sha256 `ecaefeee…`. Il n'a été modifié pour aucun modèle.
- Données complètes : `leaderboard.csv`, `significance.json`, `error_consensus.json`, et `<modèle>/summary.md`.

## Tableau

| modèle | F1 image+texte [IC 95 %] | rappel | précision | F1 texte seul | sans mot-clé (img+txt / txt) | FP / FN | AUROC P(sexual) logprobs | ECE | AUROC haine / misogynie | catégorie OK (TP) | JSON valide | `possible_minor` à tort | images/min | VRAM pic |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Qwen3.5-9B** (réf.) | 0,912 [0,86-0,96] | 0,95 | 0,88 | 0,892 | 8/10 · 7/10 | 8 / 3 | **0,975** | 0,082 | 0,76 / 0,94 | 38 % | 120/120 | 1 | 36,6 | 15,3 Go* |
| Qwen3.5-4B | 0,912 [0,85-0,96] | 0,95 | 0,88 | 0,899 | 8/10 · **9/10** | 8 / 3 | 0,974 | **0,055** | 0,79 / 0,91 | 44 % | 120/120 | **3** | **46,0** | **9,2 Go** |
| Gemma 4 12B | **0,918** [0,86-0,96] | 0,93 | **0,90** | 0,897 | 8/10 · 7/10 | **6** / 4 | 0,952 | 0,086 | **0,83** / 0,94 | **55 %** | 120/120 | 1 | 21,9 | 18,5 Go |
| InternVL3.5-8B | 0,898 [0,83-0,95] | 0,95 | 0,85 | **0,907** | 8/10 · 5/10 | 10 / 3 | 0,948 | 0,105 | 0,77 / **0,95** | 27 % | 120/120 | 1 | 32,4 | 22,9 Go |

\* Qwen3.5-9B tournait avec un contexte de 163 840 tokens, les autres avec 98 304. Sa VRAM est donc surestimée par rapport aux autres.

Colonnes secondaires :
- % d'images notées haineuses, positifs / négatifs : Qwen9B 25/20 · Qwen4B 28/23 · Gemma 20/20 · InternVL 17/23. **Aucun modèle ne sépare la haine selon le caractère sexuel.** C'est attendu : la haine est répartie des deux côtés du benchmark.
- % d'images notées misogynes, positifs / négatifs : 73/15 · 63/10 · 48/17 · 75/25.
- Cas ambigus exclus (57), jugés sexuels : 67 % · 72 % · 54 % · 70 %. Items avec P(sexual) entre 0,2 et 0,8 : 3 · 10 · 2 · 1.

## Les résultats sont-ils gonflés ? Ce que montrent les contrôles

1. **Les écarts entre modèles ne sont pas significatifs.** Les F1 vont de 0,898 à 0,918, avec des IC 95 % par bootstrap d'environ ±0,05 qui se chevauchent tous. McNemar contre Qwen3.5-9B donne p ≥ 0,6 pour les trois autres (Gemma : 4 cas meilleurs, 5 moins bons). **Sur ce benchmark, les 4 modèles sont à égalité.**
2. **L'image apporte peu.** Le texte seul fait presque aussi bien (F1 0,89-0,91), et pour InternVL il fait même mieux. L'image corrige 5 cas chez Qwen9B (accusation collective portée par la photo, expression du visage) mais en dégrade 3. Le benchmark mesure donc surtout la lecture du texte incrusté. C'est la conséquence directe de la **sélection par mots-clés**.
3. **Les positifs sans mot-clé ne sont que 10.** Leur rappel (8/10 pour tous en image+texte ; 5/10 à 9/10 en texte seul) ne permet pas de conclure.
4. **Les erreurs sont les mêmes partout.** 5 items sont ratés par les 4 modèles, et 4 autres par 3 modèles sur 4 (`error_consensus.json`) :
   - **Sexisme non sexuel lu comme harcèlement sexuel (SH-2 / SH-3)** : « blonde idiote », cuisine, conductrices, concours de beauté, coiffure. C'est **la source principale de FP pour tous les modèles** (6 à 10 FP, presque tous des pièges sexistes), malgré la phrase explicite de SH-DEF. Les raisons données inventent souvent une connotation sexuelle (« sexual availability », « double entendre »).
   - **Discrédit de plaignantes nommées** (SV-REL-5) non reconnu (3 modèles sur 4).
   - **Insultes de bestialité visant un groupe** vues comme de la haine seulement, jamais comme SH-1 (4 sur 4). C'est ma décision d'annotation qui est ici minoritaire : **à trancher par toi**.
   - Un cas où **ma référence est peut-être trop stricte** : sv1-c161 (« eat me » avec un cochon), que Gemma lit comme un double sens sexuel.
5. **Les scores écrits ne servent pas à quantifier : il faut les logprobs.** Les scores 0-100 n'ont que 5 à 6 valeurs distinctes (0 ou ≥ 80), avec une AUROC de 0,92 à 0,96. P(« true ») tiré des logprobs donne une AUROC de 0,95 à 0,975 et une calibration correcte (ECE de 0,05 à 0,11). Mais sur les cas ambigus, les modèles restent tranchés : Qwen9B, Gemma et InternVL placent moins de 4 items sur 57 dans la zone d'incertitude ; Qwen4B en place 10.
6. **Haine : faible pour tous** (AUROC 0,76-0,83). **Misogynie : correcte** (0,91-0,95). Catégorie fine peu fiable (27 à 55 % des TP).

## Recommandation

**Qualité d'abord : égalité statistique**, donc aucun modèle ne s'impose sur la détection. À qualité égale, on départage sur la quantification (le 2e objectif), puis sur la sécurité et la vitesse :

1. **Qwen3.5-9B : à garder comme modèle principal.**
   - Meilleure AUROC en logprobs (0,975) : c'est le meilleur score continu pour quantifier.
   - Un seul `possible_minor` à tort, débit correct (36,6 images/min, environ 370 en 10 min).
   - Déjà en place, avec le même backend pour le texte (Telegram).
2. **Qwen3.5-4B : alternative rapide et légère.**
   - Même F1, meilleure calibration (ECE 0,055), 46 images/min, 9 Go.
   - **Mais 3 `possible_minor` à tort sur des adultes** (il déclenche sur « girl », contrairement à CH-2). Ce n'est pas bloquant pour la sécurité, mais cela brouille le circuit restreint. À n'utiliser qu'après correction de ce point (TODO_SECURITE).
3. **Gemma 4 12B : second avis possible.**
   - Le moins de FP (6), la meilleure catégorie fine (55 %) et la meilleure AUROC haine (0,83).
   - Mais 2 fois plus lent (21,9 images/min) et le plus de VRAM après InternVL. Il ne peut pas cohabiter avec un autre modèle sur la V100.
4. **InternVL3.5-8B : non recommandé.** Le plus de FP (10), la catégorie fine la moins bonne (27 %) et le plus de VRAM (22,9 Go).

**Avant de conclure plus fermement, il faut régler l'erreur commune à tous les modèles, pas changer de modèle.** Elle vient du prompt et de la définition : sexisme non sexuel lu comme SH. Cela demanderait un `sv_prompt_v2`, par exemple un exemple few-shot « stéréotype de cuisine → sexual false », et **surtout un nouveau jeu de test tenu à l'écart**. Ajuster le prompt sur ces 120 images puis le réévaluer dessus gonflerait les scores.

## Limites

- **Cas clairs uniquement.** Les 57 cas ambigus sont exclus : les scores mesurent la capacité à trancher des cas nets. Sur des contenus réels, où l'ambiguïté domine, les performances seront plus basses. Le run « ambigus » montre le comportement du modèle, pas sa justesse.
- **Sélection par mots-clés.** Les positifs ont été tirés par mots-clés dans le texte incrusté (50 sur 60 en contiennent un) : le benchmark favorise la lecture de texte et sous-évalue ce que la vision apporte. Le rappel « sans mot-clé » repose sur 10 items.
- **Référence annotée par Claude.** Une seule annotatrice (un modèle), selon policy/, validée par gmikou sur 20 cas. Pas d'accord inter-annotateurs mesuré. Au moins un cas de référence est discutable (sv1-c161), et un choix d'annotation (insultes de bestialité = SH-1) est contredit par les 4 modèles.
- **Contamination possible.** MAMI, FHM et MMHS sont publics depuis 2020-2022 et ont pu être vus à l'entraînement, avec leurs labels. L'effet peut varier selon le modèle et gonfler les scores de manière inégale.
- **Petits effectifs.** 60 / 60 : IC 95 % du F1 d'environ ±0,05 ; 2-3 erreurs d'écart ne sont pas significatives.
- **Prompt unique, mis au point sur Qwen3.5-9B.** Les autres modèles peuvent être désavantagés.
- **Profil global non approuvé.** Le prompt tourne en core seul (12 entrées encore `proposed`).
- **Les `possible_minor` sont comptés comme « sexuel prédit ».** L'escalade B1-1 suppose un élément sexuel, mais les scores de ces items sont effacés : cela gonfle légèrement le rappel des modèles qui déclenchent à tort (surtout Qwen3.5-4B).
