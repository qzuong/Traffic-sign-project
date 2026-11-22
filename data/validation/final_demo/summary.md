# Traffic sign desktop prototype — final demo

## Version and scope

- Annotated tag `final-demo` resolves to application commit `f2f61cbde310b762fd351873f546b761b631343f`, also tagged `step-i-candidate`.
- Step H comparison baseline `57b793b` (`step-h-baseline`).
- GTSDB YOLOv8n on CPU, `imgsz=640`, `conf=0.25`. The CNN classifies 30×30 RGB crops normalized by 255. The renderer supports all 43 classes. Speech uses Step I eligibility and local Google WAVs, with local eSpeak fallback.
- Step K's margin-only and selective speed-recovery policies remain offline experiments.

## Run the desktop demo

~~~powershell
Set-Location D:\Traffic-sign-project
python -m src.traffic_sign_demo
~~~

1. Choose **Open Video** and select `D:\Traffic-sign-project\data\videos\test_video.mp4`. The app opens frame zero, waits for both workers, and starts playback automatically.
2. Let the first **50 seconds of video time** play continuously. The times below refer to the video position. Worker startup adds wall-clock time before the demonstration.
3. After the Yield scene, Pause, Resume, Stop and Replay can be demonstrated. Replay starts from frame zero. Close via the window's **X**.

| Approx. video time | What to look for |
|---|---|
| 00:02–00:07 | City intersection. Priority Road and mandatory-direction signs can appear early. Spoken clips vary with confirmation and queue timing. |
| 00:12–00:16 | Blue **Giữ bên phải** (Keep Right) signs. Expect an automatic box and a spoken Keep Right alert when a track qualifies. |
| 00:24–00:27 | City junction. **Đi thẳng** (Ahead Only), and sometimes a separate Yield detection. Speech depends on confirmed tracks. |
| 00:35–00:37 | Another Keep Right sign near the approaching intersection. |
| 00:44–00:46 | **Nhường đường** (Yield) and adjacent **Rẽ phải** (Turn Right Ahead). The app has repeatedly displayed both boxes and spoken Yield in this scene. |

The box and its Vietnamese text show the **raw CNN prediction**, including tracked visual overlays between inference frames. The **Voice confirmed** status and audible clip identify a class that passed speech eligibility and reached playback. A visible label can stay silent because of crop evidence, insufficient agreement, queue expiration, or the Roundabout veto. Voice status can remain on the last spoken class while new boxes appear.

The white Priority Road sign near the Keep Right scene can receive a raw Keep Right prediction and be withheld because its face lacks blue evidence. In the separately tested motorway interval near **04:52**, electronic 100 km/h signs produced unreliable raw labels and were withheld from speech. Roundabout labels display, while specific Roundabout speech is disabled.

## Final verification

**96 tests passed**, including real-model inference. The continuous desktop run reached frames **0–1501** through Open Video, with automatic boxes and Vietnamese labels. It exercised separate worker environments, Track IDs, temporal confirmation, local Google WAV playback, queue expiration, and Pause / Resume / Stop / Replay. Both processes became ready in **23.79 s** from the start of the probe. The first overlay appeared **25.05 s** after Open Video.

| Worker | Interpreter used |
|---|---|
| YOLO | `D:\Traffic-sign-project\.venv-yolo\Scripts\python.exe` |
| CNN | `C:\Program Files\Python313\python.exe` |

I visually verified all seven spoken alerts in the final run. Priority Road spoke at **03.13 s**, Straight or Turn Left at **06.10 s**, Keep Right at **12.73 s**, Ahead Only at **15.80 s**, Yield at **25.33 s**, Keep Right at **36.30 s**, and Yield at **44.27 s**. Audio calls were sequential, with seven distinct Track IDs. Eight accepted alerts expired, 85 duplicate offers were suppressed, and one unsupported Keep Right track was blocked before admission. A separate 7.5-second excerpt reached frame 224 and cleared **three pending alerts** at end of video. The recorded app and worker processes exited after close. [Run](continuous-live.json) · [Voice crops](voice-crops.png) · [Yield overlay](yield-overlay.png) · [End-of-video run](eof-live.json) · [Hashes and verification](freeze-verification.json)

