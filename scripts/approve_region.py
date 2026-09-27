"""Review and approve region profile entries. Nothing is ever approved automatically (B5).

    python scripts/approve_region.py ru_ua --list                       # table of entries
    python scripts/approve_region.py ru_ua --list --type RG-SLUR
    python scripts/approve_region.py ru_ua --by gmikou                  # one by one: [a]pprove [r]eject [s]kip [q]uit
    python scripts/approve_region.py ru_ua --by gmikou --approve RG-SLUR-001,RG-SLUR-002
    python scripts/approve_region.py ru_ua --by gmikou --approve-all    # bulk, asks for confirmation
    python scripts/approve_region.py ru_ua --by gmikou --reject RG-ACTOR-007
"""

import argparse
import sys
from datetime import date
from pathlib import Path

import yaml

REGIONS = Path(__file__).resolve().parent.parent / "policy" / "regions"


def load(region: str) -> tuple[str, dict, Path]:
    path = REGIONS / f"{region}.yaml"
    text = path.read_text(encoding="utf-8")
    header = "".join(line + "\n" for line in text.splitlines() if line.startswith("#"))
    return header, yaml.safe_load(text), path


def save(header: str, doc: dict, path: Path):
    with open(path, "w", encoding="utf-8") as f:
        f.write(header)
        yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False, width=110)


def show(e: dict) -> str:
    notes = f"\n      note: {e['context_notes']}" if e.get("context_notes") else ""
    return (f"{e['id']:<16} [{e['status']}] ({e['language']}) {e['value']}\n"
            f"      → {e['meaning']}  supports: {', '.join(e['supports'])}{notes}")


def set_status(e: dict, status: str, by: str):
    e["status"] = status
    e["approved_by"] = by if status == "approved" else None
    e["decided"] = f"{date.today().isoformat()} by {by}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("region")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--type")
    ap.add_argument("--status")
    ap.add_argument("--by", help="reviewer name (required to change anything)")
    ap.add_argument("--approve", help="comma-separated IDs")
    ap.add_argument("--reject", help="comma-separated IDs")
    ap.add_argument("--approve-all", action="store_true", help="approve every proposed entry (asks to confirm)")
    args = ap.parse_args()

    header, doc, path = load(args.region)
    entries = [e for e in doc["entries"] if (not args.type or e["type"] == args.type)
               and (not args.status or e["status"] == args.status)]

    if args.list:
        for e in entries:
            print(show(e))
        counts = {}
        for e in doc["entries"]:
            counts[e["status"]] = counts.get(e["status"], 0) + 1
        print(f"\n{len(entries)} shown · profile {args.region} v{doc['version']}: {counts}")
        return

    if not args.by:
        sys.exit("--by <reviewer> is required to approve or reject entries.")

    by_id = {e["id"]: e for e in doc["entries"]}
    changed = 0
    for flag, status in ((args.approve, "approved"), (args.reject, "rejected")):
        for eid in filter(None, (flag or "").split(",")):
            if eid.strip() not in by_id:
                sys.exit(f"Unknown id {eid}")
            set_status(by_id[eid.strip()], status, args.by)
            changed += 1

    if args.approve_all:
        proposed = [e for e in entries if e["status"] == "proposed"]
        if input(f"Approve {len(proposed)} proposed entries as {args.by}? Type 'yes': ").strip() == "yes":
            for e in proposed:
                set_status(e, "approved", args.by)
            changed += len(proposed)

    if not (args.approve or args.reject or args.approve_all):
        for e in (e for e in entries if e["status"] == "proposed"):
            print("\n" + show(e))
            answer = input("[a]pprove [r]eject [s]kip [q]uit: ").strip().lower()
            if answer == "q":
                break
            if answer in ("a", "r"):
                set_status(e, "approved" if answer == "a" else "rejected", args.by)
                changed += 1

    if changed:
        save(header, doc, path)
    print(f"{changed} entries updated in {path.name}.")


if __name__ == "__main__":
    main()
