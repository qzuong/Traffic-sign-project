"""Select fixed official GTSDB evaluation scenes with targeted classes and negatives."""
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import struct
import zlib
import zipfile

from official_archive import ROOT,Remote

HERE=Path(__file__).resolve().parent
SEED="step-j-gtsdb-official-eval-v1"
CACHE=Path(os.environ["TEMP"])/"traffic-step-j"/"official-scenes"

def fetch(archive,item):
    with Remote(archive) as r:
        r.seek(item.header_offset)
        payload=r.read(1024+item.compress_size)
        signature,_,_,method,_,_,_,_,_,name_len,extra_len=struct.unpack("<IHHHHHIIIHH",payload[:30])
        assert signature==0x04034b50 and method==item.compress_type
        start=30+name_len+extra_len
        raw=payload[start:start+item.compress_size]
        data=zlib.decompress(raw,-15) if method==8 else raw
        assert len(data)==item.file_size and zlib.crc32(data)==item.CRC
        return data

def main():
    full="FullIJCNN2013.zip"
    test="TestIJCNN2013.zip"
    with Remote(full) as source, zipfile.ZipFile(source) as z:
        info={x.filename:x for x in z.infolist()}
        gt=z.read("FullIJCNN2013/gt.txt")
    with Remote(test) as source, zipfile.ZipFile(source) as z:
        names={x.filename:x for x in z.infolist()}
    # The test archive restarts its filenames at zero. The image size and CRC
    # identify the same original file in the complete, labeled archive.
    images={int(Path(x.filename).stem):x for x in info.values()
            if x.filename.endswith(".ppm") and x.filename.count("/")==1}
    by_content=defaultdict(list)
    for k,item in images.items():
        by_content[(item.CRC,item.file_size)].append(k)
    mapping={}
    for name,item in names.items():
        if not name.endswith(".ppm") or name.count("/")!=1:continue
        matches=by_content[(item.CRC,item.file_size)]
        expected=int(Path(name).stem)+600
        assert expected in matches,(name,matches)
        mapping[expected]=name
    assert len(mapping)==300
    labels=defaultdict(list)
    categories=defaultdict(list)
    for line in gt.decode().splitlines():
        f,x,y,r,b,k=line.split(";")
        frame=int(Path(f).stem)
        if frame not in mapping:continue
        k=int(k)
        labels[frame].append(dict(box=[int(x),int(y),int(r)+1,int(b)+1],class_id=k))
        categories[k].append(frame)
    order=lambda i:hashlib.sha256(f"{SEED}/{i}".encode()).hexdigest()
    selected=set()
    priority=sorted(set(range(9))|{9,12,13,14,15,16,17,38,40})
    for k in priority:
        selected.update(sorted(set(categories[k]),key=order)[:3])
    selected.update(sorted((n for n in mapping if not labels[n]),key=order)[:10])
    unique={}
    for n in sorted(selected):
        unique.setdefault((images[n].CRC,images[n].file_size),n)
    selected=sorted(unique.values())
    print("scene selection",len(selected),"targets",sum(len(labels[n]) for n in selected),flush=True)
    CACHE.mkdir(parents=True,exist_ok=True)
    def download(n):
        p=CACHE/f"{n:05}.ppm"
        item=names[mapping[n]]
        if p.exists():
            raw=p.read_bytes()
            assert len(raw)==item.file_size and zlib.crc32(raw)==item.CRC
        else:
            raw=fetch(test,item)
            p.write_bytes(raw)
        return dict(frame=n,archive_member=mapping[n],image_sha256=hashlib.sha256(raw).hexdigest(),references=labels[n])
    with ThreadPoolExecutor(max_workers=8) as pool:
        rows=list(pool.map(download,selected))
    manifest=dict(seed=SEED, test_archive=ROOT+test, labels_archive=ROOT+full,
        gt_file_sha256=hashlib.sha256(gt).hexdigest(), priority_classes=priority, rows=rows)
    (HERE/"gtsdb-sample.json").write_text(json.dumps(manifest,indent=2),encoding="utf8")
if __name__=="__main__":main()

