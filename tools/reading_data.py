#!/usr/bin/env python3
"""把逐題判讀（reading_cls.py）與 data/ 的題目合成自然素養頁面用的資料。

由 build.py 呼叫：
  build_reading(root) → {"items": [...]}，item =
    [考試, 年度, 題號, 考點, 答案, 能力, 陷阱, 提示, 題目文字, 資料類型, 試卷, 原題連結參數, 科目]
  build_practice(root) → 練習卷用資料（只收選擇題，附試卷圖片裁切範圍）
考試：0 = 會考自然（data/science），1 = 學測自然（xuece-sci），2 = 分科物理、化學、生物（xuece-phy、xuece-chem、xuece-bio）。
科目：P 物理、C 化學、B 生物、E 地球科學、X 跨科。
"""
import json
import re
import sys
from pathlib import Path

TESTS = {"science": 0, "xuece-sci": 1, "xuece-phy": 2, "xuece-chem": 2, "xuece-bio": 2}
ORDER = list(TESTS)
FIXED = {"xuece-phy": "P", "xuece-chem": "C", "xuece-bio": "B"}
PREFIX = {"xuece-phy": "ph", "xuece-chem": "ch", "xuece-bio": "bi"}
NAME = {"xuece-phy": "物理", "xuece-chem": "化學", "xuece-bio": "生物"}
MAXLEN = 240


def _clean(t):
    t = re.sub(r"\s+", " ", t or "").strip()
    return re.sub(r"^\d{1,2}\s*[\.．]\s*", "", t)


def _years(root, subj):
    for f in sorted((root / "data" / subj).glob("1[0-9][0-9].json")):
        yield int(f.stem), json.loads(f.read_text("utf-8"))


def _num(lab):
    m = re.match(r"\d+", str(lab))
    return int(m.group()) if m else -1


def _group(ex, n):
    return next((g for g in ex.get("g", []) if g.get("a") and g["a"] <= n <= g["b"]), None)


def _rows(root):
    """逐題產生 (試卷, 年度, 題目, 題組, 考點, 答案, 原題連結參數, 顯示題號, 科目, 題型, 試卷頁資料)。"""
    for y, d in _years(root, "science"):
        ex, ans = d["json:examData"], d["json:ansData"]
        for i, (q, c) in enumerate(zip(ex["q"], d["json:clsData"])):
            a = ans[i] if i < len(ans) else "非選"
            page = [ex["w"], ex["h"], ex["x0"], ex["xw"], f"science/sci-pages/{y}-"]
            yield "science", y, q, _group(ex, q["n"]), c[1], a, f"{y},{q['n']}", str(q["n"]), c[0], "單選題", page
    for y, d in _years(root, "xuece-sci"):
        ex = d["json:examData"]
        for q, r in zip(ex["q"], d["js:Q"]):
            page = [ex["w"], ex["h"], 56, 486, f"xuece-sci/pages/{y}-"]
            yield "xuece-sci", y, q, _group(ex, q["n"]), r[1], r[2], f"{y},{q['n']}", str(q["n"]), r[0][0], r[4], page
    for subj in ("xuece-phy", "xuece-chem", "xuece-bio"):
        for y, d in _years(root, subj):
            ex = d["json:examData"]
            for q, r in zip(ex["q"], d["js:Q"]):
                page = [ex["w"], ex["h"], 56, 486, f"{subj}/pages/{y}{PREFIX[subj]}-"]
                yield subj, y, q, _group(ex, _num(q["lab"])), r[3], r[4], f"{y},{q['lab']}", q["lab"], FIXED[subj], r[1], page


