import json, os, re, psycopg2

conn = psycopg2.connect(dbname="oorep", user="oorep_user", password="oorep", host="localhost")
cur = conn.cursor()

cur.execute("""
  SELECT table_name, column_name
  FROM information_schema.columns
  WHERE table_schema = 'public'
  ORDER BY table_name, ordinal_position
""")
schema = {}
for t, c in cur.fetchall():
  schema.setdefault(t, []).append(c)
print("Detected tables:", json.dumps(schema, indent=2))

os.makedirs("data", exist_ok=True)

rem_cols = schema.get("remedy", [])
cur.execute("SELECT * FROM remedy")
remedies = {}
for row in cur.fetchall():
  d = dict(zip(rem_cols, row))
  rid = d.get("id")
  if rid is not None:
    remedies[rid] = {
      "a": d.get("nameabbrev") or d.get("abbrev") or "",
      "n": d.get("namelong") or d.get("name") or ""
    }
with open("data/remedies.json", "w") as f:
  json.dump(remedies, f, separators=(",", ":"))

info_table = "info" if "info" in schema else "repertory"
info_cols = schema.get(info_table, [])
cur.execute(f"SELECT * FROM {info_table}")
reps = []
for row in cur.fetchall():
  d = dict(zip(info_cols, row))
  ab = d.get("abbrev")
  if ab:
    reps.append({
      "abbrev": ab,
      "title": d.get("title") or d.get("displaytitle") or ab,
      "author": d.get("authorlastname") or d.get("author") or "",
      "lang": d.get("language") or "en"
    })

rub_cols = schema.get("rubric", [])
cur.execute("SELECT abbrev, rubricid, remedyid, weight FROM rubricremedy")
rr_map = {}
for ab, ruid, remid, w in cur.fetchall():
  rr_map.setdefault((ab, ruid), []).append([remid, w])

manifest = []
for rep in reps:
  ab = rep["abbrev"]
  cur.execute("SELECT * FROM rubric WHERE abbrev = %s", (ab,))
  rows = cur.fetchall()
  if not rows:
    continue
  items = []
  for row in rows:
    d = dict(zip(rub_cols, row))
    rid = d.get("id")
    pid = d.get("mother") if "mother" in d else d.get("parentid")
    path = d.get("fullpath") or d.get("path") or ""
    txt = d.get("textt") or d.get("text") or ""
    rems = rr_map.get((ab, rid), [])
    items.append([rid, pid, path, txt, rems])
  safe_ab = re.sub(r"[^a-zA-Z0-9_-]", "_", ab)
  fname = f"rep_{safe_ab}.json"
  with open(f"data/{fname}", "w") as f:
    json.dump(items, f, separators=(",", ":"))
  rep["file"] = fname
  rep["count"] = len(items)
  manifest.append(rep)
  print(f"Exported {ab}: {len(items)} rubrics")

with open("data/manifest.json", "w") as f:
  json.dump(manifest, f, separators=(",", ":"))
