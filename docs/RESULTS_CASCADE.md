# Cascade images : un filtre rapide devant le juge complet

2026-09-27 · branche `gmikou/cascade-test` · juge = Qwen3.5-9B (prompt v3 figé `9160fe72…`, et v1 pour comparaison) · V100 32 Go.

## La phrase clé

> **Le filtre traite 32 images/s et n'envoie que 73 % des images au juge complet, pour 2 positifs perdus sur 60. La cascade obtient un F1 de 0,915, contre 0,933 pour Qwen seul (prompt v3), et divise le temps par 1,33 sur ce benchmark.**
>
> Avec le prompt v1 comme juge : F1 0,894 pour la cascade, contre 0,912 pour Qwen seul.
>
> Le benchmark contient 50 % de positifs, donc le gain de temps y est forcément faible. En extrapolant le taux de faux positifs du filtre mesuré sur le DEV, on obtiendrait environ ×2,2 à 5 % de prévalence. **C'est une projection, pas une mesure.**
>
> **À 10 % de prévalence (579 images : benchmark + négatifs du DEV)**, le filtre envoie 48 % des images à Qwen, bloque 2 positifs sur 60 et **divise le temps par 2,01** (voir la section dédiée).

Le filtre retenu est l'étudiant **I_logreg** : une régression logistique sur les embeddings SigLIP2 de l'image. Il a été choisi **sur le DEV** avant tout contact avec le benchmark. Son seuil vise **95 % de rappel face au professeur**, lui aussi réglé sur le DEV.

## Qwen seul, étudiant seul, cascade (benchmark sv_images_v1 : 60 sexuels / 60 non sexuels, référence validée)

| système | TP | FP | FN | TN | précision | rappel | F1 | images envoyées à Qwen | positifs perdus par le filtre | secondes / image |
|---|---|---|---|---|---|---|---|---|---|---|
| **Qwen3.5-9B seul, v3** | 56 | 4 | 4 | 56 | 0,933 | 0,933 | **0,933** | 100 % | – | 1,508 |
| Qwen3.5-9B seul, v1 (officiel) | 57 | 8 | 3 | 52 | 0,877 | 0,950 | 0,912 | 100 % | – | 1,637 |
| Étudiant I_logreg seul (seuil 95 %) | 58 | 30 | 2 | 30 | 0,659 | 0,967 | 0,784 | – | – | 0,031 |
| **Cascade I_logreg → Qwen v3, seuil 95 %** | 54 | 4 | 6 | 56 | 0,931 | 0,900 | **0,915** | **73 %** (88/120) | **2 / 60** | 1,137 (÷1,33) |
| Cascade → Qwen v3, seuil 97 % | 54 | 4 | 6 | 56 | 0,931 | 0,900 | 0,915 | 79 % | 2 / 60 | 1,224 (÷1,23) |
| Cascade → Qwen v3, seuil 99 % | 56 | 4 | 4 | 56 | 0,933 | 0,933 | 0,933 | 90 % | 0 / 60 | 1,388 (÷1,09) |
| Cascade → Qwen v1, seuil 95 % | 55 | 8 | 5 | 52 | 0,873 | 0,917 | 0,894 | 73 % | 2 / 60 | 1,232 (÷1,33) |

- AUROC de l'étudiant retenu face à la référence : 0,935.
- Le temps de la cascade = embeddings pour toutes les images + Qwen seulement pour les images envoyées. Le temps de Qwen est celui mesuré lors des runs v3 et v1 (8 requêtes en parallèle).
- Au seuil 99 %, la cascade garde **exactement** les performances de Qwen seul, mais le gain de temps est minime.

**Ce que la distillation apporte** (bonus d). Les mêmes étudiants, entraînés sur les **labels du dataset** (misogyne / haineux) au lieu du professeur, ont une AUROC face à la référence de **0,71 à 0,79**, contre 0,895 à 0,969 avec le professeur. Pour garder 95 % de rappel, ils doivent envoyer 88 à 94 % des images au juge, contre 73 %. Les labels des datasets ne mesurent pas le caractère sexuel : il faut le professeur.

## Test du filtre à 10 % de prévalence

Le benchmark contient 50 % de positifs, ce qui plafonne le gain de temps. Pour mesurer le filtre à une prévalence plus réaliste **sans nouvel appel à Qwen**, j'ai ajouté aux 120 images du benchmark **les 459 négatifs du DEV**. Ces négatifs sont étiquetés par le professeur et n'ont jamais servi à l'entraînement.
- Total : 579 images, dont **60 positifs (10,4 %)** issus de la référence validée à la main.
- Le filtre est **figé** : I_logreg, seuil réglé sur le DEV pour 95 % de rappel.
- Les calculs réutilisent uniquement les embeddings et les étiquettes existants.

