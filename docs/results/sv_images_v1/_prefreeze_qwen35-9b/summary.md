# Qwen3.5-9B — benchmark « caractère sexuel » sv_images_v1

Qwen3.5-9B Q8_0 + mmproj F16 · llama.cpp sur V100 32 Go, 8 slots · température 0 · 2026-09-26.
- Prompt : core + children + modalities + plateforme generic + profil global en core seul (entrées encore `proposed`) + 4 exemples synthétiques (G03, G05, G06, G09).
- Benchmark : 120 images figées (60 positifs / 30 pièges / 30 neutres, sha256 `f8477c9e…`).

## En bref

- **Caractère sexuel : F1 0,90** (P 0,93 · R 0,87 · spécificité 0,93). AUROC du score max(sexual_violence, sexual_harassment) : **0,92**.
- **Axe 1 (violences sexuelles) quasi parfait : 36 sur 38.** Menaces, blagues sur le viol et accusations collectives sont toutes détectées. Les erreurs portent sur le **harcèlement** : 16 sur 22, faiblesse sur les insultes sexualisées (6 sur 10).
- **Les pièges tiennent bien** : 0 % de violence sexuelle prédite sur les 60 négatifs. Les 4 FP sont tous des mèmes **sexistes non sexuels** jugés « degrading_sexualisation ». La confusion « méchant ≠ sexuel » reste donc un risque sur le sexisme, pas sur la haine raciale ou religieuse.
- **Les scores ne sont pas vraiment indépendants.** Quand le modèle dit `sexual=false`, il met souvent tout à 0, y compris la haine ou la misogynie évidentes. D'où le rappel de 0,67 en misogynie.
- **Catégorie fine correcte sur 39 % des TP seulement.** Le modèle range beaucoup de cas en « rape_joke_glorification » ou « humiliating_objectification » : il détecte bien, il classe mal.
- **Technique** : 120/120 JSON valides, 0 refus, 0 timeout. **46,7 images/min**, 154 s au total, VRAM au pic 15,3 Go. 1 `possible_minor` levé à tort (aucun mineur dans le benchmark).

## Matrice principale : `sexual` prédit vs référence

| | prédit sexuel | prédit non sexuel |
|---|---|---|
| **référence sexuelle (60)** | TP 52 | FN 8 |
| **référence non sexuelle (60)** | FP 4 | TN 56 |

Précision 0,929 · rappel 0,867 · F1 0,897 · accuracy 0,900 · spécificité 0,933. Fichiers : `confusion.csv` / `confusion.png`.

L'item restreint (`possible_minor`) est compté comme prédit sexuel, puisqu'une escalade B1-1 suppose un élément sexuel. Ici c'est un vrai positif (sv1-c089). Mais le drapeau mineur est faux et les scores de cet item sont effacés.

## Quantification

- **AUROC 0,916** sur max(sexual_violence, sexual_harassment) (`roc.png`). Les items restreints valent 100.
- **Meilleur seuil (Youden) : 85**, avec TPR 0,87 et FPR 0,07. Au seuil 50, le résultat est identique (P 0,93 · R 0,87) : les scores sont presque binaires (0 ou ≥ 80).

Pourcentage d'images avec un score ≥ 50, et score moyen :

| dimension | positifs (59 notés) | négatifs (60) | dont pièges (30) | dont neutres (30) |
|---|---|---|---|---|
| sexual_violence | 47,5 % · moy. 45 | 0 % · 0 | 0 % · 0 | 0 % · 0 |
| sexual_harassment | 72,9 % · 67 | 6,7 % · 6 | 13,3 % · 12 | 0 % · 0 |
| hate | 25,4 % · 29 | 23,3 % · 23 | 36,7 % · 35 | 10,0 % · 10 |
| misogyny | 62,7 % · 57 | 13,3 % · 12 | 26,7 % · 25 | 0 % · 0 |
| other_violence | 10,2 % · 11 | 8,3 % · 9 | 13,3 % · 13 | 3,3 % · 4 |
| **sexual (décision)** | **86,7 %** | **6,7 %** | 13,3 % | 0 % |

**Haine et misogynie face à la référence** (score ≥ 50, n = 119 notés) :

| | TP | FP | FN | TN | P | R | F1 |
|---|---|---|---|---|---|---|---|
| hate (réf. 31 oui) | 20 | 9 | 12 | 78 | 0,69 | 0,63 | 0,66 |
| misogyny (réf. 65 oui) | 42 | 3 | 21 | 53 | 0,93 | 0,67 | 0,78 |

La misogynie est sous-estimée : seuls 8 des 15 pièges sexistes sont notés misogynes (≥ 50), alors que la référence les marque tous misogynes. Les 21 FN de misogynie viennent surtout des items où le modèle met tous les scores à 0.

