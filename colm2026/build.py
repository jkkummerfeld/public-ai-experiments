"""Build the COLM 2026 Paper Scout page.

Steps (each cached in ./cache):
  1. Scrape the accepted-papers list and the schedule from colm.eventhosts.cc
  2. Look up each paper's abstract / keywords / TL;DR on OpenReview
  3. Embed every paper with the static model2vec model minishlab/potion-base-8M
  4. Write index.html plus model/ (vocab + int8 embedding table, used in the
     browser to embed the reader's interest lines with the same model)

Usage: pip install model2vec numpy && python build.py
"""
import base64, html, json, os, re, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
PAPERS_URL = "https://colm.eventhosts.cc/Conferences/2026/AcceptedPapers"
CAL_URL = "https://colm.eventhosts.cc/virtual/2026/calendar"
OR_GROUP = "colmweb.org/COLM/2026/Conference"
MODEL = "minishlab/potion-base-8M"

norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
clean = lambda x: html.unescape(re.sub(r"<[^>]+>", "", re.sub(r"\s+", " ", x))).strip()


def fetch(url, name):
    path = os.path.join(CACHE, name)
    if not os.path.exists(path):
        os.makedirs(CACHE, exist_ok=True)
        with urllib.request.urlopen(url, timeout=60) as r, open(path, "wb") as f:
            f.write(r.read())
    return open(path, encoding="utf-8").read()


def parse_papers(s):
    out = []
    for r in re.findall(r"<tr[^>]*>\s*<td>(.*?)</tr>", s, re.S):
        t = re.search(r"<strong>(.*?)</strong>", r, re.S)
        if not t:
            continue
        a = re.search(r'class="indented">\s*<i>(.*?)</i>', r, re.S)
        link = re.search(r'href="([^"]+)"[^>]*class="elc-project-link"', r, re.S)
        where = [clean(p) for p in re.findall(r'class="elc-where-part">(.*?)</span>', r, re.S)]
        g = lambda pre: next((x[len(pre):].strip(" .") for x in where if x.startswith(pre)), "")
        out.append(dict(
            t=clean(t.group(1)),
            a=[x.strip() for x in clean(a.group(1)).split("⋅")] if a else [],
            l=link.group(1) if link else "",
            s=int(re.search(r"\d+", g("in Poster Session")).group()),
            r=g("In Room:"),
            n=int(g("Poster Location: #") or 0),
            time=g("at").split(" PDT")[0],
        ))
    return out


def parse_schedule(s):
    t = re.sub(r"<(script|style).*?</\1>", " ", s, flags=re.S)
    t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "|", t)))
    day = sess = None
    oral, pday = {}, {}
    for x in (x.strip() for x in re.sub(r"(\| ?)+", "|", t).split("|")):
        if re.match(r"(MON|TUE|WED|THU|FRI|SAT|SUN) \d+ \w+$", x):
            day = x
        m = re.match(r"(Oral|Poster) Session (\d+)$", x)
        if m:
            sess = m.groups()
            if sess[0] == "Poster":
                pday[sess[1]] = day
        m = re.match(r"\[(\d+:\d+)\] (.+)$", x)
        if m and sess and sess[0] == "Oral":
            oral[norm(m.group(2))] = [day, m.group(1), "Oral Session " + sess[1]]
    return pday, oral


def openreview(p):
    q = urllib.parse.urlencode(dict(term=p["t"][:200], group=OR_GROUP, limit=10, type="terms", content="title"))
    for i in range(6):
        try:
            with urllib.request.urlopen("https://api2.openreview.net/notes/search?" + q, timeout=30) as r:
                d = json.load(r)
            for n in d["notes"]:
                c = n["content"]
                if n["id"] == n.get("forum") and "abstract" in c and norm(c["title"]["value"]) == norm(p["t"]):
                    v = lambda k: c.get(k, {}).get("value", "")
                    return dict(id=n["id"], ab=v("abstract"), k=v("keywords") or [], tl=v("TLDR"))
            return None
        except Exception:
            time.sleep(2 ** i)
    return None


