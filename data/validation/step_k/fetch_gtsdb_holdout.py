"""Select unseen official GTSDB test scenes before scoring candidate policies."""
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,os,sys,zipfile,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/"step_j"))
from sample_gtsdb import Remote,ROOT,fetch

CACHE=Path(os.environ["TEMP"])/"traffic-step-k"/"gtsdb-holdout"
SEED="step-k-frozen-external-scenes-v1"
with Remote("FullIJCNN2013.zip") as h,zipfile.ZipFile(h) as z:
    gt=z.read("FullIJCNN2013/gt.txt")
    full={int(Path(x.filename).stem):x for x in z.infolist()
          if x.filename.endswith(".ppm") and x.filename.count("/")==1}
with Remote("TestIJCNN2013.zip") as h,zipfile.ZipFile(h) as z:
    test={int(Path(x.filename).stem)+600:x for x in z.infolist()
          if x.filename.endswith(".ppm") and x.filename.count("/")==1}
assert all((x.CRC,x.file_size)==(full[k].CRC,full[k].file_size) for k,x in test.items())
truth=defaultdict(list)
for line in gt.decode().splitlines():
    f,x,y,r,b,k=line.split(";")
    truth[int(Path(f).stem)].append({"box":[int(x),int(y),int(r)+1,int(b)+1],"class_id":int(k)})
step_j=json.loads((HERE.parent/"step_j/gtsdb-sample.json").read_text(encoding="utf8"))
USED={full[x["frame"]].CRC for x in step_j["rows"]}
sorted_positive=sorted(truth)
published_train=set(sorted_positive[:int(.8*len(sorted_positive))])
available={}
for n,item in sorted(test.items()):
    if n not in published_train and item.CRC not in USED:
        available.setdefault(item.CRC,n)
def order(n):return hashlib.sha256(f"{SEED}/{n}".encode()).hexdigest()
priority=set(range(9))|{9,12,13,14,15,16,17,38,40}
rank=[]
for label in sorted(priority):
    group=sorted((n for n in available.values() if any(a["class_id"]==label for a in truth.get(n,()))),key=order)
    rank+=group[:5]
rank+=sorted((n for n in available.values() if not truth.get(n)),key=order)[:12]
rank=list(dict.fromkeys(rank))
# Add a fixed sample of other labeled scene classes for broader negatives/collisions.
rank+=sorted((n for n in available.values() if truth.get(n) and n not in rank),key=order)[:12]
rank=sorted(set(rank))
CACHE.mkdir(parents=True,exist_ok=True)
def download(n):
    item=test[n]; p=CACHE/f"{n:05}.ppm"
    raw=p.read_bytes() if p.exists() else fetch("TestIJCNN2013.zip",item)
    assert len(raw)==item.file_size and zlib.crc32(raw)==item.CRC
    if not p.exists():p.write_bytes(raw)
    return dict(frame=n,archive_member=item.filename,image_sha256=hashlib.sha256(raw).hexdigest(),
                references=truth[n],prior_step_j_crc_overlap=False,excluded_published_detector_train=True)
print("frozen scene ids",rank,flush=True)
with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(download,rank))
(HERE/"holdout-gtsdb-manifest.json").write_text(json.dumps(dict(seed=SEED,gt_sha256=hashlib.sha256(gt).hexdigest(),
    archive=ROOT+"TestIJCNN2013.zip",rows=rows),indent=2),encoding="utf8")
print(len(rows),sum(len(x["references"]) for x in rows),flush=True)
