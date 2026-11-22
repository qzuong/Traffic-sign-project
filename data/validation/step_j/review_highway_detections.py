import json, os
from pathlib import Path
import cv2, numpy as np
a=Path(os.environ['TEMP'])/'traffic-step-j'
dest=Path('data/validation/step_j')
for name in ['highway-baseline','highway-candidate']:
    log=json.loads((a/name/'live.json').read_text(encoding='utf8'))
    cap=cv2.VideoCapture(log['video']); panels=[]
    for row in log['observations']:
        frame=row['frame']; cap.set(1,frame)
        ok,im=cap.read(); assert ok and round(cap.get(1))-1==frame
        for det in row['detections']:
            x,y,r,b=map(round,det['bbox'])
            show=im[max(y-50,0):b+50,max(x-50,0):r+50].copy()
            pos=(x-max(0,x-50),y-max(0,y-50))
            cv2.rectangle(show,pos,(pos[0]+r-x,pos[1]+b-y),(10,235,10),1)
            pane=cv2.copyMakeBorder(cv2.resize(show,(200,140)),27,0,0,0,0)
            cv2.putText(pane,f'f {frame} / CNN {det["cnn_class_id"]}',(6,19),0,.53,(0,255,255),1)
            panels.append(pane)
    if panels:
        while len(panels)%5: panels.append(np.zeros_like(panels[0]))
        cv2.imwrite(str(dest/f'{name}-detections.jpg'),np.vstack([np.hstack(panels[i:i+5]) for i in range(0,len(panels),5)]))
    print(name,'rendered positive observations',len(log['observations']),
          'rendered predictions',sum(len(row['detections']) for row in log['observations']))
    (dest/f'{name}-live.json').write_text(json.dumps(log,indent=2,ensure_ascii=False),encoding='utf8')