def build_reading(root):
    root = Path(root)
    sys.path.insert(0, str(root / "tools"))
    from reading_cls import CLS

    rows = list(_rows(root))
    items = []
    for key in ORDER:
        kr = [r for r in rows if r[0] == key]
        for y in sorted({r[1] for r in kr}):
            yr = [r for r in kr if r[1] == y]
            hints = CLS[key][y].strip().split("｜")
            if len(hints) != len(yr):
                raise SystemExit(f"[錯誤] {key} {y}：題數 {len(yr)}、判讀 {len(hints)} 不一致")
            for (t, _, q, g, lab, a, args, shown, sub, kind, _), h in zip(yr, hints):
                abil, src, trap, hint = h.split(" ", 3)
                if a in ("／", "") or "非選" in kind:
                    a = "非選"
                text = _clean(q.get("t")) or (_clean(g["t"]) if g else "")
                no = shown if key in ("science", "xuece-sci") else f"{NAME[key]} {shown}"
                items.append([TESTS[key], y, no, lab, a, abil, trap, hint, text[:MAXLEN], src, t, args, sub])
    return {"items": items}


def _opts(text, ans, multi):
    """由題目文字中的 (A)(B)… 判斷選項個數；找不到時，單選 4 個（會考）或 5 個，多選 5 個。"""
    found = [c for c in "ABCDEFGH" if f"({c})" in (text or "")]
    last = max([*found, *ans, "E" if multi else "D"])
    return "ABCDEFGH"[: "ABCDEFGH".index(last) + 1]


def build_practice(root):
    """練習卷用資料：只收有標準答案的單選題與多選題。

    回傳 {"items": [...]}，item = [考試, 年度, 題號, 答案, 能力, 陷阱, 提示, 考點, 題目裁切, 題組裁切, 選項字元, 資料類型, 頁面資料, 題庫代號, 科目, 是否多選]
    頁面資料 = [寬, 高, x0, xw, 圖片路徑前綴]；裁切 = [頁, 上, 下, 裁切框, 遮罩]。
    """
    root = Path(root)
    reading = {(it[10], it[1], it[11]): it for it in build_reading(root)["items"]}
    items = []

    def norm(sl):
        return [list(s[:3]) + [s[3] if len(s) > 3 else [], s[4] if len(s) > 4 else []] for s in sl]

    for t, y, q, g, lab, a, args, shown, sub, kind, page in _rows(root):
        it = reading[(t, y, args)]
        ans = str(a).strip()
        if not re.fullmatch(r"[A-H]+", ans) or it[6] == "T0":
            continue
        if not q.get("s"):
            continue
        multi = "多選" in kind or len(ans) > 1 or "多選" in it[7]
        gs = norm(g["s"]) if g and g.get("s") else []
        items.append([it[0], y, it[2], ans, it[5], it[6], it[7], lab, norm(q["s"]), gs, _opts(q.get("t"), ans, multi),
                      it[9], page, f"{t}-{args.replace(',', '-')}", sub, 1 if multi else 0])
    return {"items": items}


if __name__ == "__main__":
    from collections import Counter
    R = Path(__file__).resolve().parents[1]
    idx = build_reading(R)["items"]
    print(len(idx), "題", Counter(it[0] for it in idx), Counter(it[12] for it in idx))
    def show(name, a):
        n = len(a)
        f = lambda i: ", ".join(f"{k}{round(v / n * 100)}" for k, v in Counter(x[i] for x in a).most_common())
        print(name, n, "|", f(5), "|", f(9), "|", f(6))
    show("會考", [x for x in idx if x[0] == 0])
    show("學測舊", [x for x in idx if x[0] == 1 and x[1] <= 110])
    show("學測新", [x for x in idx if x[0] == 1 and x[1] >= 111])
    show("分科舊", [x for x in idx if x[0] == 2 and x[1] <= 110])
    show("分科新", [x for x in idx if x[0] == 2 and x[1] >= 111])
    for s in "PCBE":
        show("科" + s, [x for x in idx if x[12] == s])
    p = build_practice(R)["items"]
    print("練習卷", len(p), "題", Counter((it[0], it[15]) for it in p), Counter(it[10] for it in p))
    print("答案異常", [(it[10], it[1], it[2], it[4]) for it in idx if not re.fullmatch(r"[A-H]+|非選", it[4])])
    print("多選但提示未標", sum(1 for it in p if it[15] and "多選" not in it[6]), "提示標多選但答案單一", [(it[13], it[3]) for it in p if "多選" in it[6] and len(it[3]) == 1])
