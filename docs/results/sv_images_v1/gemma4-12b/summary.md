# gemma4-12b — benchmark « caractère sexuel » sv_images_v1

Backend llama.cpp (`gemma-4-12b`) · V100 32 Go · 8 requêtes parallèles · température 0 · prompt figé `sv_prompt_v1` (ecaefeee7cb1…) · profil global-0.1/core-1.2+no-approved-entries.

## Résultats principaux

| mesure | image + texte | texte seul |
|---|---|---|
| F1 sexual | 0.918 | 0.897 |
| précision | 0.903 | 0.929 |
| rappel | 0.933 | 0.867 |
| spécificité | 0.900 | 0.933 |
| TP / FP / FN / TN | 56 / 6 / 4 / 54 | 52 / 4 / 8 / 56 |
| rappel positifs sans mot-clé | 8/10 | 7/10 |
| AUROC P(sexual) logprobs | 0.952 | 0.962 |
| ECE / Brier P(sexual) | 0.086 / 0.084 | 0.096 / 0.09 |
| AUROC score écrit | 0.961 | 0.959 |
| valeurs distinctes du score écrit | 9 | 10 |
| AUROC haine (logprobs) | 0.830 | 0.785 |
| AUROC misogynie (logprobs) | 0.936 | 0.862 |
| F1 haine (décision) | 0.750 | 0.615 |
| F1 misogynie (décision) | 0.765 | 0.603 |
| catégorie ou SV-REL correcte (TP) | 54.5 % | 51.9 % |
| JSON invalide / timeouts / refus | 0 / 0 / 0 | 0 / 0 / 0 |
| possible_minor levé (à tort) | 1 | 0 |
| débit (images/min) | 21.9 | 25.1 |
| VRAM pic (Mo) | 18506 | 18506 |
| temps total (s) | 328.0 | 287.0 |

Fichiers : `image_text/` et `text_only/` → confusion.csv/png, confusion_hate / confusion_misogyny, roc.png, calibration.png, metrics.json, predictions.jsonl.

## Pourcentages par classe de référence (image + texte, score ≥ 50 · moyenne)

| dimension | positifs | négatifs | pièges | neutres |
|---|---|---|---|---|
| sexual_violence | 49.2 % · 43.1 | 0.0 % · 0.0 | 0.0 % · 0.0 | 0.0 % · 0.0 |
| sexual_harassment | 30.5 % · 35.3 | 5.0 % · 5.7 | 10.0 % · 11.3 | 0.0 % · 0.0 |
| hate | 20.3 % · 25.7 | 20.0 % · 19.2 | 30.0 % · 30.0 | 10.0 % · 8.3 |
| misogyny | 47.5 % · 47.1 | 16.7 % · 14.5 | 33.3 % · 29.0 | 0.0 % · 0.0 |
| other_violence | 13.6 % · 18.0 | 10.0 % · 9.2 | 20.0 % · 15.3 | 0.0 % · 3.0 |
| **sexual (décision)** | 93.3 % | 10.0 % | 20.0 % | 0.0 % |

Rappel par catégorie (image + texte) : victim_stigmatisation 4/5, rape_joke_glorification 10/11, denial_minimization 7/7, threat_incitement 8/8, collective_accusation 7/7, degrading_sexualisation 9/10, sexualised_insult 9/10, humiliating_objectification 2/2

**Apport de l'image** : corrige 6 cas (sv1-c036, sv1-c062, sv1-c106, sv1-c104, sv1-c136, sv1-c202), en dégrade 4 (sv1-c049, sv1-c183, sv1-c201, sv1-c208).

## Faux positifs (image + texte) : 6

| item | catégorie réf. | référence (neutre) | P(sexual) | raison du modèle | cause probable |
|---|---|---|---|---|---|
| `sv1-c161` | hate_non_sexual | religious mockery with a pig | 0.96 | The meme uses a pig image and text to target Muslims with a sexualized, dehumanizing slur (SH-1, HI-TYPE-04). No SV-REL present. | « eat me » lu comme double sens sexuel : lecture défendable, la référence (non sexuel) est peut-être trop stricte → cas à revoir |
| `sv1-c183` | sexist_non_sexual | assumes a woman at work is making a sandwich | 1.00 | The meme uses a double entendre to attribute sexual availability or acts to a woman in a professional setting (SH-2). | Stéréotype sexiste NON sexuel lu comme SH-2 (sexisme ≠ sexualisation non respecté) ; « double entendre » inventé |
| `sv1-c187` | sexist_non_sexual | dumb-blonde stereotype | 1.00 | The meme uses a 'dumb blonde' trope to attribute a lack of intelligence to women, constituting degrading sexualisation (SH-2) and misogyny. | Stéréotype sexiste NON sexuel lu comme SH-2 (sexisme ≠ sexualisation non respecté) ; la raison parle d'intelligence, pas de sexualité |
| `sv1-c201` | sexist_non_sexual | mocks a pageant winner as hypocritical | 0.98 | The meme uses irony to mock a woman's perceived hypocrisy regarding objectification while participating in a beauty pageant (SH-3, misogyny). No SV-REL present. | Le mot « objectification » du texte déclenche SH-3 ; sexual=true mais catégorie « none » : sortie incohérente |
| `sv1-c208` | sexist_non_sexual | women's olympics as cooking | 1.00 | The meme uses a sexualized double entendre to demean female athletes, constituting degrading sexualisation (SH-2) and misogyny without a conflict link or SV-REL. | Stéréotype sexiste NON sexuel lu comme SH-2 (sexisme ≠ sexualisation non respecté) ; « double entendre » inventé |
| `sv1-c212` | sexist_non_sexual | hairstyle stereotype about women | 1.00 | The meme attributes sexual availability or behavior to women based on their appearance (SH-2), constituting degrading sexualisation and misogyny. | Stéréotype sexiste NON sexuel lu comme SH-2 (sexisme ≠ sexualisation non respecté) ; « sexual availability » halluciné |

