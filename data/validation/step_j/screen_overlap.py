"""Screen a local candidate clip for duplicate frames in the development video."""
import json
from pathlib import Path
import cv2
import numpy as np

def tiny(image):
    return cv2.resize(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY),(48,27),interpolation=cv2.INTER_AREA).astype(np.float32)

clip=cv2.VideoCapture(r'D:\TSR\10364-224234516.mp4')
targets={}
for frame in (0,65,194,259,389,519,648):
    clip.set(1, frame)
    ok,img=clip.read()
    assert ok
    targets[frame]=tiny(img)
source=cv2.VideoCapture('data/videos/test_video.mp4')
scores={k:[] for k in targets}
frame=0
while source.grab():
    if frame % 6 == 0:
        ok,img=source.retrieve()
        if not ok: break
        im=tiny(img)
        for k,expected in targets.items():
            scores[k].append((float(np.abs(im-expected).mean()),frame))
    frame+=1
result={k:sorted(v)[:5] for k,v in scores.items()}
print(frame, result)
(Path(__file__).parent/'video-overlap-screen.json').write_text(json.dumps(result,indent=2),encoding='utf8')
