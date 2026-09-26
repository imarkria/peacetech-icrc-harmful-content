"""Check that the policy defines every required ID and that nothing cites an unknown one.

    python scripts/check_policy_ids.py            # exit code 1 if anything is missing or unknown

1. core.md defines every ID of the required list (definitions, relations, harm types, pathways, affiliation, age,
   features, barriers) and the required sections (flag rule, priority, risk flags, decision procedure, v1.1).
2. children.md, modalities.md and the platform profiles exist.
3. Every policy ID cited in the code (harmwatch/, scripts/, tests/), the region profiles and the examples is defined
   in a policy layer or is a region entry ID / type.
"""

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
POLICY = ROOT / "policy"

REQUIRED_CORE = (
    ["SV-DEF", "SV-EL-A", "SV-EL-B", "SV-EL-C", "CONF-DEF", "HI-DEF", "AFF-DEF", "AGE-DEF"]
    + [f"SV-CO-{i}" for i in range(1, 7)]
    + [f"SV-FORM-{i:02d}" for i in range(1, 11)]
    + [f"SV-REL-{i}" for i in range(1, 6)]
    + [f"HI-TYPE-{i:02d}" for i in range(1, 7)]
    + [f"HP-{i:02d}" for i in range(1, 8)]
    + [f"AFF-{i}" for i in range(1, 5)]
    + [f"CONF-{i}" for i in range(1, 5)]
    + ["FT-STANCE", "FT-TARGET", "FT-GENERAL", "FT-MODAL", "FT-CTA", "FT-FRAME", "FT-SPEAKER"]
    + ["B1-1", "B1-2", "B1-3", "B1-4", "B2-1", "B2-2", "B2-3", "B2-4", "B2-5", "B3", "B5", "B6-1", "B6-2", "B6-3"]
)
REQUIRED_SECTIONS = {
    "flag rule (3 axes)": r"## Flag rule[\s\S]*Axis 1[\s\S]*Axis 2[\s\S]*AFF-1/2/3",
    "priority": r"## Priority[\s\S]*Urgent[\s\S]*High[\s\S]*Standard",
    "risk flags": r"possible_minor[\s\S]*identifiable_person[\s\S]*possible_manipulated_media",
    "decision procedure": r"## Decision procedure",
    "barriers B1-B6": r"## Barriers",
    "v1.1 'reports' clarification": r"Clarification \(v1\.1\)[\s\S]*attributed source",
    "v1.1 SV-EL-C": r"SV-EL-C = CONF-DEF",
}
REQUIRED_FILES = ["core.md", "children.md", "modalities.md", "platforms/telegram.md", "platforms/generic.md"]

# Policy IDs only (known prefixes), so that e.g. "UTF-8" or "GPT-4" in code is not taken for one.
CITED = re.compile(r"(?<![\w-])(?:SV-(?:EL-[ABC]|CO-\d|FORM-\d\d|REL-\d|DEF)|HI-(?:TYPE-\d\d|DEF)|HP-\d\d|AFF-(?:\d|DEF)"
                   r"|AGE-DEF|CONF-(?:\d|DEF)|FT-[A-Z]+|CH-\d[ab]?|TG-L\d|GEN-L\d|MOD-[A-Z]+|B\d(?:-\d)?"
                   r"|RG-[A-Z]+(?:-\d{3})?)(?![\w-])")
def main() -> int:
    rows: list[tuple[str, bool, str]] = []
    for f in REQUIRED_FILES:
        rows.append((f"policy/{f} present", (POLICY / f).exists(), ""))
    core = (POLICY / "core.md").read_text(encoding="utf-8")
    core_ids = set(CITED.findall(core)) | set(re.findall(r"\b[A-Z]{2,4}-DEF\b", core))
    missing = [i for i in REQUIRED_CORE if i not in core_ids]
    rows.append(("core.md defines required IDs", not missing, ", ".join(missing) or f"{len(REQUIRED_CORE)} IDs"))
    for name, pattern in REQUIRED_SECTIONS.items():
        rows.append((f"core.md: {name}", bool(re.search(pattern, core)), ""))

    known: set[str] = set()
    for f in POLICY.rglob("*.md"):
        known |= set(CITED.findall(f.read_text(encoding="utf-8"))) | set(re.findall(r"\b[A-Z]{2,4}-DEF\b", f.read_text()))
    profiles = {p.stem: yaml.safe_load(p.read_text(encoding="utf-8")) for p in (POLICY / "regions").glob("*.yaml")
                if not p.stem.endswith("_filter")}
    for doc in profiles.values():
        known |= {e["id"] for e in doc["entries"]} | {e["type"] for e in doc["entries"]}

    unknown: dict[str, set[str]] = {}

    def check(where: str, text: str):
        for i in CITED.findall(text):
            if i not in known:
                unknown.setdefault(i, set()).add(where)

    for region, doc in profiles.items():
        for e in doc["entries"]:
            check(f"regions/{region}.yaml:{e['id']}", " ".join(e.get("supports", [])) + " " + (e.get("meaning") or "")
                  + " " + (e.get("context_notes") or ""))
    for p in (POLICY / "regions").glob("*_examples.jsonl"):
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                x = json.loads(line)
                check(f"{p.name}:{x['id']}", json.dumps(x["expected"]) + " " + x.get("why", ""))
    for d in ("harmwatch", "scripts", "tests"):
        for p in (ROOT / d).glob("*.py"):
            if p.name != Path(__file__).name:
                check(str(p.relative_to(ROOT)), p.read_text(encoding="utf-8"))
    rows.append(("no unknown ID cited in code / profiles / examples", not unknown,
                 "; ".join(f"{i} in {', '.join(sorted(w))}" for i, w in sorted(unknown.items())) or f"{len(known)} known IDs"))

    width = max(len(r[0]) for r in rows)
    for name, ok, detail in rows:
        print(f"{'OK' if ok else 'KO'}  {name:<{width}}  {detail}")
    return 0 if all(ok for _, ok, _ in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
