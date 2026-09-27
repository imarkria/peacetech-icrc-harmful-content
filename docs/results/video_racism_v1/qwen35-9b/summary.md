# Test vidéo par segments — sujet « racisme » (HateMM) · Qwen3.5-9B

2026-09-26 · branche `gmikou/video-racism-test` · **test isolé** : il vérifie la *méthode vidéo* sur un sujet pour lequel il existe des données ouvertes. Le cœur violences sexuelles (core.md, prompts v1 / v3 figés) n'est ni chargé ni modifié.

## En bref

- **Détection au niveau vidéo : ça marche.**
  - Variante B (captures + transcription + OCR) : **F1 0,968** (15 TP, 1 FP, 0 FN, 14 TN), AUROC du score max = 1,0.
  - Variante C (transcription + OCR seulement) : F1 0,937 (2 FP).
  - **Les captures corrigent un FP sur deux** : les deux FP de C disparaissent en B, mais B en ajoute un autre (non_hate_video_179, voir §5).
- **Localisation : le test n'est pas concluant, faute de données adaptées.** Le passage le plus haut chevauche le `hate_snippet` de HateMM dans 14 cas sur 15 (B) en top-1 et 15 sur 15 en top-3. Mais les passages HateMM couvrent en moyenne **79 %** de la vidéo : un segment tiré au hasard tomberait dedans **86 %** du temps. Une seule vidéo a un passage court (13 % de sa durée). Elle est bien localisée en top-1 (hasard : 38 %), mais un seul cas ne prouve rien.
- **La timeline par segment est plus fine que l'annotation HateMM.** Dans les longues chansons, seuls certains segments sont jugés racistes : par exemple 7 segments sur 15 pour hate_video_307, dont le passage HateMM couvre 8-213 s. C'est utile pour le relecteur, mais non vérifiable avec cette référence.
- **Couche déclencheuse (B, segments racistes) :** 89 parole · 24 texte à l'écran · 1 visuel. 5 vidéos positives sont détectées via le texte à l'écran, dont 2 sans aucune parole (pochette d'album, tableau de hiérarchie raciale).
- **Coût :** 45 min de vidéo (30 vidéos, 191 segments, 6.4 par vidéo) traitées en 9.6 min pour B, soit **≈ 4.7 fois plus vite que le temps réel**. 0 JSON invalide, 0 timeout.
- **Point dur de sécurité :** le filtre d'images explicites (CLIP ≥ 0,9 OU AdamCodd ≥ 0,7 OU Falconsai ≥ 0,3, appliqué à chaque capture) a mis **54 vidéos candidates sur 120 en quarantaine (45 %)**. Il fallait donc un vivier de 60 par classe pour obtenir 15 + 15. C'est surtout CLIP qui déclenche : 117 des 121 déclenchements sur les 50 premières vidéos.

## 1. Matrice de confusion (niveau vidéo, 15 racistes / 15 non racistes)

| variante | TP | FP | FN | TN | précision | rappel | F1 | spécificité | AUROC (max P(racist)) |
|---|---|---|---|---|---|---|---|---|---|
| B | 15 | 1 | 0 | 14 | 0,938 | 1,000 | 0,968 | 0,933 | 1,000 |
| C | 15 | 2 | 0 | 13 | 0,882 | 1,000 | 0,937 | 0,867 | 1,000 |

Fichiers : `B/confusion.csv|png`, `C/confusion.csv|png`. AUROC 1,0 : même le FP de B (0,976) reste sous le positif le plus bas (0,991). Le problème vient de la décision (seuil implicite du booléen), pas du classement.

## 2. Localisation (vrais positifs, segment le plus haut vs `hate_snippet` HateMM)

| variante | top-1 | top-3 | décalage moyen top-1 | hasard top-1 (segment aléatoire) | vidéos à passage court (< 50 % de la durée) |
|---|---|---|---|---|---|
| B | 14/15 | 15/15 | 0.2 s | 0.86 | 1 (top-1 1/1, hasard 0.38) |
| C | 15/15 | 15/15 | 0.0 s | 0.86 | 1 (top-1 1/1, hasard 0.38) |

**Lecture :** la méthode retrouve bien un passage raciste, mais on ne peut pas dire qu'elle localise *mieux que le hasard* : la référence HateMM est trop grossière sur cet échantillon (des chansons racistes de bout en bout). Pour mesurer vraiment la localisation, il faut des vidéos longues dont seul un court passage est problématique, avec un horodatage précis.

Timelines des 15 vidéos positives (segments, P(racist), catégorie, couche, passage signalé ◀ et `[snippet]` HateMM) : `timelines.txt`.

## 3. Couche déclencheuse

| variante | parole | texte à l'écran | visuel |
|---|---|---|---|
| B | 89 | 24 | 1 |
| C | 101 | 13 | 0 |

La parole domine : l'échantillon est surtout fait de chansons et de monologues. Le texte à l'écran porte seul 2 vidéos sans parole (hate_video_10 et hate_video_297), détectées par B **et** C grâce à l'OCR. Le visuel seul n'a déclenché qu'un segment.

## 4. Coût (30 vidéos, 2700 s de vidéo, V100)

| étape | temps total | par vidéo |
|---|---|---|
| découpage (PySceneDetect) | 47 s | 1.6 s |
| captures + filtre de sécurité | 40 s | 1.4 s |
| Whisper large-v3-turbo (GPU, fp16) | 52 s | 1.7 s |
| OCR (RapidOCR, CPU) | 144 s | 4.8 s |
| juge B (captures + texte, 8 en parallèle) | 291 s | 9.7 s |
| juge C (texte seul) | 177 s | 5.9 s |
| **total B** | **9.6 min** | **19.2 s** |

L'OCR sur CPU est l'étape la plus lente de la préparation. Environ 6,4 segments par vidéo (fenêtres de 15 s en l'absence de changement de scène, ce qui est fréquent pour les chansons sur image fixe).

## 5. Cinq erreurs expliquées

| # | vidéo | type | ce qui se passe (neutre) | cause probable |
|---|---|---|---|---|
| 1 | non_hate_video_179 | FP (B) | discours conspirationniste antisémite | **Frontière de définition** : le modèle classe l'antisémitisme en RAC-5 (« complot racial »), alors que racism.md le range en `other_hate`. Le discours parle lui-même de « haine ethnique », ce qui brouille la frontière. HateMM le label « Non Hate ». |
| 2 | non_hate_video_431 | FP (C seulement) | scène de rue avec des cris, transcription courte et confuse | **Hallucination sans image** : le modèle affirme qu'il y a une insulte raciale qui n'est pas dans la transcription. Avec les captures (B), il juge correctement. |
| 3 | non_hate_video_541 | FP (C seulement) | discours politique mentionnant un terme yiddish (« Shabbat goy ») | **Terme culturel mal compris**, lu comme une déshumanisation (RAC-2). Avec les captures (B : une conférence), il juge correctement. |
| 4 | hate_video_216 | localisation (B, top-1) | chanson raciste ; segment signalé 195-210 s, passage HateMM jusqu'à 192 s | Le segment signalé est **3 s après** le passage annoté, dans la même chanson : la limite du passage HateMM est grossière (top-3 correct). |
| 5 | hate_video_307 et autres | segments hors passage / dans le passage | 43 % des segments hors `hate_snippet` sont jugés racistes (B), et à l'inverse des segments dans le passage ne le sont pas | **Granularité différente** : HateMM annote une plage large (8-213 s), le juge décide segment par segment (couplets vs refrain, silences). Ce ne sont pas forcément des erreurs, mais on ne peut pas trancher avec cette référence. |

## 6. Référence et sélection

- HateMM (Zenodo 7799469, CC BY 4.0) : le zip et le CSV sont vérifiés (2,27 Go et 4,08 Go, `testzip` OK, 431 + 652 vidéos). Seed 42, 4 minutes maximum.
- Positifs : label Hate, cible raciale, `hate_snippet` présent. Négatifs : label Non Hate.
- **Viviers de 60 par classe** pour obtenir 15 + 15 : 54 vidéos en quarantaine (filtre d'images explicites, jamais regardées) ; 10 exclues pour mineur possible (captures ou texte) ; 22 exclues comme ambiguës, inaudibles, doublons, en désaccord avec le label ou relevant d'une autre haine.
- **Référence écrite avant tout appel au juge** : label HateMM + ma confirmation sur les captures et la transcription, selon RAC-DEF. Toutes les décisions sont dans `data/videos/racism_v1/reference_notes.jsonl` (hors git).
- Positifs retenus : 3 RAC-1, 3 RAC-2, 1 RAC-3, 7 RAC-4, 1 RAC-5. Négatifs : 13 neutres, 1 reportage (RAC-EX-1), 1 piège `other_hate` (antisémitisme).

## 7. Le mécanisme de « sujets » séparés

Le prompt est assemblé par `harmwatch/video_segments.py` : consignes du juge de segment + `policy/modalities.md` (lu tel quel) + `policy/topics/racism.md` + `policy/topics/racism_examples.jsonl`. **Il ne charge jamais core.md, children.md ni un profil de région.** Pour ajouter un autre sujet (par exemple une autre forme de haine, ou la violence sexuelle en vidéo), il suffit d'un nouveau `policy/topics/<sujet>.md` et de ses exemples, sans toucher au cœur. Le prompt racisme a été figé **avant** de regarder la moindre vidéo : `4396e156…`, et le script refuse de tourner s'il change.

## 8. Limites

- **30 vidéos seulement** : chaque erreur pèse environ 7 points de rappel ou de spécificité.
- **Racisme ≠ violences sexuelles.** Ce test valide la *méthode vidéo* (segments, captures, transcription, OCR, jugement par segment, agrégation), pas la détection des violences sexuelles en vidéo.
- **Localisation non démontrée** : la référence HateMM est trop grossière sur cet échantillon (§2).
- **Échantillon peu varié** : surtout des chansons et monologues ouvertement racistes, donc « faciles ». Peu de cas visuels ou implicites.
- **Référence = HateMM + confirmation par Claude** (une seule annotatrice, pas d'accord inter-annotateurs), sur des captures et une transcription automatique qui peut contenir des erreurs.
- **Quarantaine à 45 %** : le filtre d'images explicites choisi sur 10 images de mèmes est beaucoup trop sensible sur des vidéos, surtout CLIP. Les vidéos écartées ne sont pas aléatoires, ce qui introduit un biais possible. Il faudra régler ce filtre pour la vidéo (seuil par capture, nombre minimum de captures) avant un usage réel.
- **Mineurs** : exclus à la revue (10 cas), mais sans outil automatique fiable (voir TODO_SECURITE.md).
- **Contamination possible** : HateMM est public depuis 2023.
- **Un seul modèle**, Qwen3.5-9B, et un seul prompt figé.

## Contrôles « aucune interférence avec l'existant »

Voir le rapport de commit : `git diff --stat gmikou/local-pipeline` (seulement des fichiers nouveaux + une ligne dans policy/README.md), empreintes v1 `ecaefeee…` et v3 `9160fe72…` inchangées, tous les tests existants passent, check_policy_ids OK.
