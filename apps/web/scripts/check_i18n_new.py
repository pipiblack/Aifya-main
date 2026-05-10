"""Check missing i18n keys in NEW (this-session) areas only."""
import json
import os
import re
import sys

en = json.load(open("src/messages/en.json", encoding="utf-8"))
sw = json.load(open("src/messages/sw.json", encoding="utf-8"))


def get(d, key):
    for k in key.split("."):
        if not isinstance(d, dict):
            return None
        d = d.get(k)
        if d is None:
            return None
    return d


missing_en = {}
missing_sw = {}
NEW_PREFIXES = (
    "finance.",
    "payroll.",
    "employees.",
    "leave.",
    "performance.",
    "tour.",
    "helpBot.",
    "patients.help.",
    "help.",
)

for root, _dirs, files in os.walk("src"):
    for f in files:
        if not f.endswith((".tsx", ".ts")):
            continue
        path = os.path.join(root, f)
        try:
            text = open(path, encoding="utf-8").read()
        except OSError:
            continue
        ns_matches = re.findall(r"useTranslations\([\"\']([\w]+)[\"\']\)", text)
        if not ns_matches:
            continue
        ns = ns_matches[0]
        for key in re.findall(r"t\([\"\']([a-zA-Z][\w.]+)[\"\']\)", text):
            if not re.match(r"^[a-zA-Z_][\w]*(\.[a-zA-Z_][\w]*)*$", key):
                continue
            full = f"{ns}.{key}" if not key.startswith(ns + ".") else key
            if not any(full.startswith(p) for p in NEW_PREFIXES):
                continue
            if get(en, full) is None:
                missing_en[full] = path
            if get(sw, full) is None:
                missing_sw[full] = path

print(f"MISSING EN in NEW areas ({len(missing_en)}):")
for k, p in sorted(missing_en.items()):
    print(f"  {k}  <- {p}")
print(f"MISSING SW in NEW areas ({len(missing_sw)}):")
for k, p in sorted(missing_sw.items()):
    print(f"  {k}  <- {p}")
