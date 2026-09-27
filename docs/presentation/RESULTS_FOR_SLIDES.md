# Results for the slides / Résultats pour les slides

All numbers come from `docs/results/ALL_METRICS.csv` and the timing files; hardware 1× NVIDIA V100 32 GB. Figures: `docs/presentation/figures/<name>.png` (300 dpi) and `.pdf`.

## 1. Images — the method works whatever the model

- **EN:** With the same frozen definition (prompt v1), four open vision models detect the sexual character of memes with F1 0.90–0.92 and AUROC 0.95–0.97 on 120 hand-validated images; no difference between them is statistically significant.
- **FR :** Avec la même définition figée (prompt v1), quatre modèles de vision ouverts détectent le caractère sexuel des mèmes avec un F1 de 0.90 à 0.92 et une AUROC de 0.95 à 0.97 sur 120 images validées à la main ; aucune différence entre eux n'est significative.
- **EN:** The definition, not the model, drives the result: all four make the same main error (sexist but non-sexual memes read as sexual).
- **FR :** C'est la définition, pas le modèle, qui fait le résultat : les quatre font la même erreur principale (mèmes sexistes non sexuels lus comme sexuels).
- **Numbers:** Qwen3.5-9B F1 0.912 [0.85-0.96], AUROC 0.975, 37 img/min; Qwen3.5-4B F1 0.912 [0.85-0.96], AUROC 0.974, 46 img/min; Gemma 4 12B F1 0.918 [0.86-0.96], AUROC 0.952, 22 img/min; InternVL3.5-8B F1 0.898 [0.83-0.95], AUROC 0.948, 32 img/min.
- **Figures:** `images_4models_confusions`, `images_4models_f1_auroc_ci`; annex `annex_images_v1_v3_and_text_only`.
- **Limit:** 120 clear cases selected by keywords, reference annotated by Claude (20 checked by the team); public datasets (possible contamination).

## 2. Video — segment-by-segment method (racism test)

- **EN:** Cutting a video into segments and judging each one (frames + transcript + on-screen text) flags racist videos with F1 0.97 (15/15 found, 1 false alarm) and AUROC 1.00; without the frames, F1 0.94.
- **FR :** En découpant la vidéo en segments jugés un par un (captures + transcription + texte à l'écran), on repère les vidéos racistes avec un F1 de 0.97 (15/15 trouvées, 1 fausse alerte) et une AUROC de 1.00 ; sans les captures, F1 0.94.
- **EN:** It runs 4.7× faster than real time on one V100 (≈ 2.1 min for a 10-min video, estimate).
- **FR :** Elle tourne 4.7 fois plus vite que le temps réel sur un V100 (≈ 2.1 min pour une vidéo de 10 min, estimation).
- **Numbers:** B TP 15 FP 1 FN 0 TN 14; C TP 15 FP 2 FN 0 TN 13; layer: speech 89, on-screen text 24, visuals 1; localisation top-1 14/15, top-3 15/15.
- **Figures:** `video_racism_confusions_roc`, `video_triggered_layer`.
- **Limit:** racism ≠ sexual violence (the test validates the method); 30 videos; localisation NOT demonstrated (annotated passages cover 79 % of each video).

## 3. Fast filter + judge (cascade, images)

- **EN:** A small filter distilled from Qwen reads 37 images/s; at 10 % prevalence it sends 48 % of images to the full judge, loses 2/60 positives and halves the compute time (÷2.01).
- **FR :** Un petit filtre distillé de Qwen lit 37 images/s ; à 10 % de prévalence, il n'envoie que 48 % des images au juge complet, perd 2 positifs sur 60 et divise le temps de calcul par 2.01.
- **EN:** Distillation matters: students trained on Qwen's labels reach AUROC 0.90–0.97, vs 0.71–0.79 with the datasets' own labels.
- **FR :** La distillation compte : entraînés sur les étiquettes de Qwen, les étudiants atteignent une AUROC de 0.90 à 0.97, contre 0.71 à 0.79 avec les labels des datasets.
- **Numbers:** cascade F1 0.915 vs 0.933 Qwen alone (benchmark, 50 %: 73 % sent, ÷1.33); 10.4 %: recall 0.967 [0.89-0.99], false passes 0.42.
- **Figures:** `cascade_filter_50_vs_10pct`, `cascade_qwen_alone_vs_cascade`, `cascade_recall_curve_and_distillation`.
- **Limit:** training labels = Qwen, not humans; the selected filter uses image features (research experiment, B5: never train on media); the 459 extra negatives are Qwen-labelled and the threshold was set on the same DEV.

## 4. Compute time (1× V100 32 GB)

- **EN:** One image takes 1.51 s with the full judge and 0.027 s with the filter; the cascade brings it to 0.75 s at 10 % prevalence (estimate). Video: 12.8 s of compute per minute of video.
- **FR :** Une image prend 1.51 s avec le juge complet et 0.027 s avec le filtre ; la cascade la ramène à 0.75 s à 10 % de prévalence (estimation). Vidéo : 12.8 s de calcul par minute de vidéo.
- **EN:** Video cascade not measured (not executed); hypothesis only: 5.4 s/min if 20 % of segments reach the judge, 8.3 s/min if 50 %.
- **FR :** Cascade vidéo non mesurée (non exécutée) ; hypothèse seulement : 5.4 s/min si 20 % des segments vont au juge, 8.3 s/min si 50 %.
- **Figure:** `compute_time_images_and_video`. Full table: `TABLES.md` section 4.
- **Limit:** judge times with 8 parallel requests on one GPU; cascade times are estimates (filter + share sent × measured judge time); videos ≤ 4 min.
