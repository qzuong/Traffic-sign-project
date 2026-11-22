"""Compare unmodified Step H and Step I voice schedulers on paired observations."""
from collections import Counter
from dataclasses import replace
from pathlib import Path
import importlib.util
import json
import wave

import cv2

from src.traffic_sign_demo.alert_tracking import AlertTracks
from src.traffic_sign_demo.desktop_ui import DesktopVideoPlayer
from src.traffic_sign_demo.tracked_voice_alerts import TrackedVoiceAlerts
from src.traffic_sign_demo.vision import ClassifiedDetection, DisplayFrame, clip_bbox
from src.traffic_sign_demo.voice_alerts import _clip_timing

from evaluate_gtsrb import DATA, load_baseline_tracker
from scripts.benchmark_detectors import iou

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("step_i_replay",HERE.parent/"step_i/replay_alerts.py")
replay=importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)

def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def verdict(row, build, track_id, label):
    alert=next(x for x in row[build] if x["track_id"]==track_id)
    matched=row["matched_prediction"]
    if matched is None: return "incorrect"
    ref_det=row["predictions"][matched]["bbox"]
    image=row["image"]
    h,w=image.shape[:2]
    if list(clip_bbox(ref_det,w,h))!=alert["box"]: return "incorrect"
    return "correct" if label==row["actual_class"] else "incorrect"

def evaluate_stills():
    data=read(HERE/"gtsrb-results.json")
    baseline=replay.baseline_class()
    timings={}
    for label in range(43):
        with wave.open(f"assets/voice_google/{label:02}.wav","rb") as clip:
            timings[label]=_clip_timing(clip,check_tail=True)
    summary=Counter()
    by_class={}
    rows=[]
    for n,row in enumerate(data["rows"]):
        actual=row["actual_class"]
        by_class.setdefault(actual,Counter())
        per=by_class[actual]
        summary["images"]+=1
        matched=row["matched_prediction"]
        per["images"]+=1
        summary["fp"]+=len(row["predictions"])-(matched is not None)
        if matched is not None:
            summary["tp"]+=1
            raw=row["predictions"][matched]["cnn_class_id"]
            per["localized"]+=1
            per["cnn_correct"]+=raw==actual
            summary["cnn_correct"]+=raw==actual
        else: summary["fn"]+=1
        img=cv2.imread(str(DATA/row["path"]))
        h,w=img.shape[:2]
        row["image"]=img
        detections=tuple(replace(ClassifiedDetection(**r),valid_yolo_at=.01,valid_cnn_at=.10) for r in row["predictions"])
        frames=[(at,DisplayFrame(n,i,at*1000,w,h,img),detections if i<3 else ())
                for i,at in enumerate((0,.2,.4,.8,1.2,1.6))]
        results={}
        for build,cls in (("baseline",baseline),("candidate",TrackedVoiceAlerts)):
            result=replay.simulate(cls,frames,timings)
            results[build]=[dict(track_id=tid,label=label,verdict=verdict(row,build,tid,label))
                            for tid,label in result["stats"]["played_tracks"]]
            for e in results[build]:
                summary[f"{build}_{e['verdict']}"]+=1
                per[f"{build}_{e['verdict']}"]+=1
            reasons=[]
            for e in result["trace"]:
                if e["event"]=="speech_suppressed":
                    check=verdict(row,build,e["track_id"],e["class_id"])
                    reasons.append({**e,"verdict_if_spoken":check})
                    summary["veto_of_"+check]+=1
                    per["veto_of_"+check]+=1
                    summary["veto_reason_"+e["reason"]]+=1
            if reasons: results["suppression_reasons"]=reasons
        bs={(e["track_id"],e["label"],e["verdict"]) for e in results["baseline"]}
        cs={(e["track_id"],e["label"],e["verdict"]) for e in results["candidate"]}
        for _,_,v in bs-cs: summary["lost_"+v]+=1
        for _,_,v in cs-bs: summary["added_"+v]+=1
        rows.append(dict(path=row["path"],truth=actual,**results))
    values=[r["iou"] for r in data["rows"] if r["iou"] is not None]
    out=dict(counts=summary,per_class=by_class, mean_iou=sum(values)/len(values) if values else None,
             voices=rows, artificial_exposure="identical still at 0, 200 and 400 ms; isolated trial; simulated audio clock")
    (HERE/"matched-still-speech.json").write_text(json.dumps(out,indent=2),encoding="utf8")
    print(dict(summary),flush=True)

def check_existing_tracker():
    source=read(HERE.parent/"step_h/city-live.json")
    cap=cv2.VideoCapture(source["video"])
    old, new=load_baseline_tracker()(), AlertTracks()
    reference_frames=0
    associations=0
    for row in source["observations"]:
        n=row["frame"]; cap.set(1,n)
        ok,im=cap.read()
        assert ok and round(cap.get(1))-1==n
        h,w=im.shape[:2]
        resized=DesktopVideoPlayer._resize_for_display(im)
        frame=DisplayFrame(1,n,row["media_ms"],w,h,resized)
        detections=tuple(ClassifiedDetection(**r) for r in row["detections"])
        ordered=lambda seq: [(t.id,t.box,t.confirmed) for t in seq]
        lhs,rhs=(ordered(tracker.update(frame,detections,row["media_ms"]/1000))
                 for tracker in (old,new))
        assert lhs==rhs,(n,lhs,rhs)
        reference_frames+=1
        associations+=len(lhs)
    assert (old.created,old.lost,old.unresolved_associations)==(new.created,new.lost,new.unresolved_associations)
    result=dict(frames=reference_frames,obs=associations,identical_between_builds=True,tracks_created=new.created,
                tracks_lost_before_final_frame=new.lost,unresolved_associations=new.unresolved_associations)
    (HERE/"existing-tracker-regression.json").write_text(json.dumps(result,indent=2),encoding="utf8")
    print(result,flush=True)

if __name__=="__main__":
    evaluate_stills()
    check_existing_tracker()


