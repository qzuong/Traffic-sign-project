"""Replay known Step I failure scenes with the frozen policies."""
from dataclasses import replace
import json,statistics,sys,wave
from pathlib import Path
import cv2
from crop_evidence import HERE,features
from policies import POLICIES,block
from analyze_tuning import read
from src.traffic_sign_demo.vision import clip_bbox,preprocess_crop
from src.traffic_sign_demo.tracked_voice_alerts import TrackedVoiceAlerts
from src.traffic_sign_demo.voice_alerts import _clip_timing

sys.path.insert(0,str(HERE.parent/"step_j"))
from compare_speech import replay

old_data=read(HERE.parent/"step_i/cnn-forensics.json")
models={(x["tag"],x["frame_id"],tuple(x["detected_box"])):x["top5"]
        for x in old_data if x["tag"] in {"repeat","motorway"}}
timings={}
for i in range(43):
    with wave.open(f"assets/voice_google/{i:02}.wav","rb") as wav:timings[i]=_clip_timing(wav,check_tail=True)
def known_timeline(log,tag):
    camera=cv2.VideoCapture(log["video"])
    for at,frame,detections in replay.recording(log):
        evidence=[]
        if detections:
            assert camera.set(1,frame.frame_id)
            ok,im=camera.read()
            assert ok and round(camera.get(1))-1==frame.frame_id
            for d in detections:
                h,w=im.shape[:2]
                x,y,r,b=clip_bbox(d.bbox,w,h)
                prob=models[tag,frame.frame_id,tuple(d.bbox)]
                evidence.append(dict(pred=d.cnn_class_id,baseline=d.speech_veto,
                    margin=prob[0]["probability"]-prob[1]["probability"],width=r-x,height=b-y,
                    **features(preprocess_crop(im[y:b,x:r])[0])))
        out={p:tuple(replace(d,speech_veto=block(e,p)) for d,e in zip(detections,evidence)) for p in POLICIES}
        yield at,frame,out
    camera.release()
out={}
for filename,source in [("performance-live.json","repeat"),("motorway-live.json","motorway")]:
    log=read(HERE.parent/"step_h"/filename)
    book=list(known_timeline(log,source))
    results={}
    for p in POLICIES:
        run=replay.simulate(TrackedVoiceAlerts,[(at,f,r[p]) for at,f,r in book],timings)
        stats=run["stats"]; delays=stats["speech_latency_ms"]
        results[p]=dict(played=stats["played_tracks"],withheld=stats.get("tracks_with_speech_suppression",0),
            latency_median_max_ms=[statistics.median(delays),max(delays)] if delays else None,
            suppression=[r for r in run["trace"] if r["event"]=="speech_suppressed"])
    out[source]=results
    print(source,{p:(r["played"],r["latency_median_max_ms"]) for p,r in results.items()},flush=True)
panel=read(HERE.parent/"step_i/blue-panel-forensics.json")
out["known_blue_panel"]={p:[block(dict(pred=r["top5"][0]["class_id"],
    baseline="roundabout_voice_unverified",margin=r["top5"][0]["probability"]-r["top5"][1]["probability"]),p)
    for r in panel] for p in POLICIES}
(HERE/"known-live-observation-replay.json").write_text(json.dumps(out,indent=2),encoding="utf8")