def main():
    papers = parse_papers(fetch(PAPERS_URL, "accepted.html"))
    pday, oral = parse_schedule(fetch(CAL_URL, "calendar.html"))

    or_path = os.path.join(CACHE, "openreview.json")
    meta = json.load(open(or_path)) if os.path.exists(or_path) else {}
    todo = [p for p in papers if norm(p["t"]) not in meta]
    with ThreadPoolExecutor(4) as ex:
        for p, r in zip(todo, ex.map(openreview, todo)):
            if r:
                meta[norm(p["t"])] = r
    json.dump(meta, open(or_path, "w"))
    missing = [p["t"] for p in papers if norm(p["t"]) not in meta]
    if missing:
        raise SystemExit(f"{len(missing)} papers not found on OpenReview, re-run: {missing[:3]}")

    sessions = {}
    for p in papers:
        p.update(meta[norm(p["t"])])
        p["o"] = oral.get(norm(p["t"]))
        sessions[str(p["s"])] = dict(day=pday[str(p["s"])], time=p.pop("time"))

    # Embeddings
    from model2vec import StaticModel
    model = StaticModel.from_pretrained(MODEL)
    texts = [". ".join([p["t"], ", ".join(p["k"]), p["tl"], p["ab"]]) for p in papers]
    vecs = model.encode(texts, max_length=None)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    q = np.clip(np.round(vecs * 127 / np.abs(vecs).max(axis=1, keepdims=True)), -127, 127).astype(np.int8)
    emb_b64 = base64.b64encode(q.tobytes()).decode()

    os.makedirs(os.path.join(HERE, "model"), exist_ok=True)
    vocab = sorted(model.tokenizer.get_vocab().items(), key=lambda kv: kv[1])
    assert [i for _, i in vocab] == list(range(len(vocab)))
    open(os.path.join(HERE, "model", "vocab.txt"), "w", encoding="utf-8").write("\n".join(t for t, _ in vocab))
    E = model.embedding.astype(np.float32)
    scale = np.abs(E).max(axis=1) / 127
    scale[scale == 0] = 1
    Eq = np.clip(np.round(E / scale[:, None]), -127, 127).astype(np.int8)
    # header (rows, dim as uint32) + per-row float32 scales + int8 table, base64 so it can be served as text
    raw = np.array([E.shape[0], E.shape[1]], dtype=np.uint32).tobytes() + scale.astype(np.float32).tobytes() + Eq.tobytes()
    open(os.path.join(HERE, "model", "potion-base-8M.b64.txt"), "w").write(base64.b64encode(raw).decode())
    # reference query embeddings, used by test_tokenizer.js to check the JS port
    probe = [p["t"] for p in papers] + [p["ab"] for p in papers] + ["Text-to-SQL for dialogue agents", "naïve café résumé", "RLHF/DPO: reward-model over-optimisation?"]
    json.dump(dict(texts=probe, ids=[[i for i in model.tokenizer.encode(t, add_special_tokens=False).ids if i != model.unk_token_id] for t in probe]),
              open(os.path.join(CACHE, "tokenizer_probe.json"), "w"))

    data = dict(sessions=sessions, dim=int(vecs.shape[1]), emb=emb_b64,
                papers=[{k: p[k] for k in ["id", "t", "a", "k", "tl", "ab", "s", "r", "n", "l", "o"]} for p in papers])
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    page = open(os.path.join(HERE, "template.html"), encoding="utf-8").read().replace("__DATA__", blob)
    open(os.path.join(HERE, "index.html"), "w", encoding="utf-8").write(page)
    print(f"{len(papers)} papers, {sum(1 for p in papers if p['o'])} orals, index.html {len(page)/1e6:.1f} MB")


if __name__ == "__main__":
    main()