| jeu | positifs passés | positifs bloqués | négatifs passés | négatifs bloqués | rappel [IC 95 %] | taux de faux passages [IC 95 %] | envoyé à Qwen | temps par image | gain |
|---|---|---|---|---|---|---|---|---|---|
| **579 images (10,4 % positives)** | 58 | **2** | 219 | 300 | **0,967** [0,886-0,991] | 0,422 [0,380-0,465] | **47,8 %** | 0,75 s | **÷2,01** |
| 120 images du benchmark (50 %) | 58 | 2 | 30 | 30 | 0,967 [0,886-0,991] | 0,500 [0,377-0,623] | 73,3 % | 1,13 s | ÷1,33 |

- **Temps estimé** = temps du filtre (0,027 s par image : embedding SigLIP2 + régression, soit 36,9 images/s mesurées) + part envoyée × 1,51 s (temps de Qwen v3 par image mesuré sur le benchmark), comparé à 1,51 s pour Qwen sur toutes les images.
- **Positifs bloqués** (les mêmes dans les deux jeux) :
  - `sv1-c046` : accusation collective ; photo d'une foule, avec un texte qui attribue des abus sexuels sur animaux à un groupe religieux (score 0,088) ;
  - `sv1-c062` : accusation collective ; photo d'un animal, avec un texte qui moque un groupe national par une plaisanterie de « survivante de viol » (score 0,090).

  Dans les deux cas, le sens est porté par le texte, alors que le filtre ne voit que l'image.
- **Lecture :** à 10 % de prévalence, le filtre envoie un peu moins de la moitié des images au juge complet et **divise le temps par 2**, pour **2 positifs perdus sur 60**. Le gain reste plafonné par le taux de faux passages, d'environ 42 % : le filtre image laisse passer beaucoup de négatifs, surtout des photos de femmes sans contenu sexuel.

**Limites propres à ce test :**
- **Les 459 négatifs du DEV sont étiquetés par Qwen, pas vérifiés à l'œil.** Quelques « négatifs » pourraient être des positifs manqués par Qwen, et inversement.
- **Le seuil et le choix de l'étudiant ont été faits sur ce même DEV.** Le taux de faux passages mesuré sur ses négatifs (0,42) est donc possiblement un peu optimiste. Sur les 60 négatifs du benchmark, jamais vus, il est de 0,50.
- Les 60 positifs sont ceux du benchmark : l'IC du rappel reste large (0,886-0,991).
- Un essai sur un flux de 1 000 mèmes jamais utilisés avait été lancé : filtre passé (27,7 % envoyés au seuil 95 %), mais jugement Qwen arrêté à 210 sur 1 000 sur décision de méthode. **Ce flux n'est pas utilisé comme résultat.**

## Figures

- `docs/figures/cascade_filter_10pct_confusion.png` : matrices du filtre à 10,4 % et à 50 % de prévalence.
- `docs/figures/cascade_confusion_qwen_vs_cascade.png` : matrices de Qwen seul et de la cascade, côte à côte.
- `docs/figures/cascade_recall_vs_sent.png` : rappel en fonction de la part d'images envoyées à Qwen, pour les étudiants T, I et I+T, avec les points de fonctionnement.
- `docs/figures/cascade_time_per_image.png` : temps par image (filtre, Qwen seul, cascade mesurée, cascade projetée).

## Données

- **Pool d'entraînement** : 3 000 mèmes de QCRI/MemeLens (tous splits), seed 42. Les strates sont MAMI violence / objectification / shaming / autres misogynes / négatifs, et FHM et MMHS haineux / non haineux.
- **Exclus avant l'étiquetage : 681 candidats**, dont :
  - 406 mis en quarantaine par le filtre d'images explicites ;
  - 146 pour un indicateur d'âge dans le texte ;
  - **34 quasi-copies du benchmark ou de ses 57 ambigus** (pHash ≤ 8, anti-fuite) ;
  - 95 doublons à l'intérieur du pool.
- **Professeur** : Qwen3.5-9B avec le prompt v3 figé, image + texte. 3 000 images en 72 min (41,6 images/min), 0 erreur. **120 images exclues** parce que le professeur a levé `possible_minor` (CH-5).
- **Données utilisables : 2 880**.
  - Entraînement : 2 300, dont **464 sexuelles** (20 %).
  - DEV : 580, dont **121 sexuelles**. Le DEV sert au choix de l'étudiant et des seuils.
- **Benchmark** : les 120 images de sv_images_v1, **utilisées une seule fois, pour le test final**. Aucun réglage n'a été fait dessus.
- **Features** :
  - T = Qwen3-Embedding-0.6B sur le texte incrusté ;
  - I = SigLIP2 so400m sur l'image ;
  - I+T = concaténation des deux.
- **Classifieurs** : régression logistique et MLP. La régularisation est choisie par validation croisée à 5 plis **sur l'entraînement seul**. L'équilibrage (`class_weight="balanced"` ou sous-échantillonnage 50/50) est choisi sur le DEV : la pondération gagne partout sauf pour T_logreg.

