import json
from pathlib import Path
import cv2
import numpy as np
import tensorflow as tf
from src.traffic_sign_demo.vision import clip_bbox, preprocess_crop
from src.traffic_sign_demo.class_mapping import load_class_mapping

a=Path(__file__).parent
d=json.loads((a/'blue-panel-initial.json').read_text(encoding='utf8'))
reader=cv2.VideoCapture(d['video'])
mapping=load_class_mapping('models/model.py')
tf.config.threading.set_intra_op_parallelism_threads(2)
tf.config.threading.set_inter_op_parallelism_threads(1)
model=tf.keras.models.load_model('models/model.h5',compile=False)
output=[]
for i in (320,326):
 row=next(row for row in d['observations'] if row['frame']==i)
 pred=next(p for p in row['detections'] if p['cnn_class_id']==40)
 reader.set(1,i); ok,frame=reader.read()
 assert ok and round(reader.get(1))-1==i
 x,y,r,b=clip_bbox(pred['bbox'],frame.shape[1],frame.shape[0])
 crop=frame[y:b,x:r]
 file=f'crops/blue-panel-{i}.png'
 cv2.imwrite(str(a/file),crop)
 scores=model(preprocess_crop(crop),training=False).numpy()[0]
 top=[dict(class_id=int(k),label=mapping[int(k)],probability=float(scores[k]))
      for k in np.argsort(scores)[-5:][::-1]]
 output.append(dict(excerpt_frame=i,source_frame=5760+i,source_timestamp_ms=192000+i*1000/30,
    bbox=pred['bbox'],clipped_box=[x,y,r,b],ground_truth='blue rectangular panel, exact subset type unresolved',
    crop=file,top5=top))
(a/'blue-panel-forensics.json').write_text(json.dumps(output,indent=2),encoding='utf8')
print([(row['source_frame'],row['top5'][0]['probability']) for row in output])
