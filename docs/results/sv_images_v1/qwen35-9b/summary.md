# qwen35-9b — benchmark « caractère sexuel » sv_images_v1

Backend llama.cpp (`qwen3.5-9b`) · V100 32 Go · 8 requêtes parallèles · température 0 · prompt figé `sv_prompt_v1` (ecaefeee7cb1…) · profil global-0.1/core-1.2+no-approved-entries.

## Résultats principaux

| mesure | image + texte | texte seul |
|---|---|---|
| F1 sexual | 0.912 | 0.892 |
| précision | 0.877 | 0.885 |
| rappel | 0.950 | 0.900 |
| spécificité | 0.867 | 0.883 |
| TP / FP / FN / TN | 57 / 8 / 3 / 52 | 54 / 7 / 6 / 53 |
| rappel positifs sans mot-clé | 8/10 | 7/10 |
| AUROC P(sexual) logprobs | 0.975 | 0.954 |
| ECE / Brier P(sexual) | 0.082 / 0.086 | 0.101 / 0.101 |
| AUROC score écrit | 0.949 | 0.923 |
| valeurs distinctes du score écrit | 5 | 5 |
| AUROC haine (logprobs) | 0.763 | 0.723 |
| AUROC misogynie (logprobs) | 0.943 | 0.936 |
| F1 haine (décision) | 0.678 | 0.618 |
| F1 misogynie (décision) | 0.817 | 0.873 |
| catégorie ou SV-REL correcte (TP) | 37.5 % | 37.0 % |
| JSON invalide / timeouts / refus | 0 / 0 / 0 | 0 / 0 / 0 |
| possible_minor levé (à tort) | 1 | 0 |
| débit (images/min) | 36.600 | 45.500 |
| VRAM pic (Mo) | 15328 | 15328 |
| temps total (s) | 196.500 | 158.300 |

Fichiers : `image_text/` et `text_only/` → confusion.csv/png, confusion_hate / confusion_misogyny, roc.png, calibration.png, metrics.json, predictions.jsonl.

## Pourcentages par classe de référence (image + texte, score ≥ 50 · moyenne)

| dimension | positifs | négatifs | pièges | neutres |
|---|---|---|---|---|
| sexual_violence | 45.8 % · 43.1 | 0.0 % · 0.0 | 0.0 % · 0.0 | 0.0 % · 0.0 |
| sexual_harassment | 57.6 % · 55.6 | 13.3 % · 11.5 | 26.7 % · 23.0 | 0.0 % · 0.0 |
| hate | 25.4 % · 26.0 | 20.0 % · 19.8 | 30.0 % · 29.8 | 10.0 % · 9.8 |
| misogyny | 72.9 % · 66.2 | 15.0 % · 14.2 | 30.0 % · 28.2 | 0.0 % · 0.3 |
| other_violence | 13.6 % · 14.9 | 10.0 % · 9.6 | 16.7 % · 14.8 | 3.3 % · 4.3 |
| **sexual (décision)** | 95.0 % | 13.3 % | 26.7 % | 0.0 % |

Rappel par catégorie (image + texte) : denial_minimization 7/7, rape_joke_glorification 11/11, threat_incitement 8/8, victim_stigmatisation 4/5, collective_accusation 7/7, sexualised_insult 8/10, degrading_sexualisation 10/10, humiliating_objectification 2/2

**Apport de l'image** : corrige 5 cas (sv1-c043, sv1-c062, sv1-c127, sv1-c200, sv1-c225), en dégrade 3 (sv1-c187, sv1-c206, sv1-c214).

## Faux positifs (image + texte) : 8

| item | catégorie réf. | référence (neutre) | P(sexual) | raison du modèle | cause probable |
|---|---|---|---|---|---|
| `sv1-c194` | sexist_non_sexual | wife as beer carrier | 0.98 | Implies women are sexual objects used for carrying beer (SH-2), demeaning women (misogyny), no conflict link. | Stéréotype sexiste NON sexuel lu comme SH-2 : le modèle applique SH-DEF à tout mépris envers les femmes, malgré l'exclusion explicite du sexisme non sexuel ; raison hallucinée (« sexual objects ») |
| `sv1-c187` | sexist_non_sexual | dumb-blonde stereotype | 0.97 | Meme uses sexualized insult and stereotype to demean women (SH-2, SH-1), misogynous (HI-TYPE-04), but lacks sexual violence relation (Axis 1). | Stéréotype sexiste NON sexuel lu comme SH-2 : le modèle applique SH-DEF à tout mépris envers les femmes, malgré l'exclusion explicite du sexisme non sexuel ; photo d'une femme en décolleté → l'image entraîne le label |
| `sv1-c202` | sexist_non_sexual | celebrates hitting a real woman | 0.91 | Sexualized insult and degrading sexualisation of a woman using slurs; no conflict link or sexual violence relation present. | Insulte genrée + violence physique confondues avec une insulte sexuelle (SH-1) |
| `sv1-c201` | sexist_non_sexual | mocks a pageant winner as hypocritical | 0.99 | Meme implies a woman is objectified and complicit in misogyny (SH-2, HI-TYPE-04), but lacks sexual violence relation (Axis 1). | Stéréotype sexiste NON sexuel lu comme SH-2 : le modèle applique SH-DEF à tout mépris envers les femmes, malgré l'exclusion explicite du sexisme non sexuel ; le mot « objectification » du texte déclenche SH-2 |
| `sv1-c206` | sexist_non_sexual | feminists as violent | 0.94 | Meme implies women are inherently aggressive and must be physically subdued, constituting degrading sexualisation (SH-2) and misogyny (HI-TYPE-04). | Stéréotype sexiste NON sexuel lu comme SH-2 : le modèle applique SH-DEF à tout mépris envers les femmes, malgré l'exclusion explicite du sexisme non sexuel ; violence physique lue comme sexualisation |
| `sv1-c208` | sexist_non_sexual | women's olympics as cooking | 0.97 | Implies women are sexual objects for male entertainment (SH-2), demeaning them (SH-DEF). | Stéréotype sexiste NON sexuel lu comme SH-2 : le modèle applique SH-DEF à tout mépris envers les femmes, malgré l'exclusion explicite du sexisme non sexuel ; raison hallucinée (« for male entertainment ») |
| `sv1-c212` | sexist_non_sexual | hairstyle stereotype about women | 0.98 | Implies sexual availability based on appearance (SH-2) and uses sexualized insults (SH-1) against women (HI-TYPE-04, HP-04). | Stéréotype sexiste NON sexuel lu comme SH-2 : le modèle applique SH-DEF à tout mépris envers les femmes, malgré l'exclusion explicite du sexisme non sexuel ; raison hallucinée (« sexual availability ») |
| `sv1-c214` | sexist_non_sexual | women-drivers stereotype | 0.95 | SH-2 degrading sexualisation: implies incompetence based on gender; misogynous stereotype. | Stéréotype sexiste NON sexuel lu comme SH-2 : le modèle applique SH-DEF à tout mépris envers les femmes, malgré l'exclusion explicite du sexisme non sexuel ; la raison dit elle-même « incompetence », pas de dimension sexuelle |

