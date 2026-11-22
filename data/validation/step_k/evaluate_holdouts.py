"""Score the locked policies once on new labeled Belgian crops and German scenes."""
from collections import Counter,defaultdict
from dataclasses import asdict,replace
import hashlib,json,os,sys,time,wave,zipfile
from pathlib import Path

import cv2,numpy as np

from analyze_tuning import read,split_counts
from belgian_sample import ARCHIVE,by_group,crop
from crop_evidence import HERE,row_features,load_model
from policies import POLICIES,block
from src.traffic_sign_demo.vision import preprocess_crop,clip_bbox,DisplayFrame
from src.traffic_sign_demo.desktop_ui import DesktopVideoPlayer
from src.traffic_sign_demo.inference_service import InferenceService
from src.traffic_sign_demo.tracked_voice_alerts import TrackedVoiceAlerts

sys.path.insert(0,str(HERE.parent/"step_j"))
from compare_speech import replay
from evaluate_gtsdb import matches
from src.traffic_sign_demo.voice_alerts import _clip_timing

CACHE=Path(os.environ["TEMP"])/"traffic-step-k"/"gtsdb-holdout"
def assert_locked():
    lock=read(HERE/"policy-lock.json")
    for filename,k in [("policies.py","policy_sha256"),("belgium-label-map.json","label_map_sha256")]:
        assert hashlib.sha256((HERE/filename).read_bytes()).hexdigest()==lock[k]

def belgian(model):
    mapping=read(HERE/"belgium-label-map.json")
    target=defaultdict(dict)
    with zipfile.ZipFile(ARCHIVE) as z:
        def rank(ids):
            return sorted(ids,key=lambda k:hashlib.sha256(("step-k-foreign-v1/"+k).encode()).hexdigest())
        for label,true in mapping["equivalent_belgian_classes"].items():
            label=int(label)
            for key in rank(by_group(z,label))[:24]:target[label][key]=true
        for label,k,true in [
            (32,"manual_speed_50_ids",2),(32,"manual_speed_70_ids",4),
            (34,"manual_straight_ids",35),(35,"manual_keep_right_ids",38),(35,"manual_keep_left_ids",39)]:
            for key in mapping[k]:target[label][key]=true
        rows=[]; batches=[]
        for label,groups in sorted(target.items()):
            src=by_group(z,label)
            for key,true in groups.items():
                seq=sorted(src[key],key=lambda r:r["member"])
                for meta in seq:
                    pix=crop(z,meta)
                    batches.append(pix)
                    rows.append(dict(true=true,group=f"{label}/{key}",**meta))
        seen=set()
        for offset in range(0,len(rows),192):
            batch=batches[offset:offset+192]
            scores=model(np.concatenate([preprocess_crop(c) for c in batch]),training=False).numpy()
            for index,(im,probs) in enumerate(zip(batch,scores)):
                r=rows[offset+index]
                sha=hashlib.sha256(im.tobytes()).hexdigest()
                r.update(image_sha256=sha,**row_features(im,probs))
                seen.add(r["group"])
    # The labels for these repeated crops correspond to physical sign groups.
    groups=defaultdict(list)
    for r in rows:groups[r["group"]].append(r)
    consensus={}
    for policy in POLICIES:
        total=Counter()
        for seq in groups.values():
            vote=Counter(r["pred"] for r in seq if block(r,policy) is None)
            majority=[label for label,n in vote.items() if n>=2 and n>len(seq)/2]
            if not majority:total["withheld"]+=1
            elif majority[0]==seq[0]["true"]:total["correct"]+=1
            else:total["incorrect"]+=1
        consensus[policy]=total
    out=dict(archive_sha256=hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),groups=len(seen),
       cut_note="Ordinal views of same sign; no capture timestamps or full-scene tracks. Consensus is a majority of all supplied views, minimum two.",
       crop_level={p:split_counts(rows,p) for p in POLICIES},group_consensus=consensus,rows=rows)
    (HERE/"belgium-holdout-results.json").write_text(json.dumps(out,indent=2),encoding="utf8")
    print("Belgium",len(rows),len(seen),{p:out["crop_level"][p]["total"] for p in POLICIES},consensus,flush=True)

