"""Make prediction-blind label review panels from the Belgian testing archive."""
from collections import defaultdict
import csv, hashlib,json,os,zipfile
from pathlib import Path
import cv2,numpy as np
HERE=Path(__file__).resolve().parent
BASE=Path(os.environ["TEMP"])/"traffic-step-k"
ARCHIVE=BASE/"belgium-test.zip"
classes=(BASE/"belgium-classes.txt").read_text(encoding="utf8").splitlines()[1:]
def by_group(z,k):
    stem=f"Testing/{k:05}/"
    items=defaultdict(list)
    names=set(z.namelist())
    with z.open(stem+f"GT-{k:05}.csv") as raw:
        for r in csv.DictReader((line.decode() for line in raw),delimiter=";"):
            member=stem+r["Filename"]
            if member in names:
                box=[int(r[f"Roi.{c}"])+(1 if c.endswith("2") else 0) for c in ("X1","Y1","X2","Y2")]
                items[r["Filename"].split("_")[0]].append(dict(member=member,box=box))
    return items
def crop(z,r):
    im=cv2.imdecode(np.frombuffer(z.read(r["member"]),np.uint8),cv2.IMREAD_COLOR)
    x,y,b,c=r["box"]
    return im[y:c,x:b]
def tile(im, label):
    out=np.zeros((125,110,3),np.uint8)
    h,w=im.shape[:2]
    scale=min(100/h,100/w)
    v=cv2.resize(im,(max(1,round(w*scale)),max(1,round(h*scale))))
    out[24:24+v.shape[0],:v.shape[1]]=v
    cv2.putText(out,label,(2,18),0,.48,(0,255,255),1)
    return out
def main():
    with zipfile.ZipFile(ARCHIVE) as z:
        seq=by_group(z,32)
        keys=sorted(seq,key=lambda k:hashlib.sha256(("step-k-safety-v1/"+k).encode()).hexdigest())[:48]
        reps=[(k,max(seq[k],key=lambda r:(r["box"][2]-r["box"][0])*(r["box"][3]-r["box"][1]))) for k in keys]
        panels=[tile(crop(z,row),key) for key,row in reps]
        cv2.imwrite(str(HERE/"belgian-speed-label-review.jpg"),np.vstack([np.hstack(panels[i:i+8]) for i in range(0,48,8)]))
        panels=[]
        for label in [19,21,22,28,31,34,35,37,61]:
            items=by_group(z,label)
            row=max((r for s in items.values() for r in s),key=lambda r:r["box"][2]-r["box"][0])
            panels.append(tile(crop(z,row),f"{label} {classes[label]}"))
        cv2.imwrite(str(HERE/"belgian-class-review.jpg"),np.hstack(panels))
        (HERE/"belgian-speed-sample-ids.json").write_text(json.dumps(keys,indent=2),encoding="utf8")
if __name__=="__main__":main()
