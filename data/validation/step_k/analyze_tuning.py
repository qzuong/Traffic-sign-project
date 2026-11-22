from collections import Counter, defaultdict
import hashlib,json
from pathlib import Path
import cv2,numpy as np
from crop_evidence import HERE,DATA
from policies import POLICIES,block

def read(path):return json.loads(path.read_text(encoding="utf-8-sig"))
def split_counts(rows,policy):
    n=Counter()
    by_true=defaultdict(Counter)
    by_pred=defaultdict(Counter)
    matrix=defaultdict(Counter)
    eligible_wrong=defaultdict(Counter)
    for r in rows:
        correct=r["true"]==r["pred"]
        word="correct" if correct else "incorrect"
        why=block(r,policy)
        key=word+("_eligible" if why is None else "_withheld")
        n[key]+=1
        for group,idx in [(by_true,r["true"]),(by_pred,r["pred"])]:
            group[idx][key]+=1
            if why:group[idx][word+"_veto_"+why]+=1
        matrix[r["true"]][r["pred"]]+=1
        if not correct and why is None:eligible_wrong[r["true"]][r["pred"]]+=1
    return dict(total=n,by_true=by_true,by_predicted=by_pred,
                confusion_matrix=matrix,eligible_wrong_confusion_matrix=eligible_wrong)
def summarize_tuning():
    rows=read(HERE/"gtsrb-tuning-features.json")
    audit={p:split_counts(rows,p) for p in POLICIES}
    blocked=[r for r in rows if r["true"]==r["pred"] and r["baseline"]]
    wrong=[r for r in rows if r["true"]!=r["pred"] and r["baseline"] is None]
    kept=[r for r in rows if r["true"]==r["pred"] and r["baseline"] is None]
    keys=("top1","top2","margin","bright","neutral","dark","v_median","red","blue","sharpness","width","height")
    def quantiles(sample):
        return {k:[float(x) for x in np.quantile([r[k] for r in sample],[.1,.5,.9])] for k in keys}
    audit["quantiles_p10_p50_p90"]={"correct_kept":quantiles(kept),"wrong_kept":quantiles(wrong)}
    for why in sorted({r["baseline"] for r in blocked}):
        group=[r for r in blocked if r["baseline"]==why]
        audit["quantiles_p10_p50_p90"][why]=quantiles(group)
    audit["eligible_wrong_rows"]=wrong
    (HERE/"tuning-audit.json").write_text(json.dumps(audit,indent=2),encoding="utf8")
    for k in POLICIES:print(k,audit[k]["total"])
    wrong_pairs=Counter((r["true"],r["pred"]) for r in wrong).most_common(16)
    tiles=[]
    for (actual,pred),count in wrong_pairs:
        group=[r for r in wrong if (r["true"],r["pred"])==(actual,pred)]
        r=sorted(group,key=lambda r:r["top1"])[len(group)//2]
        image=cv2.imread(str(DATA/r["path"]))
        image=cv2.resize(image,(172,132))
        image=cv2.copyMakeBorder(image,43,0,0,0,0)
        cv2.putText(image,f"{actual} -> {pred}, n={count}",(4,16),0,.53,(0,255,255),1)
        cv2.putText(image,f'{r["path"].split("/")[-1]} {r["top1"]:.3f}',(4,36),0,.51,(0,255,255),1)
        tiles.append(image)
    cv2.imwrite(str(HERE/"eligible-wrong-contact.jpg"),np.vstack([np.hstack(tiles[i:i+4]) for i in range(0,len(tiles),4)]))
    lock=dict(design=["Step H and Step I real-video error cases","Step J already inspected data"],
        tuning="All local GTSRB Test ROIs, after Step J exposure",
        heldout=["BelgiumTSC Testing labeled before model inference","New official GTSDB scenes distinct from Step J by content CRC"],
        policy_sha256=hashlib.sha256((HERE/"policies.py").read_bytes()).hexdigest(),
        label_map_sha256=hashlib.sha256((HERE/"belgium-label-map.json").read_bytes()).hexdigest(),
        candidates=list(POLICIES),production_revision="f2f61cb")
    (HERE/"policy-lock.json").write_text(json.dumps(lock,indent=2),encoding="utf8")
if __name__=="__main__":summarize_tuning()
