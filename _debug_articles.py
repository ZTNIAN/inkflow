import json, os
files = sorted(
    [f for f in os.listdir("data/articles") if f.endswith(".json")],
    key=lambda f: os.path.getmtime(f"data/articles/{f}"),
    reverse=True,
)
for f in files:
    data = json.load(open(f"data/articles/{f}", encoding="utf-8"))
    clen = len(data.get("content", ""))
    o = data.get("outline")
    olen = len(o.get("sections", [])) if o else 0
    hlen = len(data.get("html", ""))
    topic = data.get("topic", "")
    print(f"{f}: topic={topic[:20]} content={clen} outline_sections={olen} html={hlen}")
