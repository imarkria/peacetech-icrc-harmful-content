# Test images — juge Qwen3.5-9B (vision) sur QCRI/MemeLens

Run `20260926_1614_qwen35-9b` · 2026-09-26 · Qwen3.5-9B Q8_0 + mmproj F16 via llama.cpp (V100, 8 slots) · température 0 · sortie compacte, règles dures appliquées par le code (`harmwatch/vision.py`).

## En bref

- **Fiabilité technique : bonne.** 240/240 JSON valides, 0 refus, 0 timeout, 0 erreur serveur. Débit : **40,3 images/min** (240 images en 358 s), soit **~400 images en 10 min**. Latence moyenne 11,8 s par image (8 en parallèle), prompt de ~6 600 tokens dont la plus grande partie est en cache.
- **Haine (T1) : faible.** F1 = 0,50 au global. Correct sur FHM (F1 0,63), inutilisable sur MMHS (rappel 0,05, labels très bruités) et sur les mèmes russes (F1 0,49, OCR du dataset illisible).
- **Misogynie (T2) : correcte.** F1 = 0,73 (précision 0,71, rappel 0,75).
- **Lien avec les violences sexuelles (T3) : très conservateur.** Précision 1,0 mais rappel 0,10 face au proxy MAMI. Ce résultat est attendu : MAMI « violence » ≠ violence sexuelle.
- **Décision de flag (T4) : rappel 0,11 face au label « contenu nuisible ».** Là encore c'est attendu, et c'est la définition qui le produit : la haine sans violence sexuelle n'est jamais flaggée (Axe 1 obligatoire). Ce n'est pas une erreur du modèle.
- **Face à ma référence selon policy/ (T5)**, le modèle signale trop de haine : 16 FP pour 15 TP. Il met HI-TYPE-04 sur des mèmes ironiques, des références culturelles et de simples grossièretés.
- **Deux problèmes de sécurité à corriger avant tout usage :**
  1. `possible_minor` est levé 14 fois sur 240, **surtout à tort** : sur des enfants présents sans aucun élément sexuel, et même sur des adultes. Le masquage (blanking) efface alors `hateful`, ce qui crée des FN.
  2. Inversement, **un cas réel est manqué** : une BD associant un enfant et une blague sexuelle (`b6da7941`) est partie en `standard_review` au lieu de `restricted_escalation`.
- **Contamination par les exemples few-shot :** 3 mèmes russes reçoivent un raisonnement « SV présentée comme une 'reward' » copié de l'exemple G02.

## Données et correspondance des labels

Source : `QCRI/MemeLens`, split **test** uniquement, parquet téléchargés sans formulaire (CC BY-NC 4.0). Le juge reçoit seulement l'image (768 px max) et le champ `text` (texte incrusté fourni par le dataset). Il ne voit jamais `label`, `explanation` ni `task_description`.

| sous-ensemble | n (pos/neg) | positif (`label`) | négatif (`label`) | `native_label` | profil |
|---|---|---|---|---|---|
| violence_en__MAMI | 40 (20/20) | `violence` | `not-violence` | vide | global |
| objectification_en__MAMI | 20 (10/10) | `objectification` | `not-objectification` | vide | global |
| shaming_en__MAMI | 20 (10/10) | `shaming` | `not-shaming` | vide | global |
| Hateful_en_FHM | 80 (40/40) | `hateful` | `not-hateful` | vide | global |
| Hateful_en__MMHS | 40 (20/20) | `hateful` | `not-hateful` | vide | global |
| toxic_ru__Toxic_Memes_Detection_Dataset | 40 (20/20) | `toxic` (`токсичный`) | `not-toxic` (`нетоксичный`) | renseigné | ru_ua |

Échantillonnage : seed 42, stratifié par sous-ensemble × label. Chaque liste mélangée est parcourue jusqu'à remplir le quota avec des images propres. Pas de doublon d'image entre sous-ensembles (les trois tâches MAMI partagent des mèmes ; dédoublonnage par hash).

**Quarantaine NSFW :** filtre `Falconsai/nsfw_image_detection` (ViT open source, Apache-2.0), seuil 0,7, appliqué avant le juge. **3 images mises en quarantaine** (2 MAMI objectification, 1 FHM) : hash + raison dans `data/images/memelens/quarantine.jsonl`. Elles n'ont été ni envoyées au juge, ni conservées, ni affichées, et ont été remplacées dans l'échantillon. Le filtre a laissé passer au moins deux images de nudité adulte partielle (score < 0,7), qui ont donc été envoyées au juge. Un seuil plus bas ou un second filtre serait à prévoir pour un usage réel.

