"""Separate likely checkpoint-development membership from official test membership."""
from collections import Counter
from pathlib import Path
import json, time, zipfile

from official_archive import Remote

a=Path(__file__).resolve().parent
for _ in range(120):
    if (a/"gtsdb-results.json").exists(): break
    time.sleep(2)
d=json.loads((a/"gtsdb-results.json").read_text(encoding="utf8"))
with Remote("FullIJCNN2013.zip") as http, zipfile.ZipFile(http) as z:
    gt=z.read("FullIJCNN2013/gt.txt").decode()
annotated=sorted({int(Path(line.split(";")[0]).stem) for line in gt.splitlines()})
split=int(.8*len(annotated))
training=set(annotated[:split])
validation=set(annotated[split:])
out={}
for group,rows in {
    "published_converter_training": [x for x in d["rows"] if x["frame"] in training],
    "published_converter_validation": [x for x in d["rows"] if x["frame"] in validation],
    "published_converter_excluded_negative": [x for x in d["rows"] if x["frame"] not in training|validation],
}.items():
    c=Counter(images=len(rows))
    for x in rows:
        c["tp"]+=len(x["matches"])
        c["fp"]+=len(x["predictions"])-len(x["matches"])
        c["fn"]+=len(x["references"])-len(x["matches"])
        for p,(r,_) in x["matches"].items():
            c["cnn_correct"]+=x["predictions"][int(p)]["cnn_class_id"]==x["references"][r]["class_id"]
        for version in ("baseline","candidate"):
            for _,_,good in x[version]["played"]:
                c[f"{version}_{'correct' if good else 'incorrect'}"]+=1
    out[group]=dict(counts=c,frames=[x["frame"] for x in rows])
(a/"published-split-overlap.json").write_text(json.dumps(out,indent=2),encoding="utf8")
print({k:v["counts"] for k,v in out.items()})
