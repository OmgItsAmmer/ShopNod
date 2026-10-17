"""List every i18n key used in the source: `useTranslations('ns')` / `getTranslations('ns')` + `t('key')` calls.
A call resolves to the nearest preceding declaration of that variable, so several components in one file work.
Usage: python scripts/extract_keys.py [--json]"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = [p for d in ("app", "components", "lib") for p in (ROOT / d).rglob("*.ts*") if "node_modules" not in p.parts]
DECL = re.compile(r"(?:const|let)\s+(\w+)\s*=\s*(?:await\s+)?(?:useTranslations|getTranslations)\(\s*'([\w.]+)'\s*\)")
CALL = re.compile(r"(?<![\w.])(\w+)\(\s*(?:'([\w.]+)'|`([^`]+)`)")


def extract() -> set[str]:
    keys: set[str] = set()
    for f in FILES:
        src = f.read_text(encoding="utf8")
        decls = [(m.start(), m.group(1), m.group(2)) for m in DECL.finditer(src)]
        if not decls:
            continue
        names = {d[1] for d in decls}
        for m in CALL.finditer(src):
            var = m.group(1)
            if var not in names:
                continue
            ns = None
            for pos, v, n in decls:
                if v == var and pos < m.start():
                    ns = n
            if ns is None:
                continue
            if m.group(2):
                keys.add(f"{ns}.{m.group(2)}")
            else:
                keys.add(f"{ns}.{m.group(3).split('${')[0]}*")
    return keys


if __name__ == "__main__":
    ks = sorted(extract())
    print(json.dumps(ks, indent=1) if "--json" in sys.argv else "\n".join(ks))
