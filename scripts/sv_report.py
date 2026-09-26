"""Reports for the sexual-character benchmark.

    python scripts/sv_report.py model qwen35-9b     # results/sv_benchmark/<model>/summary.md
    python scripts/sv_report.py leaderboard         # results/sv_benchmark/leaderboard.md + .csv

FP / FN are described by the neutral reference reason (written at annotation time) and the model's own one-sentence
reason; the probable cause is written by hand in data/benchmarks/sv_causes.json ({model: {item_id: cause}}).
No image and no embedded text is reproduced.
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results" / "sv_benchmark"
CAUSES = ROOT / "data" / "benchmarks" / "sv_causes.json"
MODES = ("image_text", "text_only", "ambiguous")
LIMITS = """## Limites

- **Cas clairs uniquement.** Les 57 cas ambigus ont été exclus du benchmark : les scores mesurent la capacité à trancher des cas nets. Sur des contenus réels, où l'ambiguïté domine, les performances seront plus basses. Le run « ambigus » montre seulement comment le modèle se comporte sur ces cas, pas s'il a raison.
- **Sélection par mots-clés.** Les candidats positifs ont été tirés par mots-clés (viol, insultes sexuelles, vocabulaire sexuel) dans le texte incrusté. Seuls 10 positifs sur 60 n'ont aucun mot-clé explicite : le benchmark favorise les modèles qui lisent bien le texte. Le rappel « sans mot-clé » (n = 10) est très incertain.
- **Référence annotée par Claude.** Une seule annotatrice (un modèle, Claude), selon policy/, validée par gmikou sur 20 cas. Pas d'accord inter-annotateurs mesuré. Les choix d'annotation (haine / misogynie, insultes de bestialité, exclusion de tout mineur) orientent les résultats.
- **Contamination possible.** MAMI, FHM et MMHS sont publics depuis des années et ont pu être vus à l'entraînement par les modèles testés, avec leurs labels. Cela peut gonfler leurs scores de façon inégale.
- **Petits effectifs.** 60 / 60 : un écart de 2-3 erreurs entre modèles n'est pas significatif (IC 95 % du F1 d'environ ±0,06).
- **Prompt unique.** Un seul prompt figé (sv_prompt_v1), conçu et mis au point sur Qwen3.5-9B. Les autres modèles peuvent être désavantagés par un prompt qui n'a pas été adapté pour eux.
- **Profil global non approuvé.** Le prompt tourne en core seul : les 12 entrées du profil global sont encore `proposed`.
"""


def load(model: str, mode: str) -> dict | None:
    p = RESULTS / model / mode / "metrics.json"
    return json.loads(p.read_text()) if p.exists() else None


def preds(model: str, mode: str) -> dict:
    p = RESULTS / model / mode / "predictions.jsonl"
    return {json.loads(l)["item_id"]: json.loads(l) for l in p.read_text().splitlines() if l.strip()} if p.exists() else {}


def f(v, nd=3):
    if v is None:
        return "–"
    if isinstance(v, float):
        return f"{v:.1f}" if abs(v) >= 10 else f"{v:.{nd}f}"
    return str(v)


def model_report(model: str):
    causes = (json.loads(CAUSES.read_text()) if CAUSES.exists() else {}).get(model, {})
    it, tx, amb = load(model, "image_text"), load(model, "text_only"), load(model, "ambiguous")
    info = json.loads((RESULTS / model / "image_text" / "run_info.json").read_text())
    L = [f"# {model} — benchmark « caractère sexuel » sv_images_v1", "",
         f"Backend {info['backend']} (`{info['api_model']}`) · V100 32 Go · {info['workers']} requêtes parallèles · température 0 · "
         f"prompt figé `sv_prompt_v1` ({info['prompt_sha256'][:12]}…) · profil {info['profile']}.", ""]
    L += ["## Résultats principaux", "", "| mesure | image + texte | texte seul |", "|---|---|---|"]
    rows = [("F1 sexual", lambda m: m["sexual"]["f1"]), ("précision", lambda m: m["sexual"]["precision"]),
            ("rappel", lambda m: m["sexual"]["recall"]), ("spécificité", lambda m: m["sexual"]["specificity"]),
            ("TP / FP / FN / TN", lambda m: f"{m['sexual']['TP']} / {m['sexual']['FP']} / {m['sexual']['FN']} / {m['sexual']['TN']}"),
            ("rappel positifs sans mot-clé", lambda m: f"{m['positives_without_keyword']['detected']}/{m['positives_without_keyword']['n']}"),
            ("AUROC P(sexual) logprobs", lambda m: (m["logprob"].get("sexual") or {}).get("auroc")),
            ("ECE / Brier P(sexual)", lambda m: "{} / {}".format(*(lambda c: (c["ece"], c["brier"]))(m["logprob"]["sexual"]["calibration"])) if m["logprob"].get("sexual") else "–"),
            ("AUROC score écrit", lambda m: m["written_scores"]["auroc"]),
            ("valeurs distinctes du score écrit", lambda m: m["written_scores"]["distinct_values"]),
            ("AUROC haine (logprobs)", lambda m: (m["logprob"].get("hate") or {}).get("auroc")),
            ("AUROC misogynie (logprobs)", lambda m: (m["logprob"].get("misogyny") or {}).get("auroc")),
            ("F1 haine (décision)", lambda m: m["hate_vs_reference"]["f1"]),
            ("F1 misogynie (décision)", lambda m: m["misogyny_vs_reference"]["f1"]),
            ("catégorie ou SV-REL correcte (TP)", lambda m: f"{m['tp_category_or_relation_correct']['pct']} %"),
            ("JSON invalide / timeouts / refus", lambda m: f"{m['counts']['invalid_json']} / {m['counts']['timeouts']} / {m['counts']['refusals']}"),
            ("possible_minor levé (à tort)", lambda m: m["counts"]["restricted_possible_minor"]),
            ("débit (images/min)", lambda m: m["throughput"]["images_per_min"]),
            ("VRAM pic (Mo)", lambda m: m["throughput"]["vram_peak_mib"]),
            ("temps total (s)", lambda m: m["throughput"]["total_seconds"])]
    for name, fn in rows:
        vals = []
        for m in (it, tx):
            try:
                vals.append(f(fn(m)) if m else "–")
            except Exception:
                vals.append("–")
        L.append(f"| {name} | {vals[0]} | {vals[1]} |")
    L += ["", "Fichiers : `image_text/` et `text_only/` → confusion.csv/png, confusion_hate / confusion_misogyny, roc.png, "
          "calibration.png, metrics.json, predictions.jsonl.", ""]
    if it:
        L += ["## Pourcentages par classe de référence (image + texte, score ≥ 50 · moyenne)", "",
              "| dimension | positifs | négatifs | pièges | neutres |", "|---|---|---|---|---|"]
        br = it["by_reference_class"]
        for d in ("sexual_violence", "sexual_harassment", "hate", "misogyny", "other_violence"):
            L.append(f"| {d} | " + " | ".join(f"{br[k][f'pct_{d}_ge50']} % · {br[k][f'mean_{d}']}"
                                              for k in ("positives", "negatives", "negatives_trap", "negatives_neutral")) + " |")
        L.append("| **sexual (décision)** | " + " | ".join(f"{br[k]['pct_sexual_pred']} %" for k in
                                                       ("positives", "negatives", "negatives_trap", "negatives_neutral")) + " |")
        L += ["", "Rappel par catégorie (image + texte) : " + ", ".join(
            f"{k} {v['detected']}/{v['n']}" for k, v in it["by_category_recall"].items()), ""]
        pi, pt = preds(model, "image_text"), preds(model, "text_only")
        if pt:
            helps = [i for i in pi if pi[i]["prediction"] and pt[i]["prediction"]
                     and pi[i]["prediction"]["sexual"] == pi[i]["reference"]["sexual"] != pt[i]["prediction"]["sexual"]]
            hurts = [i for i in pi if pi[i]["prediction"] and pt[i]["prediction"]
                     and pt[i]["prediction"]["sexual"] == pt[i]["reference"]["sexual"] != pi[i]["prediction"]["sexual"]]
            L += [f"**Apport de l'image** : corrige {len(helps)} cas ({', '.join(helps) or '–'}), en dégrade {len(hurts)} "
                  f"({', '.join(hurts) or '–'}).", ""]
        for kind, label in (("FP", "Faux positifs"), ("FN", "Faux négatifs")):
            ids = it["errors"][kind]
            L += [f"## {label} (image + texte) : {len(ids)}", "",
                  "| item | catégorie réf. | référence (neutre) | P(sexual) | raison du modèle | cause probable |", "|---|---|---|---|---|---|"]
            for i in ids:
                p = pi[i]
                a = p["prediction"]
                ps = (a.get("p_true") or {}).get("sexual")
                L.append(f"| `{i}` | {p['reference']['category']} | {p['reference']['reason']} | {f(ps, 2)} | "
                         f"{a['reason'].replace('|', '/')} | {causes.get(i, '–')} |")
            L.append("")
    if amb:
        a = amb["ambiguous"]
        L += ["## Cas ambigus exclus (57, sans référence : distribution seulement)", "",
              f"- jugés sexuels : {a['pct_sexual_pred']} % ; P(sexual) entre 0,2 et 0,8 : {a['p_sexual_between_0.2_0.8']} items "
              f"(déciles 0→1 : {a['p_sexual_hist_deciles']}) ; possible_minor : {amb['counts']['restricted_possible_minor']}.",
              "- scores écrits (moyenne · % ≥ 50 · histogramme [0-25, 25-50, 50-75, 75-100]) :"]
        for d in ("sexual_violence", "sexual_harassment", "hate", "misogyny", "other_violence"):
            L.append(f"  - {d} : {a[d]['mean']} · {a[d]['pct_ge50']} % · {a[d]['hist_0_25_50_75_100']}")
        L.append("")
    L.append(LIMITS)
    (RESULTS / model / "summary.md").write_text("\n".join(L), encoding="utf-8")
    print(RESULTS / model / "summary.md")


def leaderboard(models: list[str]):
    rows = []
    for mdl in models:
        it, tx = load(mdl, "image_text"), load(mdl, "text_only")
        if not it:
            rows.append({"model": mdl, "status": "not run"})
            continue
        amb = load(mdl, "ambiguous")
        rows.append({
            "model": mdl, "status": "ok",
            "f1_image_text": it["sexual"]["f1"], "recall_image_text": it["sexual"]["recall"],
            "precision_image_text": it["sexual"]["precision"],
            "f1_text_only": tx["sexual"]["f1"] if tx else None, "recall_text_only": tx["sexual"]["recall"] if tx else None,
            "recall_no_keyword": f"{it['positives_without_keyword']['detected']}/{it['positives_without_keyword']['n']}",
            "FP": it["sexual"]["FP"], "FN": it["sexual"]["FN"],
            "auroc_logprob_sexual": (it["logprob"].get("sexual") or {}).get("auroc"),
            "ece_sexual": (it["logprob"].get("sexual") or {}).get("calibration", {}).get("ece"),
            "auroc_written": it["written_scores"]["auroc"],
            "auroc_hate": (it["logprob"].get("hate") or {}).get("auroc"),
            "auroc_misogyny": (it["logprob"].get("misogyny") or {}).get("auroc"),
            "pct_hate_pos_vs_neg": f"{it['by_reference_class']['positives']['pct_hate_ge50']} / {it['by_reference_class']['negatives']['pct_hate_ge50']}",
            "pct_misogyny_pos_vs_neg": f"{it['by_reference_class']['positives']['pct_misogyny_ge50']} / {it['by_reference_class']['negatives']['pct_misogyny_ge50']}",
            "f1_hate": it["hate_vs_reference"]["f1"], "f1_misogyny": it["misogyny_vs_reference"]["f1"],
            "category_ok_pct": it["tp_category_or_relation_correct"]["pct"],
            "valid_json": f"{it['counts']['valid']}/{it['counts']['n']}",
            "possible_minor_false_alarms": it["counts"]["restricted_possible_minor"],
            "images_per_min": it["throughput"]["images_per_min"], "vram_peak_mib": it["throughput"]["vram_peak_mib"],
            "ambiguous_pct_sexual": amb["ambiguous"]["pct_sexual_pred"] if amb else None,
        })
    ok = [r for r in rows if r["status"] == "ok"]
    keys = list(ok[0].keys()) if ok else ["model", "status"]
    with open(RESULTS / "leaderboard.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return rows


if __name__ == "__main__":
    if sys.argv[1] == "model":
        model_report(sys.argv[2])
    else:
        for r in leaderboard(sys.argv[2:]):
            print(r)
