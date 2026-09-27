# Rapport final — partie images : détection du caractère sexuel

2026-09-26 · gmikou / Claude · branche `gmikou/local-pipeline`.
Benchmark `sv_images_v1` : 120 images de QCRI/MemeLens (données ouvertes), 60 positifs / 60 négatifs (30 pièges, 30 neutres), confirmées à la main, figé (sha256 `f8477c9e…`).
Juge : Qwen3.5-9B Q8_0 + mmproj F16 via llama.cpp, V100 32 Go, température 0, sortie JSON contrainte ; les règles dures restent appliquées par le code.

## 1. Modèle retenu

**Qwen3.5-9B.** Les 4 modèles testés sont à **égalité statistique** sur la détection (F1 de 0,898 à 0,918, IC 95 % qui se chevauchent, McNemar p ≥ 0,6). Qwen3.5-9B est retenu pour trois raisons :
- la meilleure AUROC en logprobs (0,975 avec le prompt v1), donc le meilleur score continu pour quantifier ;
- un seul `possible_minor` levé à tort ;
- un débit correct (≈ 37 images/min), et il est déjà en place pour le texte.

## 2. Scores : prompt v1 (officiel) et prompt v3 (indicatif)

> **v3 a été ajusté après analyse des erreurs de ce jeu : son score est indicatif ; v1 est le résultat officiel.**
> v3 = core v1.4 : définition SH-DEF, définitions de travail des SV-FORM, exclusions B2 → non sexuel, et 10 exemples généraux, dont un exemple « sexisme non sexuel » écrit après avoir vu les erreurs de v1 sur ces 120 images.

### Matrice de confusion « sexual » — image + texte

| prompt | TP | FP | FN | TN | précision | rappel | F1 | spécificité | AUROC P(sexual) logprobs | ECE |
|---|---|---|---|---|---|---|---|---|---|---|
| **v1 (officiel)** | 57 | 8 | 3 | 52 | 0,877 | 0,950 | 0,912 | 0,867 | 0,975 | 0,082 |
| v3 (indicatif) | 56 | 4 | 4 | 56 | 0,933 | 0,933 | 0,933 | 0,933 | 0,993 | 0,054 |

### Matrice de confusion « sexual » — texte seul (texte incrusté, sans image)

| prompt | TP | FP | FN | TN | précision | rappel | F1 | spécificité | AUROC P(sexual) logprobs | ECE |
|---|---|---|---|---|---|---|---|---|---|---|
| **v1 (officiel)** | 54 | 7 | 6 | 53 | 0,885 | 0,900 | 0,892 | 0,883 | 0,954 | 0,101 |
| v3 (indicatif) | 53 | 8 | 7 | 52 | 0,869 | 0,883 | 0,876 | 0,867 | 0,969 | 0,113 |

Autres mesures (image + texte, v1 → v3) :
- AUROC haine (logprobs) : 0,763 → 0,793 ;
- AUROC misogynie : 0,943 → 0,937 ;
- F1 misogynie (décision) : 0,817 → 0,889 ;
- catégorie fine correcte sur les TP : 37,5 % → 45,5 % ;
- positifs sans mot-clé (n = 10) : 8/10 → 7/10 ;
- JSON valides : 120/120 dans les deux cas ; `possible_minor` à tort : 1 → 1 ;
- débit : 36,6 → 39,8 images/min.

### Scores moyens par dimension (image + texte) : moyenne 0-100 (et % d'images ≥ 50)

