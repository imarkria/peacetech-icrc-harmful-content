# qwen35-4b — benchmark « caractère sexuel » sv_images_v1

Backend llama.cpp (`qwen3.5-4b`) · V100 32 Go · 8 requêtes parallèles · température 0 · prompt figé `sv_prompt_v1` (ecaefeee7cb1…) · profil global-0.1/core-1.2+no-approved-entries.

## Résultats principaux

| mesure | image + texte | texte seul |
|---|---|---|
| F1 sexual | 0.912 | 0.900 |
| précision | 0.877 | 0.841 |
| rappel | 0.950 | 0.967 |
| spécificité | 0.867 | 0.817 |
| TP / FP / FN / TN | 57 / 8 / 3 / 52 | 58 / 11 / 2 / 49 |
| rappel positifs sans mot-clé | 8/10 | 9/10 |
| AUROC P(sexual) logprobs | 0.974 | 0.969 |
| ECE / Brier P(sexual) | 0.055 / 0.069 | 0.081 / 0.081 |
| AUROC score écrit | 0.958 | 0.969 |
| valeurs distinctes du score écrit | 8 | 9 |
| AUROC haine (logprobs) | 0.790 | 0.744 |
| AUROC misogynie (logprobs) | 0.908 | 0.888 |
| F1 haine (décision) | 0.710 | 0.714 |
| F1 misogynie (décision) | 0.736 | 0.807 |
| catégorie ou SV-REL correcte (TP) | 44.4 % | 31.5 % |
| JSON invalide / timeouts / refus | 0 / 0 / 0 | 0 / 0 / 0 |
| possible_minor levé (à tort) | 3 | 4 |
| débit (images/min) | 46.0 | 54.2 |
| VRAM pic (Mo) | 9164 | 9164 |
| temps total (s) | 156.7 | 132.8 |

Fichiers : `image_text/` et `text_only/` → confusion.csv/png, confusion_hate / confusion_misogyny, roc.png, calibration.png, metrics.json, predictions.jsonl.

## Pourcentages par classe de référence (image + texte, score ≥ 50 · moyenne)

| dimension | positifs | négatifs | pièges | neutres |
|---|---|---|---|---|
| sexual_violence | 40.4 % · 41.1 | 0.0 % · 0.0 | 0.0 % · 0.0 | 0.0 % · 0.0 |
| sexual_harassment | 71.9 % · 67.7 | 3.3 % · 4.1 | 6.7 % · 8.2 | 0.0 % · 0.0 |
| hate | 28.1 % · 29.7 | 23.3 % · 21.6 | 33.3 % · 31.3 | 13.3 % · 11.8 |
| misogyny | 63.2 % · 57.4 | 10.0 % · 9.8 | 20.0 % · 19.5 | 0.0 % · 0.0 |
| other_violence | 5.3 % · 10.2 | 0.0 % · 2.5 | 0.0 % · 3.0 | 0.0 % · 2.0 |
| **sexual (décision)** | 95.0 % | 13.3 % | 26.7 % | 0.0 % |

Rappel par catégorie (image + texte) : rape_joke_glorification 11/11, threat_incitement 7/8, denial_minimization 7/7, victim_stigmatisation 5/5, collective_accusation 7/7, sexualised_insult 9/10, degrading_sexualisation 9/10, humiliating_objectification 2/2

**Apport de l'image** : corrige 5 cas (sv1-c107, sv1-c136, sv1-c159, sv1-c189, sv1-c225), en dégrade 3 (sv1-c127, sv1-c174, sv1-c187).

## Faux positifs (image + texte) : 8

| item | catégorie réf. | référence (neutre) | P(sexual) | raison du modèle | cause probable |
|---|---|---|---|---|---|
| `sv1-c187` | sexist_non_sexual | dumb-blonde stereotype | 0.63 | Sexualised insult (SH-1) and hate speech (HI-TYPE-04) targeting women based on gender and ethnicity. | Stéréotype sexiste NON sexuel lu comme SH-2 : le modèle applique SH-DEF à tout mépris envers les femmes, malgré l'exclusion explicite du sexisme non sexuel ; photo d'une femme en décolleté → l'image entraîne le label |
| `sv1-c194` | sexist_non_sexual | wife as beer carrier | 0.65 | Meme implies a woman is a wife solely to carry heavy beer, degrading her role. | Stéréotype sexiste NON sexuel lu comme SH-2 : le modèle applique SH-DEF à tout mépris envers les femmes, malgré l'exclusion explicite du sexisme non sexuel ; raison hallucinée (« sexual objects ») |
| `sv1-c201` | sexist_non_sexual | mocks a pageant winner as hypocritical | 0.65 | Meme implies a woman's participation in a beauty pageant is a result of sexual objectification. | Stéréotype sexiste NON sexuel lu comme SH-2 : le modèle applique SH-DEF à tout mépris envers les femmes, malgré l'exclusion explicite du sexisme non sexuel ; le mot « objectification » du texte déclenche SH-2 |
| `sv1-c202` | sexist_non_sexual | celebrates hitting a real woman | 1.00 | SH-1 sexualised insult and HI-TYPE-04 hate speech targeting women. | Insulte genrée (« bitch ») + violence lues comme SH-1 |
| `sv1-c206` | sexist_non_sexual | feminists as violent | 0.58 | Meme mocks a sexist claim about defending against feminists; implies women are aggressive, degrading sexualisation (SH-2). | Stéréotype sexiste NON sexuel lu comme SH-2 : le modèle applique SH-DEF à tout mépris envers les femmes, malgré l'exclusion explicite du sexisme non sexuel ; violence physique lue comme sexualisation |
| `sv1-c208` | sexist_non_sexual | women's olympics as cooking | 0.78 | Implies women compete in cooking rather than sports, demeaning their athletic ability (SH-2). | Stéréotype sexiste NON sexuel lu comme SH-2 : le modèle applique SH-DEF à tout mépris envers les femmes, malgré l'exclusion explicite du sexisme non sexuel ; raison hallucinée (« for male entertainment ») |
| `sv1-c212` | sexist_non_sexual | hairstyle stereotype about women | 1.00 | Implies women with short hair are sexually available to managers (SH-2) and mocks women's appearance (misogyny). | Stéréotype sexiste NON sexuel lu comme SH-2 : le modèle applique SH-DEF à tout mépris envers les femmes, malgré l'exclusion explicite du sexisme non sexuel ; raison hallucinée (« sexual availability ») |
| `sv1-c214` | sexist_non_sexual | women-drivers stereotype | 0.88 | Meme implies women are incompetent drivers, demeaning their ability without sexual violence. | Stéréotype sexiste NON sexuel lu comme SH-2 : le modèle applique SH-DEF à tout mépris envers les femmes, malgré l'exclusion explicite du sexisme non sexuel ; la raison dit elle-même « incompetence », pas de dimension sexuelle |