Run the regression suite from the project root in PowerShell.

~~~powershell
$env:TRAFFIC_SIGN_REAL_MODEL_TEST = '1'
python -m unittest discover -s tests
~~~

The desktop evidence uses [the existing QA probe](../step_j/native_probe.py) as a temporary `sitecustomize.py`. It selects the file via Open Video, captures overlays and audio calls during automatic playback, then exercises the controls. To repeat the probe in a fresh PowerShell session, run from the project root.

~~~powershell
$probe = Join-Path $env:TEMP ('traffic-final-check-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $probe | Out-Null
Copy-Item data\validation\step_j\native_probe.py (Join-Path $probe 'sitecustomize.py')
$env:PYTHONPATH = "$probe;$(Get-Location)"
$env:TRAFFIC_H_WORK = $probe
Remove-Item Env:TRAFFIC_J_BASELINE, Env:TRAFFIC_H_EXPECT_ERROR -ErrorAction SilentlyContinue
$env:TRAFFIC_H_RUN = 'continuous'
$env:TRAFFIC_H_VIDEO = (Resolve-Path data\videos\test_video.mp4).Path
$env:TRAFFIC_H_END = '1500'
python -m src.traffic_sign_demo
$env:TRAFFIC_H_RUN = 'eof'
$env:TRAFFIC_H_VIDEO = (Resolve-Path data\validation\final_demo\eof-sample.mp4).Path
$env:TRAFFIC_H_END = '10000'
python -m src.traffic_sign_demo
~~~

The probe writes one `live.json` per run below `$probe`. Run the ordinary demo command from its own PowerShell session. [Test log](regression.log)

The Step H–K originals remain in their existing validation folders. A verified backup of **143 evidence files** is at `D:\Traffic-sign-project-backups\step-h-to-k-evidence-f2f61cb.zip`. The manifest records the archive SHA-256 and hashes of the preserved files. [Evidence manifest](evidence-manifest.json)

## Experiment results

Localization uses one-to-one matching at IoU ≥ 0.50. CNN accuracy in full scenes is conditional on a matched detection with a scorable label. The GTSRB result uses dataset-provided crops.

| Dataset | Composition and interpretation | YOLO TP / FP / FN | Precision / recall | CNN |
|---|---|---:|---:|---:|
| [H — original video](../step_h/detections.json) | 17 exact frames, 31 signs, 4 negative frames, one route | 24 / 2 / 7 | 92.3% / 77.4% | 17/21 readable localized crops |
| [J — local GTSRB test split](../step_j/gtsrb-roi-results.json) | 12,630 annotated crops, 43 classes | Crop task | Crop task | 12,216/12,630 (96.72%) |
| [J — official GTSDB still scenes](../step_j/gtsdb-results.json) | 55 scenes, 75 signs, 10 negative scenes | 75 / 2 / 0 | 97.4% / 100% | 75/75 matched crops |
| [K — additional GTSDB still scenes](../step_k/gtsdb-holdout-results.json) | 64 scenes, 87 signs, 12 negative scenes | 83 / 1 / 4 | 98.8% / 95.4% | 83/83 matched crops |
| [K — BelgiumTSC holdout](../step_k/belgium-holdout-results.json) | 607 mapped labeled crops, 202 physical signs | Crop task | Crop task | 513/607 mapped crops (84.5%) |

GTSDB J includes scenes in the detector author's published training and validation conversion. K excludes duplicate Step J images and that published training partition. Historical checkpoint exposure is uncertain. K used the already inspected local GTSRB split for tuning, found eight exact Train/Test file matches there, and found zero exact decoded ROI matches between the Belgian holdout and local tuning crops. Both experimental policies were frozen before holdout scoring. [Sample partition audit](../step_j/published-split-overlap.json) · [Policy lock](../step_k/policy-lock.json) · [Data integrity](../step_k/dataset-integrity.json)

### Tracking, speech and coverage

- **H, continuous city playback.** A manually followed Yield sign switched IDs **four times across 12 matched observations**, and its adjacent right-turn sign switched **twice across 11**. One city run produced 6 correct, 1 wrong, and 1 unresolved spoken alert. A separate motorway run announced 70 km/h for an electronic 100 km/h sign. Another repeated error was Priority Road spoken as Keep Right. [Tracking review](../step_h/tracking-review.json) · [Voice review](../step_h/voice-review.json)
- **I, paired replay of recorded observations.** Across the city, electronic motorway, and blue-panel traces, correct alerts selected rose **6 → 7** and wrong alerts fell **3 → 0**. Six tracks had speech suppressed. The city replay retained **1.86 s median** detection-to-speech and moved **2.63 → 2.50 s max**. Raw CNN classification on the H sample stayed **17/21**. [Paired replay](../step_i/replay-metrics.json)
- **J, moving-road negative check.** Both builds played a separate 13-second motorway clip and spoke zero alerts. The reviewed detections were out-of-scope markers, sign backs, or background. In a motion replay on the original video, both trackers had identical IDs and confirmations over **148 associations**. All **75** matched GTSDB signs kept their IDs across repeated stills. Positive tracking performance on independent moving footage remains unverified. [Motorway trace](../step_j/highway-candidate-live.json) · [Motion replay](../step_j/existing-tracker-regression.json) · [Static tracking](../step_j/matched-static-tracking.json)
- **J, still-scene speech simulation.** Step H selected **45 correct / 0 wrong**, and Step I selected **35 correct / 0 wrong**. Step I removed 14 previously selected correct alerts, admitted four replacements, and vetoed all three correctly classified Roundabout candidates. [Matched still-scene results](../step_j/gtsdb-results.json)
- **K, alternative policies.** On the local GTSRB tuning crops, stable Step I allowed **7,941 correct / 189 wrong** and withheld **4,275 correct / 225 wrong** predictions. On the Belgian holdout, stable, margin-only, and selective speed recovery allowed **410/73**, **389/44**, and **405/44** correct/wrong crops. All three selected **41 correct / 0 wrong** on new GTSDB scenes with a virtual audio clock and repeated static observations. Step I remains selected. [Per-class coverage](../step_k/per-class-coverage.csv) · [Fixed replay](../step_k/known-live-observation-replay.json)

### Actual desktop throughput and latency

AI FPS is the rolling value at the endpoint. Display FPS is measured after worker readiness. Latency uses first valid YOLO detection to speech start.

| Run, original city video | Display FPS | AI FPS | Detection to speech, median / max |
|---|---:|---:|---:|
| [H performance run](../step_h/performance-live.json) | 19.00 | 6.97 | 2.12 / 2.98 s |
| [J positive regression](../step_j/positive-regression-live.json) | 18.63 | 6.21 | 1.86 / 3.54 s |
| [K stable desktop](../step_k/stable-native.json) | 18.14 | 5.46 | 1.93 / 3.11 s |
| [L final freeze](continuous-live.json) | 18.80 | 6.12 | 1.97 / 3.09 s |

These are individual runs with varying CPU scheduling and frame sampling. In Step H, warm submit-to-inference-result latency was **172 ms median**. In the final city run, submit-to-visible-overlay latency was **1.82 s median / 1.88 s max** across 99 matched presentations. That endpoint includes display buffering.

## Remaining limitations and readiness

The prototype is ready for a controlled demonstration on the verified video. Electronic speed signs and some priority/direction signs remain classification failure cases. The speech guard reduces specific wrong advice at a measured cost in correct coverage. Roundabout speech is disabled. A physical sign can speak twice if it is reacquired under a different Track ID. Long clips and finite queue capacity can cause an alert to expire while audio is busy. Evidence spans static benchmarks and limited moving footage, with positive moving-road observations concentrated on one source video. CPU inference updates run at a lower rate than video playback. Real-world driving validation remains outside this freeze.