| classe | prompt | violence sexuelle | harcèlement sexuel | haine | misogynie | autre violence | jugées sexuelles |
|---|---|---|---|---|---|---|---|
| positifs (60) | v1 | 43 (46 %) | 56 (58 %) | 26 (25 %) | 66 (73 %) | 15 (14 %) | 95 % |
| positifs (60) | v3 | 56 (61 %) | 38 (36 %) | 31 (32 %) | 75 (83 %) | 14 (15 %) | 93 % |
| négatifs (60) | v1 | 0 (0 %) | 12 (13 %) | 20 (20 %) | 14 (15 %) | 10 (10 %) | 13 % |
| négatifs (60) | v3 | 0 (0 %) | 6 (7 %) | 17 (17 %) | 18 (23 %) | 6 (7 %) | 7 % |
| dont pièges (30) | v1 | 0 (0 %) | 23 (27 %) | 30 (30 %) | 28 (30 %) | 15 (17 %) | 27 % |
| dont pièges (30) | v3 | 0 (0 %) | 12 (13 %) | 27 (27 %) | 37 (47 %) | 8 (10 %) | 13 % |
| dont neutres (30) | v1 | 0 (0 %) | 0 (0 %) | 10 (10 %) | 0 (0 %) | 4 (3 %) | 0 % |
| dont neutres (30) | v3 | 0 (0 %) | 0 (0 %) | 6 (7 %) | 0 (0 %) | 3 (3 %) | 0 % |

### Images qui changent de résultat entre v1 et v3 (image + texte)

| item | référence | description (neutre) | v1 | v3 | effet |
|---|---|---|---|---|---|
| `sv1-c127` | sexuel (degrading_sexualisation) | implies women react sexually to a greeting | sexuel | non sexuel | dégradé |
| `sv1-c183` | non sexuel (sexist_non_sexual) | assumes a woman at work is making a sandwich | non sexuel | sexuel | dégradé |
| `sv1-c187` | non sexuel (sexist_non_sexual) | dumb-blonde stereotype | sexuel | non sexuel | **corrigé** |
| `sv1-c194` | non sexuel (sexist_non_sexual) | wife as beer carrier | sexuel | non sexuel | **corrigé** |
| `sv1-c206` | non sexuel (sexist_non_sexual) | feminists as violent | sexuel | non sexuel | **corrigé** |
| `sv1-c208` | non sexuel (sexist_non_sexual) | women's olympics as cooking | sexuel | non sexuel | **corrigé** |
| `sv1-c214` | non sexuel (sexist_non_sexual) | women-drivers stereotype | sexuel | non sexuel | **corrigé** |

Texte seul :

| item | référence | description (neutre) | v1 | v3 | effet |
|---|---|---|---|---|---|
| `sv1-c036` | sexuel (threat_incitement) | suggests drugging the woman pictured | sexuel | non sexuel | dégradé |
| `sv1-c183` | non sexuel (sexist_non_sexual) | assumes a woman at work is making a sandwich | non sexuel | sexuel | dégradé |

### Lecture