## Faux négatifs (image + texte) : 3

| item | catégorie réf. | référence (neutre) | P(sexual) | raison du modèle | cause probable |
|---|---|---|---|---|---|
| `sv1-c036` | threat_incitement | suggests drugging the woman pictured | 0.04 | Harmless meme referencing a drug; no sexual violence, harassment, or hate. | Menace implicite (droguer la femme de la photo) : le modèle lit « drug » sans la combinaison image + légende → « harmless » |
| `sv1-c127` | degrading_sexualisation | implies women react sexually to a greeting | 0.04 | Meme mocking a sexist phrase; no sexual violence, harassment, or hate present. | Sens porté par l'expression du visage dans l'image ; ironie inversée (« mocking a sexist phrase ») |
| `sv1-c174` | sexualised_insult | bestiality slur against Muslims | 0.18 | Hate speech against a specific individual using dehumanizing slurs; no sexual violence or harassment. | Insulte de bestialité contre un groupe religieux vue comme haine seulement (HI-TYPE-04), pas comme SH-1 : frontière de définition |

## Cas ambigus exclus (57, sans référence : distribution seulement)

- jugés sexuels : 71.9 % ; P(sexual) entre 0,2 et 0,8 : 10 items (déciles 0→1 : [10, 1, 3, 0, 2, 1, 2, 2, 5, 31]) ; possible_minor : 2.
- scores écrits (moyenne · % ≥ 50 · histogramme [0-25, 25-50, 50-75, 75-100]) :
  - sexual_violence : 11.5 · 7.3 % · [49, 2, 1, 3]
  - sexual_harassment : 46.3 · 49.1 % · [26, 2, 2, 25]
  - hate : 23.5 · 21.8 % · [42, 1, 2, 10]
  - misogyny : 45.5 · 50.9 % · [26, 1, 5, 23]
  - other_violence : 7.5 · 1.8 % · [51, 3, 0, 1]

## Limites

- **Cas clairs uniquement.** Les 57 cas ambigus ont été exclus du benchmark : les scores mesurent la capacité à trancher des cas nets. Sur des contenus réels, où l'ambiguïté domine, les performances seront plus basses. Le run « ambigus » montre seulement comment le modèle se comporte sur ces cas, pas s'il a raison.
- **Sélection par mots-clés.** Les candidats positifs ont été tirés par mots-clés (viol, insultes sexuelles, vocabulaire sexuel) dans le texte incrusté. Seuls 10 positifs sur 60 n'ont aucun mot-clé explicite : le benchmark favorise les modèles qui lisent bien le texte. Le rappel « sans mot-clé » (n = 10) est très incertain.
- **Référence annotée par Claude.** Une seule annotatrice (un modèle, Claude), selon policy/, validée par gmikou sur 20 cas. Pas d'accord inter-annotateurs mesuré. Les choix d'annotation (haine / misogynie, insultes de bestialité, exclusion de tout mineur) orientent les résultats.
- **Contamination possible.** MAMI, FHM et MMHS sont publics depuis des années et ont pu être vus à l'entraînement par les modèles testés, avec leurs labels. Cela peut gonfler leurs scores de façon inégale.
- **Petits effectifs.** 60 / 60 : un écart de 2-3 erreurs entre modèles n'est pas significatif (IC 95 % du F1 d'environ ±0,06).
- **Prompt unique.** Un seul prompt figé (sv_prompt_v1), conçu et mis au point sur Qwen3.5-9B. Les autres modèles peuvent être désavantagés par un prompt qui n'a pas été adapté pour eux.
- **Profil global non approuvé.** Le prompt tourne en core seul : les 12 entrées du profil global sont encore `proposed`.

## Note : `possible_minor` à tort (3 en image + texte, 4 en texte seul)

sv1-c004, sv1-c054, sv1-c134 : le modèle lève `possible_minor` sur « girl » ou sur un âge adulte (« 19 »). Or children.md CH-2 dit explicitement que « girl » seul n'est pas un indicateur d'âge. Ces items sont comptés comme prédits sexuels (escalade B1-1), ce qui gonfle légèrement le rappel du 4B.