def acquire_scenes():
    manifest=read(HERE/"holdout-gtsdb-manifest.json")
    probes=[]
    svc=InferenceService(image_size=640,confidence=.25,preload_workers=True,detector="gtsdb")
    try:
        for data in manifest["rows"]:
            n=data["frame"]; file=CACHE/f"{n:05}.ppm"
            assert hashlib.sha256(file.read_bytes()).hexdigest()==data["image_sha256"]
            im=cv2.imread(str(file)); assert im is not None
            svc.submit(im,n,n*1000/30)
            timeout=time.monotonic()+125
            while (res:=svc.poll_result()) is None:
                if time.monotonic()>timeout or svc.status.startswith("AI Error:"): raise RuntimeError(svc.status)
                time.sleep(.01)
            assert res.frame_id==n and svc.diagnostics["last_yolo_detection_count"]==len(res.detections)
            probes.append((data,im,res.detections))
            if len(probes)%15==0:print("scene",len(probes),flush=True)
    finally:svc.close()
    return probes

def evaluate_scenes(probes,model):
    timings={}
    for label in range(43):
        with wave.open(f"assets/voice_google/{label:02}.wav","rb") as clip:
            timings[label]=_clip_timing(clip,check_tail=True)
    totals={p:Counter() for p in POLICIES}
    differences=defaultdict(Counter)
    all_dets=[]; raw=Counter(); result=[]
    for n,(data,im,dets) in enumerate(probes):
        refs=data["references"]
        h,w=im.shape[:2]
        aligned=matches(dets,refs)
        boxes=[clip_bbox(d.bbox,w,h) for d in dets]
        crops=[im[y:b,x:r] for x,y,r,b in boxes]
        tensor=np.concatenate([preprocess_crop(c) for c in crops]) if crops else None
        info=[row_features(c,s) for c,s in zip(crops,model(tensor,training=False).numpy())] if crops else []
        assert all(d.cnn_class_id==v["pred"] and d.speech_veto==v["baseline"] for d,v in zip(dets,info))
        for i,item in enumerate(info):
            item["true"]=refs[aligned[i][0]]["class_id"] if i in aligned else -1
            all_dets.append(item)
        raw["tp"]+=len(aligned);raw["fp"]+=len(dets)-len(aligned);raw["fn"]+=len(refs)-len(aligned)
        raw["negative_scenes"]+=not refs
        raw["cnn_correct"]+=sum(dets[i].cnn_class_id==refs[t]["class_id"] for i,(t,_) in aligned.items())
        case={}
        for policy in POLICIES:
            approved=tuple(replace(d,speech_veto=block(r,policy),valid_yolo_at=.01,valid_cnn_at=.10)
                for d,r in zip(dets,info))
            frames=[(at,DisplayFrame(n,i,at*1000,w,h,im),approved if i<3 else ())
                    for i,at in enumerate((0,.2,.4,.8,1.2,1.6))]
            track_boxes={}
            class Capture(TrackedVoiceAlerts):
                def observe(self,frame,detections):
                    visible=super().observe(frame,detections)
                    track_boxes.update((tid,box) for tid,box,_ in visible)
                    return visible
            result_run=replay.simulate(Capture,frames,timings)
            def grade(tid,label):
                idx=boxes.index(track_boxes[tid])
                return label==info[idx]["true"]
            plays=[]
            for tid,label in result_run["stats"]["played_tracks"]:
                good=grade(tid,label)
                totals[policy]["played_correct" if good else "played_incorrect"]+=1
                totals[policy][f"played_{'correct' if good else 'incorrect'}_{label}"]+=1
                plays.append([tid,label,good])
            for evt in result_run["trace"]:
                if evt["event"]=="speech_suppressed":
                    correct=grade(evt["track_id"],evt["class_id"])
                    totals[policy]["track_correct_withheld" if correct else "track_incorrect_withheld"]+=1
            case[policy]=plays
        initial={tuple(x) for x in case["stable"]}
        for policy in POLICIES[1:]:
            now={tuple(x) for x in case[policy]}
            for _,k,good in now-initial:differences[policy]["gained_correct" if good else "new_incorrect"]+=1
            for _,k,good in initial-now:differences[policy]["missed_correct" if good else "removed_incorrect"]+=1
        result.append(dict(frame=data["frame"],matches=aligned,references=refs,boxes=boxes,evidence=info,played=case))
    out=dict(n=len(probes),detector=raw,crop_level={p:split_counts(all_dets,p) for p in POLICIES},
             paired_playback=totals,diffs=differences,rows=result,
             playback_method="real production scheduler and recorded clip durations; virtual clock and three repeated static observations per scene")
    (HERE/"gtsdb-holdout-results.json").write_text(json.dumps(out,indent=2),encoding="utf8")
    print("GTSDB",len(probes),raw,{k:{i:v for i,v in s.items() if i in ("played_correct","played_incorrect","track_correct_withheld","track_incorrect_withheld")} for k,s in totals.items()},differences,flush=True)

def main():
    assert_locked()
    probes=acquire_scenes()
    model=load_model()
    belgian(model)
    evaluate_scenes(probes,model)
if __name__=="__main__":main()
