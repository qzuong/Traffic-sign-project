"""Crop evidence and probabilities for Step K; uses the production preprocess and veto."""
import csv
import json
from pathlib import Path

import cv2
import numpy as np

from src.traffic_sign_demo.speech_evidence import _CENTRE, _OUTER, speech_veto
from src.traffic_sign_demo.vision import preprocess_crop

HERE=Path(__file__).resolve().parent
DATA=Path(r"D:\CODE\Traffic_sign_classification\Data")
Y,X=np.ogrid[:30,:30]
R=np.hypot(Y-14.5,X-14.5)
angle=(np.arctan2(Y-14.5,X-14.5)+np.pi)/(2*np.pi)
SECTORS=[(_OUTER & (angle>=i/8) & (angle<(i+1)/8)) for i in range(8)]
OUTSIDE=R>15
def features(tensor):
    rgb=np.rint(tensor*255).astype(np.uint8)
    h,s,v=cv2.split(cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV))
    red=((h<=11)|(h>=164))&(s>=75)&(v>=60)
    blue=(h>=89)&(h<=132)&(s>=65)&(v>=45)
    centre=v[_CENTRE]
    red_sector=[float(red[x].mean()) for x in SECTORS]
    return dict(bright=float(((s<=75)&(v>=150))[_CENTRE].mean()),
        neutral=float((s[_CENTRE]<=75).mean()), dark=float((centre<115).mean()),
        v_median=float(np.median(centre)),red=float(red[_OUTER].mean()),
        red_sectors=sum(x>=.10 for x in red_sector),
        relative_brightness=float(np.median(centre)-np.median(v[red & _OUTER])) if red[_OUTER].any() else 0.,
        blue=float(blue[_CENTRE].mean()),
        sharpness=float(cv2.Laplacian(cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY),cv2.CV_64F).var()))

def row_features(crop,scores):
    order=np.argsort(scores)[-2:][::-1]
    pred,runner=map(int,order)
    tensor=preprocess_crop(crop)[0]
    h,w=crop.shape[:2]
    return dict(pred=pred,runner_up=runner,top1=float(scores[pred]),top2=float(scores[runner]),
        margin=float(scores[pred]-scores[runner]),baseline=speech_veto(tensor,pred),width=w,height=h,
        **features(tensor))

def load_model():
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(2)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    return tf.keras.models.load_model("models/model.h5",compile=False)

def extract():
    model=load_model()
    with (DATA/"Test.csv").open(encoding="utf-8-sig",newline="") as f:
        manifest=list(csv.DictReader(f))
    original=json.loads((HERE.parent/"step_j/gtsrb-roi-results.json").read_text(encoding="utf8"))["rows"]
    output=[]
    for offset in range(0,len(manifest),256):
        batch=manifest[offset:offset+256]
        crops=[]
        for r in batch:
            img=cv2.imread(str(DATA/r["Path"]))
            x,y,w,h=[int(r[f"Roi.{j}"]) for j in ("X1","Y1","X2","Y2")]
            crops.append(img[y:h+1,x:w+1])
        matrix=np.concatenate([preprocess_crop(c) for c in crops])
        scores=model(matrix,training=False).numpy()
        for i,(r,c,p) in enumerate(zip(batch,crops,scores)):
            row=dict(path=r["Path"],true=int(r["ClassId"]),**row_features(c,p))
            assert [row[k] for k in ("path","true","pred","baseline")]==original[offset+i]
            output.append(row)
        if offset%2048==0:print(offset,flush=True)
    (HERE/"gtsrb-tuning-features.json").write_text(json.dumps(output,separators=(",",":")),encoding="utf8")
    print(len(output),flush=True)

if __name__=="__main__":extract()