| étudiant | AUROC DEV (vs professeur) | rappel DEV si 50 % envoyés | part envoyée au seuil 95 % (DEV) | AUROC benchmark (vs référence) |
|---|---|---|---|---|
| T_logreg (texte) | 0,816 | 0,835 | 71 % | 0,895 |
| **I_logreg (image)** ← retenu | **0,905** | **0,942** | **52 %** | 0,935 |
| I+T_logreg | 0,902 | 0,934 | 58 % | 0,965 |
| I_mlp / I+T_mlp | 0,889 / 0,897 | 0,917 / 0,926 | 54 % / 53 % | 0,938 / 0,969 |

**Seuil d'arrêt respecté** : le meilleur étudiant atteint un rappel DEV de 94,2 % en n'envoyant que 50 % des images, au-dessus du minimum de 90 %. Il n'a donc pas été nécessaire d'étiqueter plus de mèmes.

Sur le benchmark, **I+T** aurait été un peu meilleur (AUROC 0,965, 0 positif perdu au seuil 95 %, mais 80 % envoyés). Il n'a pas été retenu, parce que le choix se fait sur le DEV et jamais sur le test.

## Cinq erreurs expliquées

| # | image | ce qui se passe (neutre) | cause probable |
|---|---|---|---|
| 1 | sv1-c046 (accusation collective) | photo d'une foule ; le texte attribue des abus sexuels sur animaux à un groupe religieux | **Perdue par le filtre** (score 0,09) : le sens est dans le texte, et I_logreg ne voit que l'image. |
| 2 | sv1-c062 (accusation collective) | photo d'un animal ; le texte moque un groupe national avec une « survivante de viol » | **Perdue par le filtre**, même cause. C'est aussi un cas limite (insulte de bestialité). I+T l'aurait gardée. |
| 3 | sv1-c187 (sexisme non sexuel) | photo d'une femme en décolleté, stéréotype de la « blonde idiote » | **Score filtre le plus haut parmi les négatifs** (0,81) : l'image « ressemble » à du contenu sexuel. Qwen v3 la juge ensuite correctement, sans erreur dans la cascade. |
| 4 | 22 pièges sur 30 envoyés | mèmes sexistes non sexuels avec des photos de femmes | Le filtre image ne sépare pas « femme photographiée » et « contenu sexuel » : spécificité faible (8 neutres sur 30 envoyés, contre 22 pièges sur 30). C'est le juge qui fait le tri. |
| 5 | sv1-c049, c127, c136, c174 | discrédit de plaignantes, double sens, expression du visage, insulte de bestialité | **Erreurs du juge, héritées telles quelles par la cascade** : un filtre ne peut pas corriger le juge, il ne peut qu'ajouter des pertes. |

## Limites

- **Les étiquettes d'entraînement sont celles de Qwen, pas d'humains.** L'étudiant reproduit les biais du professeur, par exemple le sexisme lu comme sexuel. Seul le benchmark de test a une référence validée à la main.
- **406 images ont été écartées par le filtre d'images explicites, dont 196 viennent des strates MAMI positives** (117 objectification, 35 violence, 33 shaming, 11 autres). Le pool manque donc justement des images sexualisées les plus visuelles : l'étudiant ne les a jamais vues, et en production elles seraient mises en quarantaine avant lui.
- **Seulement 120 images de test**, avec 50 % de positifs. Le gain de temps mesuré (÷1,33) dépend de cette prévalence ; la projection ×2,2 à 5 % n'est pas mesurée. De plus, le filtre laisse passer environ 41 % des négatifs du DEV, ce qui plafonne le gain autour de ×2,3.
- **Contamination possible** : MAMI, FHM et MMHS sont publics depuis des années, pour Qwen, SigLIP2 et Qwen3-Embedding.
- **Conformité B5-4** : les étudiants sont entraînés sur des **features** (embeddings) et des étiquettes. **Les 3 000 images du pool ont été supprimées après le calcul des embeddings**. Seuls les embeddings, les hashes (sha256, pHash) et les étiquettes sont conservés, hors git ; aucun modèle ne contient d'image.
  - L'étudiant **T (texte seul) est pleinement conforme à B5-4**.
  - **Les étudiants I et I+T utilisent des features dérivées des images : c'est une expérimentation de recherche, à valider par l'équipe avant tout usage opérationnel.** Le filtre retenu, I_logreg, est dans ce cas.
- **Images seulement** : les vidéos viendraient ensuite, segment par segment. Le filtre s'appliquerait aux captures, à la transcription et à l'OCR avant le juge.
- La régularisation retenue (C = 0,001) est à l'intérieur de la grille testée, après élargissement de celle-ci, ce qui valide le choix.

Détails : `results/cascade/` (hors git) : `metrics.json`, `train_metrics.json`, `prevalence_projection.json`, matrices et courbe. Code : `harmwatch/cascade.py`, `scripts/eval_cascade.py`.
