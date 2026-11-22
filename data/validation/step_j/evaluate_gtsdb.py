"""Evaluate production detection and matched speech policies on labeled full scenes."""
from collections import Counter, defaultdict
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import statistics
import time
import wave

import cv2

from compare_speech import replay
from sample_gtsdb import CACHE
from scripts.benchmark_detectors import iou
from src.traffic_sign_demo.inference_service import InferenceService
from src.traffic_sign_demo.tracked_voice_alerts import TrackedVoiceAlerts
from src.traffic_sign_demo.vision import DisplayFrame,clip_bbox
from src.traffic_sign_demo.voice_alerts import _clip_timing

HERE=Path(__file__).resolve().parent
def matches(predictions, refs):
    pairs=sorted(((iou(pred.bbox,ref["box"]),p,t)
                  for p,pred in enumerate(predictions) for t,ref in enumerate(refs)),reverse=True)
    taken=set()
    matched={}
    for overlap,p,t in pairs:
        if overlap<.5:break
        if p not in matched and t not in taken:
            taken.add(t)
            matched[p]=(t,overlap)
    return matched

def evaluate():
    manifest=json.loads((HERE/"gtsdb-sample.json").read_text(encoding="utf8"))
    service=InferenceService(image_size=640,confidence=.25,preload_workers=True,detector="gtsdb")
    timings={}
    for label in range(43):
        with wave.open(f"assets/voice_google/{label:02}.wav","rb") as clip:
            timings[label]=_clip_timing(clip,check_tail=True)
    baseline=replay.baseline_class()
    rows=[]; total=Counter(); labels=defaultdict(Counter); ious=[]; incorrect_by_class=defaultdict(Counter)
    try:
        for row in manifest["rows"]:
            n=row["frame"]; src=CACHE/f"{n:05}.ppm"
            assert hashlib.sha256(src.read_bytes()).hexdigest()==row["image_sha256"]
            im=cv2.imread(str(src)); h,w=im.shape[:2]
            refs=row["references"]
            total["negative_frames"]+=not refs
            service.submit(im,n,n/30*1000)
            deadline=time.monotonic()+125
            while (result:=service.poll_result()) is None:
                if time.monotonic()>deadline or service.status.startswith("AI Error:"): raise RuntimeError(service.status)
                time.sleep(.01)
            assert result.frame_id==n and service.diagnostics["last_yolo_detection_count"]==len(result.detections)
            predictions=result.detections
            linked=matches(predictions,refs)
            total["tp"]+=len(linked); total["fp"]+=len(predictions)-len(linked); total["fn"]+=len(refs)-len(linked)
            if not refs:total["fp_on_negative"]+=len(predictions)
            for ref in refs:labels[ref["class_id"]]["annotations"]+=1
            for p,(t,overlap) in linked.items():
                label=refs[t]["class_id"]
                total["cnn_correct"]+=predictions[p].cnn_class_id==label
                labels[label]["localized"]+=1
                labels[label]["cnn_correct"]+=predictions[p].cnn_class_id==label
                ious.append(overlap)
            dets=tuple(replace(d,valid_yolo_at=.01,valid_cnn_at=.1) for d in predictions)
            frames=[(at,DisplayFrame(n,i,at*1000,w,h,im),dets if i<3 else ())
                    for i,at in enumerate((0,.2,.4,.8,1.2,1.6))]
            checked_boxes=[clip_bbox(d.bbox,w,h) for d in dets[:32]]
            outputs={}
            for key,cls in (("baseline",baseline),("candidate",TrackedVoiceAlerts)):
                track_boxes={}
                class Capture(cls):
                    def observe(self, frame, dets):
                        state=super().observe(frame,dets)
                        track_boxes.update((tid,box) for tid,box,_ in state)
                        return state
                def grade(tid,label):
                    p=checked_boxes.index(track_boxes[tid])
                    expected=refs[linked[p][0]]["class_id"] if p in linked else None
                    return label==expected
                test=replay.simulate(Capture,frames,timings)
                played=[(tid,label,grade(tid,label)) for tid,label in test["stats"]["played_tracks"]]
                for _,label,good in played:
                    total[key+("_correct" if good else "_incorrect")]+=1
                    if not good: incorrect_by_class[key][label]+=1
                suppressed=[dict(e,would_be_correct=grade(e["track_id"],e["class_id"]))
                            for e in test["trace"] if e["event"]=="speech_suppressed"]
                for e in suppressed:
                    total["veto_of_correct" if e["would_be_correct"] else "veto_of_incorrect"]+=1
                    total["veto_"+e["reason"]]+=1
                    labels[e["class_id"]]["correct_veto" if e["would_be_correct"] else "incorrect_veto"]+=1
                outputs[key]=dict(played=played,suppressed=suppressed)
            b=set(outputs["baseline"]["played"]);c=set(outputs["candidate"]["played"])
            for _,_,good in b-c:total["removed_correct" if good else "removed_incorrect"]+=1
            for tid,label,good in c-b:total["added_correct" if good else "added_incorrect"]+=1
            rows.append(dict(frame=n,references=refs,predictions=[asdict(x) for x in predictions],matches=linked,**outputs))
            if len(rows)%10==0: print("scenes",len(rows),flush=True)
    finally:service.close()
    summary=dict(n=len(rows),counts=total,per_class=labels,incorrect_by_class=incorrect_by_class,
        iou_mean=statistics.mean(ious) if ious else None,iou_median=statistics.median(ious) if ious else None,
        controlled_speech_exposure="three identical observations at 0, 200 and 400ms per isolated road scene, virtual audio clock")
    (HERE/"gtsdb-results.json").write_text(json.dumps(dict(summary=summary,rows=rows),indent=2),encoding="utf8")
    print(summary,flush=True)

if __name__=="__main__":evaluate()