## Faux négatifs (image + texte) : 4

| item | catégorie réf. | référence (neutre) | P(sexual) | raison du modèle | cause probable |
|---|---|---|---|---|---|
| `sv1-c002` | rape_joke_glorification | word-swap turning an anti-rape slogan into a call to rape women | 0.00 | The meme uses irony to mock a specific statement; it does not endorse sexual violence or harassment. | Ironie inversée : l'inversion d'un slogan anti-viol en appel au viol est lue comme une moquerie de la déclaration |
| `sv1-c049` | victim_stigmatisation | discredits named women who reported sexual assault as political activists | 0.00 | The meme references historical political events and accusations of sexual assault without endorsing, threatening, or stigmatizing victims or groups. | Discréditer des plaignantes nommées non reconnu comme SV-REL-5 |
| `sv1-c127` | degrading_sexualisation | implies women react sexually to a greeting | 0.00 | The content is a common internet meme expressing a social interaction; it contains no sexual violence, harassment, hate speech, or misogyny. | Sens porté par l'expression du visage dans l'image, raté |
| `sv1-c174` | sexualised_insult | bestiality slur against Muslims | 0.00 | The meme contains identity-based hate speech and slurs against a religious figure, but lacks any sexual violence or harassment dimensions. | Insulte de bestialité vue comme haine seule, pas SH-1 (frontière de définition) |

## Cas ambigus exclus (57, sans référence : distribution seulement)

- jugés sexuels : 54.4 % ; P(sexual) entre 0,2 et 0,8 : 2 items (déciles 0→1 : [24, 1, 0, 1, 0, 0, 1, 0, 0, 30]) ; possible_minor : 1.
- scores écrits (moyenne · % ≥ 50 · histogramme [0-25, 25-50, 50-75, 75-100]) :
  - sexual_violence : 10.1 · 8.9 % · [46, 5, 4, 1]
  - sexual_harassment : 26.1 · 25.0 % · [33, 9, 11, 3]
  - hate : 13.0 · 8.9 % · [46, 5, 1, 4]
  - misogyny : 28.0 · 32.1 % · [33, 5, 12, 6]
  - other_violence : 6.0 · 3.6 % · [51, 3, 1, 1]

## Limites

- **Cas clairs uniquement.** Les 57 cas ambigus ont été exclus du benchmark : les scores mesurent la capacité à trancher des cas nets. Sur des contenus réels, où l'ambiguïté domine, les performances seront plus basses. Le run « ambigus » montre seulement comment le modèle se comporte sur ces cas, pas s'il a raison.
- **Sélection par mots-clés.** Les candidats positifs ont été tirés par mots-clés (viol, insultes sexuelles, vocabulaire sexuel) dans le texte incrusté. Seuls 10 positifs sur 60 n'ont aucun mot-clé explicite : le benchmark favorise les modèles qui lisent bien le texte. Le rappel « sans mot-clé » (n = 10) est très incertain.
- **Référence annotée par Claude.** Une seule annotatrice (un modèle, Claude), selon policy/, validée par gmikou sur 20 cas. Pas d'accord inter-annotateurs mesuré. Les choix d'annotation (haine / misogynie, insultes de bestialité, exclusion de tout mineur) orientent les résultats.
- **Contamination possible.** MAMI, FHM et MMHS sont publics depuis des années et ont pu être vus à l'entraînement par les modèles testés, avec leurs labels. Cela peut gonfler leurs scores de façon inégale.
- **Petits effectifs.** 60 / 60 : un écart de 2-3 erreurs entre modèles n'est pas significatif (IC 95 % du F1 d'environ ±0,06).
- **Prompt unique.** Un seul prompt figé (sv_prompt_v1), conçu et mis au point sur Qwen3.5-9B. Les autres modèles peuvent être désavantagés par un prompt qui n'a pas été adapté pour eux.
- **Profil global non approuvé.** Le prompt tourne en core seul : les 12 entrées du profil global sont encore `proposed`.
