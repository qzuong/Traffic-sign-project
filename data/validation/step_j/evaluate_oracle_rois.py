"""Independent-of-Step-I whole test-split classification on labeled ROIs."""
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path
import time

import cv2
import numpy as np
import tensorflow as tf

from src.traffic_sign_demo.speech_evidence import speech_veto
from src.traffic_sign_demo.vision import preprocess_crop

DATA = Path(r"D:\CODE\Traffic_sign_classification\Data")
HERE = Path(__file__).resolve().parent

def main():
    tf.config.threading.set_intra_op_parallelism_threads(2)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    model=tf.keras.models.load_model("models/model.h5",compile=False)
    with (DATA/"Test.csv").open(encoding="utf-8-sig",newline="") as f:
        manifest=list(csv.DictReader(f))
    results=[]
    started=time.monotonic()
    for offset in range(0,len(manifest),256):
        batch=[]
        rows=manifest[offset:offset+256]
        for r in rows:
            im=cv2.imread(str(DATA/r["Path"]))
            assert im is not None and im.shape[:2]==(int(r["Height"]),int(r["Width"]))
            x,y,w,h=[int(r[f"Roi.{j}"]) for j in ("X1","Y1","X2","Y2")]
            batch.append(preprocess_crop(im[y:h+1,x:w+1])[0])
        matrix=np.stack(batch)
        labels=np.argmax(model(matrix,training=False).numpy(),axis=1)
        for row,tensor,label in zip(rows,matrix,labels):
            label=int(label)
            results.append([row["Path"],int(row["ClassId"]),label,speech_veto(tensor,label)])
    summary=defaultdict(lambda:dict(n=0,correct=0,correct_withheld=0,incorrect_withheld=0))
    for _,truth,pred,veto in results:
        item=summary[truth]
        item["n"]+=1
        item["correct"]+=truth==pred
        if veto is not None:
            item["correct_withheld" if truth==pred else "incorrect_withheld"]+=1
    output=dict(csv_sha256=hashlib.sha256((DATA/"Test.csv").read_bytes()).hexdigest(),
                elapsed_seconds=time.monotonic()-started,summary=summary,rows=results)
    (HERE/"gtsrb-roi-results.json").write_text(json.dumps(output,indent=2),encoding="utf8")
    print({k:sum(r[k] for r in summary.values()) for k in next(iter(summary.values()))},flush=True)
if __name__=="__main__":
    main()