## Faux négatifs (image + texte) : 3

| item | catégorie réf. | référence (neutre) | P(sexual) | raison du modèle | cause probable |
|---|---|---|---|---|---|
| `sv1-c049` | victim_stigmatisation | discredits named women who reported sexual assault as political activists | 0.06 | Content discusses sexual assault allegations but does not depict, incite, or glorify sexual violence; no sexual dimension present. | Discréditer des plaignantes nommées n'est pas reconnu comme SV-REL-5 (stigmatisation) : le modèle cherche un acte décrit |
| `sv1-c136` | sexualised_insult | implies an identifiable woman is sexually available to the public | 0.01 | No sexual violence or harassment detected; content is a meme with no conflict link. | Double sens (« entrée publique ») non compris : l'insulte n'existe que dans la combinaison photo + légende |
| `sv1-c174` | sexualised_insult | bestiality slur against Muslims | 0.00 | Hate speech against a religious group (HI-TYPE-04) without sexual violence or harassment elements (Axis 1 absent). | Insulte de bestialité contre un groupe religieux vue comme haine seulement (HI-TYPE-04), pas comme SH-1 : frontière de définition |

## Cas ambigus exclus (57, sans référence : distribution seulement)

- jugés sexuels : 66.7 % ; P(sexual) entre 0,2 et 0,8 : 3 items (déciles 0→1 : [16, 1, 1, 1, 0, 0, 1, 0, 0, 37]) ; possible_minor : 1.
- scores écrits (moyenne · % ≥ 50 · histogramme [0-25, 25-50, 50-75, 75-100]) :
  - sexual_violence : 5.4 · 5.4 % · [53, 0, 1, 2]
  - sexual_harassment : 55.8 · 62.5 % · [21, 0, 0, 35]
  - hate : 16.1 · 14.3 % · [48, 0, 1, 7]
  - misogyny : 58.1 · 67.9 % · [18, 0, 3, 35]
  - other_violence : 9.5 · 10.7 % · [50, 0, 2, 4]

## Limites

- **Cas clairs uniquement.** Les 57 cas ambigus ont été exclus du benchmark : les scores mesurent la capacité à trancher des cas nets. Sur des contenus réels, où l'ambiguïté domine, les performances seront plus basses. Le run « ambigus » montre seulement comment le modèle se comporte sur ces cas, pas s'il a raison.
- **Sélection par mots-clés.** Les candidats positifs ont été tirés par mots-clés (viol, insultes sexuelles, vocabulaire sexuel) dans le texte incrusté. Seuls 10 positifs sur 60 n'ont aucun mot-clé explicite : le benchmark favorise les modèles qui lisent bien le texte. Le rappel « sans mot-clé » (n = 10) est très incertain.
- **Référence annotée par Claude.** Une seule annotatrice (un modèle, Claude), selon policy/, validée par gmikou sur 20 cas. Pas d'accord inter-annotateurs mesuré. Les choix d'annotation (haine / misogynie, insultes de bestialité, exclusion de tout mineur) orientent les résultats.
- **Contamination possible.** MAMI, FHM et MMHS sont publics depuis des années et ont pu être vus à l'entraînement par les modèles testés, avec leurs labels. Cela peut gonfler leurs scores de façon inégale.
- **Petits effectifs.** 60 / 60 : un écart de 2-3 erreurs entre modèles n'est pas significatif (IC 95 % du F1 d'environ ±0,06).
- **Prompt unique.** Un seul prompt figé (sv_prompt_v1), conçu et mis au point sur Qwen3.5-9B. Les autres modèles peuvent être désavantagés par un prompt qui n'a pas été adapté pour eux.
- **Profil global non approuvé.** Le prompt tourne en core seul : les 12 entrées du profil global sont encore `proposed`.
