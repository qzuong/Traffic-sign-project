"""Audit exact source-byte overlap and dataset boundaries."""
import csv,hashlib,json
from collections import defaultdict
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from crop_evidence import DATA,HERE

def split(name):
    path=DATA/f"{name}.csv"
    rows=list(csv.DictReader(path.open(encoding="utf-8-sig",newline="")))
    def digest(r):
        file=DATA/r["Path"]
        return hashlib.sha256(file.read_bytes()).hexdigest(),r
    groups=defaultdict(list)
    with ThreadPoolExecutor(max_workers=12) as pool:
        for key,r in pool.map(digest,rows): groups[key].append(r["Path"])
    return dict(csv_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),rows=len(rows),groups=groups)
a,b=(split(name) for name in ("Train","Test"))
matches=a["groups"].keys() & b["groups"].keys()
out=dict(train_rows=a["rows"],test_rows=b["rows"],train_csv_sha256=a["csv_sha256"],
 test_csv_sha256=b["csv_sha256"],exact_cross_split_source_matches=[
 {"sha256":k,"train":a["groups"][k],"test":b["groups"][k]} for k in sorted(matches)],
 test_exact_duplicate_groups=sum(len(v)>1 for v in b["groups"].values()),
 validation_use="GTSRB Test already examined in Step J; tuning/diagnostics only in Step K",
 limitations="Exact SHA-256 excludes byte-identical files only. Near-duplicates and historical checkpoint selection cannot be ruled out.")
(HERE/"dataset-integrity.json").write_text(json.dumps(out,indent=2),encoding="utf8")
print({k:v for k,v in out.items() if k!="exact_cross_split_source_matches"},'ID-overlap',len(matches))