**Prompt :** core + children + modalities + plateforme `generic` + profil + 4 exemples.
- Mèmes anglais : profil `global` **en core seul**. Ses 12 entrées sont encore `proposed` et ne sont donc pas chargées ; le loader tourne en `allow_no_approved`.
- Mèmes russes : profil `ru_ua` (65 entrées approuvées).
- Exemples utilisés : G02, G03, G05, G06 pour global ; E08, E12, G02, G05 pour ru_ua.

## Résultats

Les matrices sont dans `confusion_<tâche>_<sous-ensemble>.csv` et `.png`, les chiffres complets dans `metrics.json`. Toutes les tâches portent sur les 240 prédictions valides (aucune erreur à exclure).

{{TABLES}}

**Sensibilité T1 :** les items en `restricted_escalation` ont `hateful` effacé par B1-1, ce qui les compte en FN. Sans eux (n = 150) : P 0,54 · R 0,50 · F1 0,52 (contre 0,50 avec). L'effet est faible sur le global, mais 4 des 14 restrictions tombent sur des mèmes FHM, dont un positif clairement raciste (`d2efa0d0`).

### Lecture par tâche

- **T1 Haine.** Les FP et FN sont en nombre comparable (33 FP / 42 FN). Le modèle met HI-TYPE-04 sur 112 items sur 240. Sur FHM, il repère les attaques explicites mais rate celles qui passent par un code culturel ou par la seule combinaison image-texte. Sur **MMHS**, 19 positifs sur 20 sont manqués. En regardant les FN, les images « hateful » sont des captures météo, des lecteurs de musique ou des scores de match : dans MMHS150K, la haine se trouve le plus souvent dans le **texte du tweet**, absent de MemeLens. C'est le dataset qui ne permet pas de conclure, pas le juge. Sur les **mèmes russes**, le champ `text` est un OCR très dégradé (mélange cyrillique-latin) et le label `toxic` couvre la vulgarité, pas seulement la haine. La tâche n'est pas alignée avec HI-TYPE-04.
- **T2 Misogynie** (`hateful` OU `sv_related`) : c'est la meilleure tâche (F1 0,73). La faiblesse est sur *shaming* (spécificité 0,50) : le modèle traite toute moquerie genrée comme de la haine.
- **T3 Lien avec les violences sexuelles** (proxy prudent) : sur 60 items, 3 sont prédits `sv_related` et les 3 sont corrects (rappel 0,10). MAMI « violence » inclut la violence physique et psychologique, et « objectification » ne relève pas de SV-DEF. Un rappel bas est donc cohérent avec les définitions, pas un défaut.
- **T4 Flag** : 13 TP sur 120 positifs. La règle de flag (Axe 1 ET Axe 2 ET AFF) exclut par construction toute la haine sans violence sexuelle. T4 mesure donc l'écart de périmètre entre « contenu nuisible » et « CRSV », pas une erreur. Les 10 FP comprennent 7 `restricted_escalation` (comptés comme flag) sur des négatifs.
- **T5 Référence selon policy/** : voir plus bas.

### Erreurs et exclusions

| | nombre |
|---|---|
| JSON invalide | 0 |
| refus (raison vide hors restriction) | 0 |
| timeouts | 0 |
| erreurs serveur | 0 |
| `restricted_escalation` (`possible_minor`) | 14 (tous levés par le modèle, 0 par la règle d'âge) |
| quarantaine NSFW (avant le juge) | 3 |
| `triggered_layer` | meme 228 · image 8 · embedded_text 4 |

## T5 — Qwen face à ma référence selon policy/ (étiquettes silver)

J'ai annoté 60 images tirées au hasard dans l'échantillon (seed 4242, distincte de la seed d'échantillonnage) selon `policy/`, en regardant chaque image, **avant d'avoir vu la moindre prédiction** (fichier écrit avant le calcul des scores). Lecture appliquée :
- `hateful` = HI-TYPE-04 au sens de core.md, plus la règle des stéréotypes de modalities.md ;
- `sv_related` = un SV-REL s'applique ;
- `flag` = la règle de flag, en comptant `restricted_escalation` comme un flag.

**22 cas sur 60 sont limites** (colonne « limite »). Ma référence compte 21 `hateful`, 1 `sv_related` et 2 `flag` (dont 1 restriction B1-1).

**Accord de ma référence avec le label du dataset** (toutes tâches confondues) : `hateful` 68 % d'accord (P 0,76, R 0,53). Le label du dataset et la définition HI-TYPE-04 ne mesurent pas la même chose, surtout pour MAMI (objectification ≠ haine) et Toxic RU (vulgarité ≠ haine).

Principaux désaccords entre Qwen et moi :
- **HI-TYPE-04 trop large (16 FP)** : ironie anti-raciste ou anti-nazie comptée comme haine, référence de jeu vidéo lue comme une insulte, simple vulgarité russe, objectification sans mépris identitaire.
- **Haine codée manquée (6 FN)** : allusion à l'esclavage, comparaison d'une femme noire à un singe, mégenrage d'une personne trans, et deux cas effacés par une restriction à tort.
- **Flag (7 FP)** : 5 restrictions `possible_minor` à tort, plus 2 SV-REL inventés : un mème transphobe lu comme SV-REL-4, et une insulte russe du type « ta mère » lue comme SV-REL-4 « reward ».
- **Accord de façade sur le flag de `b6da7941`** : nous le flaggons tous les deux, mais je l'envoie en `restricted_escalation` (enfant + contenu sexuel → B1-1) alors que Qwen l'envoie en `standard_review`. **C'est l'erreur la plus grave du run.**

### Les 60 IDs, pour que tu valides un sous-échantillon

Les fichiers `data/images/memelens/silver_labels.jsonl` (étiquettes + note par item) et `silver_ids.json` sont hors git.

| id | sous-ensemble | hateful | sv_related | flag | limite |
|---|---|---|---|---|---|
{{SILVER}}

## 10 faux positifs et 10 faux négatifs

Descriptions neutres, sans reproduire les images. Pour T1 on compare `hateful` au label du dataset ; pour MAMI, on utilise T2.

**Faux positifs** (le modèle voit de la haine, le dataset non)

| id | sous-ensemble | ce que montre le mème (neutre) | cause probable |
|---|---|---|---|
| `46586e09` | FHM | Jeu de mots rejetant le nazisme, photo d'un rassemblement avec symbole en feu | **Ironie mal comprise** : une idéologie est prise pour une identité protégée (stance `quotes_to_condemn` mais HI-TYPE-04 quand même) |
| `c1329b2f` | FHM | Gorille, légende renvoyant à un monstre de jeu vidéo | **Référence culturelle** (jeu en ligne) lue comme une insulte déshumanisante |
| `efc19461` | FHM | Chanteur sur scène, paroles de chanson détournées sur l'heure qu'il est | **HI-TYPE-04 halluciné** ; la raison du modèle se contredit (« mocking a telecom outage ») |
| `74656d7b` | FHM | Moquerie de la moustache d'un dictateur historique | Moquerie d'un individu, pas d'une identité : **définition appliquée trop largement** |
| `7345a860` | FHM | Aigle mangeant une oie, légende « frontalier détenu » | Jeu de mots sur l'oie du Canada lu comme une attaque nationale : **référence culturelle** |
| `977e984c` | Toxic RU | Blague grossière où une assiette « répond » | **Vulgarité ≠ haine** ; raison absurde (« dehumanize a plate ») |
| `293307ef` | Toxic RU | « Le prof demande des volontaires », photo de soldats de 14-18 | Imagerie guerrière lue comme de la haine : **sur-lecture du contexte conflit** |
| `0f3ab7dd` | MAMI violence | Réplique de film détournée, visée sexiste mais ironique | La raison dit « se moque d'une affirmation sexiste » mais met HI-TYPE-04 : **ironie comprise dans le texte mais pas appliquée au label** |
| `4c728daf` | MAMI shaming | Explosion nucléaire, « gender reveal party » | Se moque des fêtes, pas des femmes : **ironie / cible mal identifiée** |
| `6986098d` | FHM | Peluche, légende « ils ne sont pas tous des violeurs… hein ? » | **Cas réellement ambigu** : le modèle y voit un SV-REL-4 (déni) et le flagge, le dataset le classe non haineux (leurre FHM). Selon policy/, une accusation collective ironique pourrait relever de SV-REL-3 : à arbitrer |

**Faux négatifs** (le dataset voit un contenu nuisible, le modèle non)

| id | sous-ensemble | ce que montre le mème (neutre) | cause probable |
|---|---|---|---|
| `013fb174` | FHM | Mains récoltant du coton, légende évoquant une « machine de 1823 » | **Référence culturelle** (esclavage) non reconnue |
| `10d345ae` | FHM | Singe puis enfant en fauteuil roulant, légende sur les tests de médicaments | **Insulte codée** (« légume » pour personne handicapée) + haine portée par la combinaison image-texte, manquée |
| `66587c82` | FHM | Homme à une marche des fiertés, légende « avec une arme je changerais ce fruit en légume » | **Insulte codée** (« fruit ») + appel à la violence ; la faute de frappe « gone » pour « gun » masque l'intention |
| `d2efa0d0` | FHM | Jeunes Noirs souriants, légende « c'est vraiment un zoo » | **`possible_minor` levé à tort** (enfants visibles, aucun élément sexuel) → masquage → FN |
| `b5c5eff1` | MAMI violence | Carte où quelqu'un dit avoir frappé une femme pour une opinion sportive | **Définition trop stricte** : violence contre une femme sans motif identitaire explicite → pas HI-TYPE-04 ; le modèle cherche un lien au conflit |
| `3a438c72` | MAMI violence | Femme avec un œil au beurre noir, légende « à retenir en faisant un sandwich » | Blague sur les violences conjugales ; le modèle décrit la blessure mais **ne relie pas image et texte** |
| `2b65f378` | MAMI objectification | Innuendo sexuel « charger le lave-vaisselle » | **Lacune de définition** : l'objectification n'a pas d'équivalent dans HI-TYPE-01..06 |
| `75c61715` | MAMI shaming | Légende moqueuse sur une femme à forte poitrine | **Ironie inversée** : le modèle y voit la moquerie d'une plainte pour harcèlement |
| `cf963ae5` | MMHS | Capture d'écran météo | **Label non reproductible** à partir de l'image : la haine était dans le tweet d'origine (MMHS150K) |
| `9230d283` | MMHS | Réplique de série « je ne serai pas jugée » | Idem : **bruit de label MMHS**, rien de haineux dans l'image ni dans le texte |

## Ce qui ressort pour les définitions (propositions, rien n'est appliqué)

1. **`possible_minor`** : préciser dans les instructions image « minor ET élément sexuel ; la simple présence d'enfants ne suffit pas (CH-1b) ». Ajouter un exemple few-shot de mème non sexuel avec des enfants. Et dans le sens inverse, un cas abstrait « enfant + blague sexuelle en dessin → B1-1 ». Le code ne peut pas abaisser le drapeau (B6-3), donc la correction doit passer par le prompt.
2. **HI-TYPE-04 et ironie** : répéter dans les instructions image que stance `mocks` ou `quotes_to_condemn` dirigée CONTRE une idée haineuse ⇒ pas de HI-TYPE-04. Préciser qu'une idéologie (nazisme) ou un personnage public n'est pas une identité protégée.
3. **Objectification et violence contre les femmes** : décider si c'est dans le périmètre haine (nouvel HI-TYPE ou lecture de HI-TYPE-04 étendue au genre). Aujourd'hui une partie de MAMI tombe entre les deux.
4. **Few-shot** : G02 (« reward ») est recopié sur des mèmes russes illisibles. Pour ru_ua, remplacer G02 par un exemple négatif en russe.
5. **Mèmes russes** : faire notre propre OCR sur ces images, le texte du dataset est inutilisable. Pour mesurer la haine, prendre un autre jeu que Toxic RU (qui mesure la vulgarité).
6. **Filtre NSFW** : abaisser le seuil ou combiner deux filtres ; deux images de nudité adulte sont passées.

## Limites

- Petits effectifs (20 à 80 par sous-ensemble) : intervalles de confiance larges, ±10 à 20 points.
- Le profil `global` n'est pas encore approuvé, donc les mèmes anglais ont été jugés en core seul. À relancer après approbation (6 min).
- Les étiquettes silver sont annotées par une seule personne (moi), avec 22 cas limites sur 60 : à valider sur un sous-échantillon.
- Les jeux utilisés portent sur la haine et la misogynie, pas sur la CRSV. Ce test mesure surtout Axe 2 / HI-TYPE-04 et la discipline de l'Axe 1, pas la détection de CRSV en conflit.
