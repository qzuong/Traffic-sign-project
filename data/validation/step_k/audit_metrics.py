"""Export per-class policy coverage and verify exact decoded cross-dataset overlap."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv,hashlib,json,os,time
from pathlib import Path

import cv2,numpy as np
from crop_evidence import HERE,DATA
from analyze_tuning import read,split_counts
from policies import POLICIES
from src.traffic_sign_demo.class_mapping import load_class_mapping

def metric_table():
    names=load_class_mapping("models/model.py")
    audit=read(HERE/"tuning-audit.json")
    be=read(HERE/"belgium-holdout-results.json")
    de=read(HERE/"gtsdb-holdout-results.json")
    datasets={"gtsrb_tuning":audit,"belgium_holdout":be["crop_level"],"gtsdb_holdout":de["crop_level"]}
    columns=("correct_eligible","correct_withheld","incorrect_eligible","incorrect_withheld")
    with (HERE/"per-class-coverage.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f)
        w.writerow(["dataset","policy","true_class_id","true_class","crops",*columns,
                     "correct_eligible_pct_of_class","wrong_eligible_pct_of_class"])
        for name,rows in datasets.items():
            for policy in POLICIES:
                for label,row in sorted(rows[policy]["by_true"].items(),key=lambda pair:int(pair[0])):
                    class_id=int(label);values=[row.get(c,0) for c in columns];denom=sum(values)
                    w.writerow([name,policy,class_id,names.get(class_id,"unmatched candidate"),denom,*values,
                                round(values[0]*100/denom,2),round(values[2]*100/denom,2)])
    base=read(HERE/"dataset-integrity.json")
    leaked={x for item in base["exact_cross_split_source_matches"] for x in item["test"]}
    rows=[r for r in read(HERE/"gtsrb-tuning-features.json") if r["path"] not in leaked]
    verified={}
    for p in POLICIES:verified[p]=split_counts(rows,p)["total"]
    (HERE/"tuning-with-exact-overlap-excluded.json").write_text(json.dumps(dict(
        excluded_test_paths=sorted(leaked),rows=len(rows),counts=verified),indent=2),encoding="utf8")
    print("tuning excluding duplicate files",verified)

def check_cross_dataset():
    held=read(HERE/"belgium-holdout-results.json")["rows"]
    keys={r["image_sha256"] for r in held}
    with (DATA/"Test.csv").open(encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))
    def digest(r):
        im=cv2.imread(str(DATA/r["Path"]))
        x,y,w,h=[int(r[f"Roi.{j}"]) for j in ("X1","Y1","X2","Y2")]
        sha=hashlib.sha256(im[y:h+1,x:w+1].tobytes()).hexdigest()
        return r["Path"],sha
    with ThreadPoolExecutor(max_workers=4) as pool:
        hits=[(name,sha) for name,sha in pool.map(digest,rows) if sha in keys]
    (HERE/"belgium-gtsrb-overlap.json").write_text(json.dumps(dict(
         belgian_crops=len(held),gtsrb_crops=len(rows),exact_decoded_crop_hits=hits),indent=2),encoding="utf8")
    print("exact Belgian-to-GTSRB decoded ROI hits",len(hits))

if __name__=="__main__":
    metric_table()
    check_cross_dataset()