- En image + texte, v3 **réduit de moitié les faux positifs** (8 → 4) : 5 pièges « sexisme non sexuel » (bière, blonde, jeux olympiques = cuisine, conductrices, féministes violentes) ne sont plus lus comme du harcèlement sexuel. En contrepartie, il **perd un positif** (sv1-c127, dont le sens tient à l'expression du visage) et **ajoute un nouveau FP** (sv1-c183). F1 : 0,912 → 0,933. AUROC en logprobs : 0,975 → 0,993.
- **Ce gain ne se voit pas en texte seul** (F1 0,892 → 0,876). Le gain de v3 passe par l'image, ou il tient à peu de cas : 7 changements sur 120 en image + texte, 2 en texte seul.
- **Les erreurs résistantes sont les mêmes qu'avec v1 :** discrédit de plaignantes nommées (sv1-c049), double sens (sv1-c136), insulte de bestialité (sv1-c174, cas limite), sexisme lié à l'objectification (sv1-c201, sv1-c212) et violence genrée (sv1-c202).
- Comme v3 a été écrit en connaissant ces erreurs, **son score est optimiste**. Il faudrait un jeu tenu à l'écart pour le confirmer (non construit, par décision).

## 3. Classement des 4 modèles (prompt v1 figé, même jeu, image + texte)

| modèle | F1 [IC 95 %] | F1 texte seul | FP / FN | sans mot-clé | AUROC P(sexual) | AUROC haine / misogynie | `possible_minor` à tort | images/min | VRAM pic |
|---|---|---|---|---|---|---|---|---|---|
| **Qwen3.5-9B** (retenu) | 0,912 [0,855-0,957] | 0,892 | 8 / 3 | 8/10 | 0,975 | 0,763 / 0,943 | 1 | 36,6 | 15,3 Go* |
| Qwen3.5-4B | 0,912 [0,850-0,958] | 0,900 | 8 / 3 | 8/10 | 0,974 | 0,790 / 0,908 | 3 | 46,0 | 9,2 Go |
| Gemma 4 12B | 0,918 [0,860-0,964] | 0,897 | 6 / 4 | 8/10 | 0,952 | 0,83 / 0,936 | 1 | 21,9 | 18,5 Go |
| InternVL3.5-8B | 0,898 [0,833-0,946] | 0,907 | 10 / 3 | 8/10 | 0,948 | 0,769 / 0,950 | 1 | 32,4 | 22,9 Go |

- Aucun écart n'est significatif : 2 à 3 erreurs de différence entre modèles.
- Tous se trompent sur les mêmes cas : le sexisme non sexuel lu comme du harcèlement sexuel est la source principale de FP pour les 4 modèles.
- * La VRAM de Qwen3.5-9B est surestimée : il tournait avec un contexte de 163 840 tokens, contre 98 304 pour les autres.
- Détail : `results/sv_benchmark/leaderboard.md`.

## 4. Sécurité (TODO_SECURITE.md)

- **Filtre d'images explicites retenu :** CLIP ≥ 0,9 OU AdamCodd ≥ 0,7 OU Falconsai ≥ 0,3. Il rattrape 8 des 10 images explicites que Falconsai seul avait ratées. **Mise en garde : seuils choisis sur 10 cas.** Il n'est pas réappliqué au benchmark v1.
- **Limite connue :** pas de filtre texte. Une légende pornographique sur une image anodine n'est pas mise en quarantaine.
- **Apparence enfantine :** le signal est mesuré (insuffisant seul) mais **n'est branché nulle part** pour l'instant. Le juge v3 lève `possible_minor` sur 9 des 18 cas « mineur + élément sexuel », dont la BD ratée par v1, mais aussi à tort sur 5 des 8 enfants sans élément sexuel. La protection principale reste l'exclusion à la revue humaine.
- **Âges dans le texte (CH-2) :** faits, les mots d'âge sont désormais dans les profils de région.

## 5. Limites

- **Cas clairs uniquement.** 57 cas ambigus ont été exclus : les scores mesurent la capacité à trancher des cas nets, et seront plus bas sur des contenus réels.
- **Sélection par mots-clés.** 50 positifs sur 60 contiennent un mot-clé explicite. Le benchmark mesure surtout la lecture du texte incrusté (texte seul ≈ image + texte). Le rappel « sans mot-clé » repose sur 10 images.
- **Référence annotée par Claude.** Une seule annotatrice, un modèle, selon policy/ ; 20 cas validés par gmikou ; pas d'accord inter-annotateurs. Au moins un cas de référence est discutable (sv1-c161).
- **Contamination possible.** MAMI, FHM et MMHS sont publics depuis des années et ont pu être vus à l'entraînement, avec leurs labels.
- **Petits effectifs.** 60 / 60 : IC 95 % du F1 ≈ ±0,05.
- **Prompt v3 ajusté sur ce jeu.** Score indicatif seulement (voir §2).
- **Prompt v1 mis au point sur Qwen3.5-9B.** Il peut désavantager les autres modèles.
- **Profil global non approuvé.** Les prompts tournent en core seul.
- **Les `possible_minor` sont comptés comme « sexuel prédit ».** Le rappel des modèles qui déclenchent à tort en est légèrement gonflé.
- **Sécurité incomplète.** Voir §4 : filtre d'images explicites choisi sur 10 cas, pas de filtre texte, détection des mineurs sous la cible de 100 %.

## Fichiers

- Benchmark : `data/benchmarks/sv_images_v1*` (hors git).
- Résultats v1 : `results/sv_benchmark/<modèle>/` ; v3 : `results/sv_benchmark_v3/qwen35-9b/` (hors git).
- Prompts figés : `docs/prompts/sv_prompt_v1_system.txt`, `sv_prompt_v3_system.txt` (v2 abandonné avant toute évaluation).
- Copie versionnée de ce rapport : `docs/FINAL_IMAGES.md`.
