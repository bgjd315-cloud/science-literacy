"""把自然科題目整理成純文字，供逐題判讀使用（輸出 work/stems-<試卷>.txt）。"""
import json, re
from pathlib import Path
R = Path(__file__).resolve().parents[1]
def clean(t, n):
    t = re.sub(r"\s+", " ", t or "").strip()
    return t[:n]
for subj in ["science", "xuece-sci", "xuece-phy", "xuece-chem", "xuece-bio"]:
    out = []
    for f in sorted((R / "data" / subj).glob("1*.json")):
        d = json.loads(f.read_text("utf-8")); y = int(f.stem); ex = d["json:examData"]
        out.append(f"##### {subj} {y}")
        for g in ex.get("g", []):
            out.append(f"  [組{g.get('a')}-{g.get('b')}] " + clean(g.get("t"), 380))
        if subj == "science":
            ans = d["json:ansData"]
            rows = [(q["n"], ans[i] if i < len(ans) else "", c[0], c[1]) for i, (q, c) in enumerate(zip(ex["q"], d["json:clsData"]))]
        elif subj == "xuece-sci":
            rows = [(q["n"], r[2], r[0], r[1]) for q, r in zip(ex["q"], d["js:Q"])]
        else:
            rows = [(q["lab"], r[4], r[2], r[3]) for q, r in zip(ex["q"], d["js:Q"])]
        for (n, a, c, lab), q in zip(rows, ex["q"]):
            out.append(f"{n}|{a}|{c}|{lab}|" + clean(q.get("t"), 330))
    (R / "work" / f"stems-{subj}.txt").write_text("\n".join(out), "utf-8")
    print(subj, len(out), "lines", sum(len(x) for x in out), "chars")
