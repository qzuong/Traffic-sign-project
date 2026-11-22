"""Read selected official benchmark archive members using HTTP byte ranges."""
import io
import re
import requests
import zipfile

ROOT="https://sid.erda.dk/public/archives/ff17dc924eba88d5d01a807357d6614c/"
class Remote(io.RawIOBase):
    def __init__(self, name):
        self.url=ROOT+name
        self.session=requests.Session()
        self.pos=0
        res=self.session.get(self.url,headers={"Range":"bytes=0-0"},timeout=25)
        res.raise_for_status()
        assert res.status_code==206 and res.headers["Content-Range"].startswith("bytes 0-0/"), dict(res.headers)
        self.size=int(res.headers["Content-Range"].split("/")[-1])
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos
    def seek(self,n,whence=0):
        self.pos=n+({0:0,1:self.pos,2:self.size}[whence])
        if self.pos<0: raise ValueError(self.pos)
        return self.pos
    def read(self,n=-1):
        n=min(self.size-self.pos,n if n>=0 else self.size-self.pos)
        if n<=0:return b""
        last=self.pos+n-1
        res=self.session.get(self.url,headers={"Range":f"bytes={self.pos}-{last}"},timeout=45)
        res.raise_for_status()
        assert res.headers.get("Content-Range","")==f"bytes {self.pos}-{last}/{self.size}", dict(res.headers)
        assert len(res.content)==n
        self.pos+=n
        return res.content
    def close(self):
        self.session.close()
        super().close()

def inspect():
    for name in ("TestIJCNN2013.zip","FullIJCNN2013.zip"):
        with Remote(name) as http, zipfile.ZipFile(http) as z:
            images=[f for f in z.namelist() if re.search(r"(^|/)\d{5}\.ppm$",f) and f.count("/")<=1]
            print(name,http.size,len(images),images[:3],images[-3:],flush=True)
            for f in z.namelist():
                if f.endswith("gt.txt") and f.count("/")<=1:
                    labels=z.read(f).decode()
                    print(f,len(labels.splitlines()),labels.splitlines()[:2],labels.splitlines()[-2:],flush=True)
    response=requests.get(ROOT+"gt.txt",timeout=10)
    response.raise_for_status()
    print(len(response.text.splitlines()),response.text.splitlines()[:2])
if __name__=="__main__":inspect()
