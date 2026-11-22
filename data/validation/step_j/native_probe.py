import sys, time
import os, subprocess
from types import ModuleType
def install_baseline_modules():
    from src.traffic_sign_demo import __name__ as package
    for target in ("vision","alert_tracking","tracked_voice_alerts","inference_service"):
        name = f"{package}.{target}"
        path = f"src/traffic_sign_demo/{target}.py"
        data = subprocess.check_output(["git","show",f"step-h-baseline:{path}"])
        module = ModuleType(name)
        module.__file__ = str(Path(path).resolve())
        module.__package__ = package
        sys.modules[name] = module
        exec(compile(data,path,"exec"),module.__dict__)
started=time.perf_counter()
if sys.orig_argv[1:] == ['-m','src.traffic_sign_demo']:
 import ctypes as c, ctypes.wintypes as w, json, os, statistics
 from pathlib import Path
 from unittest.mock import patch
 from dataclasses import asdict
 from PIL import ImageTk
 import winsound
 if os.environ.get('TRAFFIC_J_BASELINE'):
    install_baseline_modules()
 from src.traffic_sign_demo import main, desktop_ui
 from src.traffic_sign_demo.playback_controller import PlaybackState
 root_dir=Path(os.environ['TRAFFIC_H_WORK'])
 output=root_dir/os.environ.get('TRAFFIC_H_RUN','live')
 output.mkdir(exist_ok=True)
 player=main.DesktopVideoPlayer
 video=Path(os.environ.get('TRAFFIC_H_VIDEO','data/videos/test_video.mp4')).resolve()
 end=int(os.environ.get('TRAFFIC_H_END','1505'))
 expect_error=bool(os.environ.get('TRAFFIC_H_EXPECT_ERROR'))
 class Memory(c.Structure):
    _fields_=[('cb',w.DWORD),('faults',w.DWORD)]+[(n,c.c_size_t) for n in
             ('peak_ws','ws','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile')]
 kernel=c.WinDLL('kernel32',use_last_error=True)
 kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD]
 kernel.OpenProcess.restype=w.HANDLE
 kernel.CloseHandle.argtypes=[w.HANDLE]
 kernel.GetProcessTimes.argtypes=[w.HANDLE]+[c.POINTER(w.FILETIME)]*4
 memory=c.WinDLL('psapi').GetProcessMemoryInfo
 memory.argtypes=[w.HANDLE,c.POINTER(Memory),w.DWORD]
 def proc(pid):
    h=kernel.OpenProcess(0x410,False,pid)
    if not h:return None
    try:
        m=Memory(); m.cb=c.sizeof(m)
        ts=[w.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(h,*[c.byref(t) for t in ts]) or not memory(h,c.byref(m),m.cb): return None
        return [sum((t.dwHighDateTime<<32)+t.dwLowDateTime for t in ts[2:])/1e7,m.ws]
    finally: kernel.CloseHandle(h)
 def create(root,**kw):
    p=player(root,**kw); root.attributes('-disabled',True)
    voice=p._alerts
    obs,wrap_display,old_audio=p._alerts.observe,p._display_frame,winsound.PlaySound
    old_results=p._handle_inference_result
    rows=[]; audio=[]; views=[]; samples=[]; output_frames=[]; proc_samples=[]; errors=[]
    opened=ready=first_overlay=None
    imgs=set()
    pids={}
    def observe(frame,detections):
        tracks=obs(frame,detections)
        if detections:
            rows.append(dict(frame=frame.frame_id,media_ms=frame.timestamp_ms,detections=[asdict(d) for d in detections],tracks=tracks))
        return tracks
    def audio_start(filename,flags):
        old_audio(filename,flags)
        audio.append(dict(at=time.monotonic(),frame=p._displayed_frame_id,path=str(filename) if filename else None))
    def result(row):
        samples.append(dict(frame=row.frame_id,session=row.session_id,elapsed=row.elapsed_ms,
                            turnaround=(row.completed_monotonic-row.submitted_monotonic)*1000,submitted=row.submitted_monotonic,positive=bool(row.detections)))
        return old_results(row)
    def display(frame,dets=(),count_for_fps=True,**kwargs):
        nonlocal first_overlay
        dets=kwargs.pop('detections',dets); wrap_display(frame,dets,count_for_fps,**kwargs)
        now=time.perf_counter()
        if count_for_fps: views.append([frame.frame_id,now])
        if dets:
            if first_overlay is None: first_overlay=now
            output_frames.append([frame.frame_id,now,(now-min(d.valid_yolo_at for d in dets))*1000,
                                 [d.cnn_class_id for d in dets]])
            bucket=frame.frame_id//150
            if bucket not in imgs:
                imgs.add(bucket); ImageTk.getimage(p._photo).save(output/f'frame-{frame.frame_id}.png')
    voice.observe=observe; winsound.PlaySound=audio_start; p._display_frame=display; p._handle_inference_result=result
    root.report_callback_exception=lambda typ,value,tb:errors.append(repr(value))
    def start():
        nonlocal opened
        opened=time.perf_counter()
        with patch.object(desktop_ui.filedialog,'askopenfilename',return_value=str(video)): p.open_button.invoke()
    last_proc=0
    def tick():
        nonlocal ready,last_proc
        now=time.perf_counter(); status=p.inference.worker_status
        if ready is None and all(d['state']=='ready' for d in status.values()):
            ready=now
            for name,d in status.items(): pids[name]=d['pid']
            pids['ui']=os.getpid()
            import subprocess
            query="Get-CimInstance Win32_Process -Filter 'ParentProcessId={}' | Select-Object -ExpandProperty ProcessId"
            launcher=pids.get('yolo')
            if launcher:
                ids=subprocess.check_output(['powershell','-NoProfile','-Command',query.format(launcher)], creationflags=subprocess.CREATE_NO_WINDOW,text=True).split()
                for i, pid in enumerate(ids): pids[f'yolo_child_{i+1}']=int(pid)
        if ready is not None and now-last_proc>=1.75:
            last_proc=now
            proc_samples.append([now,{name:proc(pid) for name,pid in pids.items()}])
        eof=p._source_eof and not p._frame_buffer
        frame=p._displayed_frame_id or 0
        if not (errors or eof or frame>=end or now-started>180 or (not expect_error and p.inference.status.startswith('AI Error:'))):
            root.after(60,tick);return
        try:
            stats=voice.diagnostics; trace=voice.trace; measured_ai_fps=p.inference.ai_fps
            steady=[x for x in views if ready is not None and x[1]>=ready]
            fps=(len(steady)-1)/(steady[-1][1]-steady[0][1]) if len(steady)>1 else None
            native_audio=list(audio)
            checked={}
            if not errors and (frame>=end or eof):
                checked['open']=p.controller.path == video and bool(views)
                if not eof:
                    p.pause_button.invoke(); checked['pause']=p.controller.state is PlaybackState.PAUSED
                    p.resume_button.invoke(); checked['resume']=p.controller.state is PlaybackState.PLAYING
                checked['eof_idle']=voice._completed and stats['pending']==0 if eof else None
                p.stop_button.invoke(); checked['stop']=p.controller.state is PlaybackState.STOPPED
                p.replay_button.invoke(); checked['replay']=p.controller.state is PlaybackState.PLAYING and p._displayed_frame_id==0
            metrics=dict(video=str(video),frames=[views[0][0],frame] if views else [],eof=eof,errors=errors,
                startup_ready_s=None if ready is None else ready-started,
                startup_first_overlay_s=None if first_overlay is None else first_overlay-started,
                open_to_first_overlay_s=None if first_overlay is None else first_overlay-opened,
                display_fps=fps,ai_fps=measured_ai_fps,workers=status,controls=checked,
                status=p.inference.status,peaks=stats,trace=trace,observations=rows,actual_audio=native_audio,results=samples,
                overlays=output_frames,views=views,system=proc_samples,logical_cpus=os.cpu_count(),pids=pids)
            (output/'live.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')
        finally:
            p.close()
    root.after(0,start);root.after(60,tick)
    return p
 main.DesktopVideoPlayer=create