## Par catégorie (rappel sur `sexual`)

| catégorie | détectés / n |
|---|---|
| threat_incitement (SV-REL-2) | 8 / 8 |
| rape_joke_glorification (SV-REL-4) | 11 / 11 |
| collective_accusation (SV-REL-3) | 7 / 7 |
| denial_minimization (SV-REL-4) | 6 / 7 |
| victim_stigmatisation (SV-REL-5) | 4 / 5 |
| degrading_sexualisation | 8 / 10 |
| sexualised_insult | 6 / 10 |
| humiliating_objectification | 2 / 2 |

**Catégorie ou SV-REL correcte sur les TP : 20 / 51 (39,2 %).** Confusions fréquentes :
- les menaces, accusations collectives et négations sont rangées en « rape_joke_glorification » ;
- la sexualisation dégradante est rangée en « humiliating_objectification ».

Les frontières entre catégories sont floues pour le modèle. Le rapprochement par SV-REL l'est aussi : il ne donne souvent pas de `primary_relation`.

## Erreurs et exclusions

| | nombre |
|---|---|
| JSON invalide | 0 |
| refus | 0 |
| timeouts / erreurs serveur | 0 / 0 |
| `possible_minor` (restreint, scores effacés) | 1 (sv1-c089, à tort) |

## Tous les faux positifs (4) et faux négatifs (8)

Il y en a moins de 10 de chaque. Descriptions neutres, sans reproduire l'image.

**Faux positifs** (sexiste non sexuel jugé sexuel)

| item | ce que montre le mème | cause probable |
|---|---|---|
| `sv1-c187` | Stéréotype « blonde idiote » sur une femme au téléphone | Photo d'une femme en haut décolleté + sexisme → « sexualisation dégradante » : **l'image entraîne le label** |
| `sv1-c202` | Célébration d'une violence physique contre une femme réelle, insulte « bitch » | **Insulte genrée confondue avec une insulte sexuelle**, violence prise pour du harcèlement sexuel |
| `sv1-c208` | « Jeux olympiques féminins » = cuisine | Stéréotype domestique : le modèle **invente** une connotation sexuelle (« sexually available ») |
| `sv1-c212` | Stéréotype « veut parler au manager » sur des coupes de cheveux | Idem : **raison hallucinée** (« sexually motivated ») |

**Faux négatifs** (sexuel confirmé, jugé non sexuel)

| item | catégorie de référence | ce que montre le mème | cause probable |
|---|---|---|---|
| `sv1-c022` | denial_minimization | Nie qu'un rapport sexuel non payé à une travailleuse du sexe soit un viol (« c'est du vol à l'étalage ») | **Ironie lue au premier degré** : le modèle y voit une « fausse accusation moquée » et pas une négation du viol |
| `sv1-c049` | victim_stigmatisation | Discrédite deux femmes nommées qui ont dénoncé une agression sexuelle | Haine 85 et misogynie 90 bien vues, mais **SV-REL-5 non reconnu** : discréditer une plaignante n'est pas lu comme une stigmatisation de victime |
| `sv1-c112` | degrading_sexualisation | Référence à un agresseur conjugal connu, contrôle sexuel d'une compagne | **Référence culturelle** manquée ; tous les scores à 0 |
| `sv1-c126` | sexualised_insult | Ex-épouse traitée de travailleuse du sexe | Lu comme une « anecdote personnelle » : **insulte sexualisée ciblant une personne privée** manquée |
| `sv1-c127` | degrading_sexualisation | Expression faciale de la femme détournée en réaction sexuelle | **Sens porté par l'image seule** (expression) + texte anodin → manqué |
| `sv1-c136` | sexualised_insult | Photo d'une femme identifiable, légende « entrée publique » | **Double sens** (« public entrance ») non compris |
| `sv1-c157` | sexualised_insult | Excitation sexuelle bestiale attribuée à un groupe religieux | Le modèle pense que la cible est l'animal : **cible mal identifiée** |
| `sv1-c174` | sexualised_insult | Insulte de bestialité contre des musulmans | Haine 95 bien vue, mais **l'insulte sexuelle (bestialité) n'est pas comptée comme harcèlement sexuel**. Frontière de définition à trancher |

## À retenir pour le choix du modèle

- Pour la détection du caractère sexuel, Qwen3.5-9B est déjà une bonne référence (F1 0,90, AUROC 0,92). Les faiblesses sont localisées : insultes sexualisées ciblant une personne, doubles sens, et sexisme non sexuel sur-lu comme sexuel.
- **La quantification multi-dimensions est le point faible** : scores quasi binaires, dimensions non indépendantes, catégorie fine peu fiable (39 %).
- Le profil global n'est pas approuvé, donc le prompt tourne en core seul. Ce sera le même pour les autres modèles : la comparaison reste équitable.
