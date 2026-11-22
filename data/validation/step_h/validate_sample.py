import argparse, hashlib, json, time
from dataclasses import asdict
from pathlib import Path
from src.traffic_sign_demo.video_reader import VideoReader
from scripts.benchmark_detectors import iou
from src.traffic_sign_demo.inference_service import InferenceService
a=Path(__file__).parent
truth=json.loads((a/'annotations.json').read_text(encoding='utf8'))
frames=truth['frames']
parser=argparse.ArgumentParser(description='Replay the manual Step H sample with the production inference service.')
parser.add_argument('--output', type=Path, required=True)
args=parser.parse_args()
if args.output.exists():
    parser.error(f'Output already exists: {args.output}')
path=Path(truth['video'])
with path.open('rb') as video_file:
    if hashlib.file_digest(video_file,'sha256').hexdigest()!=truth['sha256']:
        raise ValueError(f'Video SHA-256 differs from the annotated source: {path}')
reader=VideoReader(path)
reader.open()
service=InferenceService(image_size=640,confidence=.25,preload_workers=True,detector="gtsdb")
output={}
try:
 for k in sorted(frames,key=int):
    image, decoded = reader.seek(int(k))
    if decoded != int(k):
        raise ValueError(f'Expected frame {k} but decoded {decoded}')
    service.submit(image,int(k),int(k)*1000/30)
    deadline=time.monotonic()+125
    while (result:=service.poll_result()) is None:
        if time.monotonic()>deadline or service.status.startswith('AI Error:'):
            raise RuntimeError(service.status)
        time.sleep(.015)
    assert result.frame_id==int(k)
    info=service.diagnostics
    assert info['last_yolo_detection_count']==len(result.detections), info
    refs=frames[k]; preds=[asdict(d) for d in result.detections]
    hits=[]; matched_ref=set(); matched_pred=set()
    pairs=sorted(((iou(ref['box'],pred['bbox']),i,j) for i,ref in enumerate(refs)
                  for j,pred in enumerate(preds)),reverse=True)
    for overlap,i,j in pairs:
        if overlap < .5:break
        if i not in matched_ref and j not in matched_pred:
            matched_ref.add(i);matched_pred.add(j)
            hits.append(dict(reference=i,prediction=j,iou=overlap))
    output[k]=dict(references=refs,predictions=preds,matches=hits,
        fn=sorted(set(range(len(refs)))-matched_ref),fp=sorted(set(range(len(preds)))-matched_pred),
        elapsed_ms=result.elapsed_ms)
    print(k, 'TP',len(hits),'FP',len(output[k]['fp']),'FN',len(output[k]['fn']),flush=True)
 with args.output.open('x', encoding='utf-8') as file:
    json.dump(output, file, indent=2)
finally:
 service.close()
 reader.close()

