"""Semantic simulation observations and bounded local JSONL delivery."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from queue import Empty, Full, Queue
import re
from threading import Event, Thread
from typing import Literal, Protocol, TYPE_CHECKING
from uuid import uuid4

from .vietnamese_labels import VIETNAMESE_CLASSES

if TYPE_CHECKING:
    from .alert_tracking import AlertTrack
    from .vision import DisplayFrame

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Decision:
    event_type: str
    suggested_action: str
    parameters: tuple[tuple[str, str | int | float], ...] = ()


DECISIONS = {
    **{i: Decision(f"SPEED_LIMIT_{speed}", "Cập nhật giới hạn tốc độ", (("limit_kmh", speed),))
       for i, speed in {0: 20, 1: 30, 2: 50, 3: 60, 4: 70, 5: 80, 7: 100, 8: 120}.items()},
    6: Decision("END_SPEED_LIMIT_80", "Ghi nhận kết thúc giới hạn 80 km/h", (("ended_limit_kmh", 80),)),
    9: Decision("NO_OVERTAKING", "Ghi nhận đoạn đường cấm vượt"),
    10: Decision("NO_TRUCK_OVERTAKING", "Ghi nhận hạn chế vượt dành cho xe tải"),
    11: Decision("PRIORITY_AT_INTERSECTION", "Ghi nhận quyền ưu tiên tại giao lộ"),
    12: Decision("PRIORITY_ROAD", "Cập nhật thông tin quyền ưu tiên"),
    13: Decision("YIELD_SIGN", "Chuẩn bị nhường đường"),
    14: Decision("STOP_SIGN", "Lập kế hoạch dừng tại vị trí hợp lệ"),
    15: Decision("NO_VEHICLE_ACCESS", "Ghi nhận đường cấm phương tiện"),
    16: Decision("HEAVY_VEHICLE_RESTRICTION", "Ghi nhận hạn chế phương tiện trên 3,5 tấn", (("mass_threshold_t", 3.5),)),
    17: Decision("NO_ENTRY", "Đánh dấu hướng đường không hợp lệ"),
    **{i: Decision(kind, "Ghi nhận cảnh báo " + hazard)
       for i, (kind, hazard) in enumerate((
           ("GENERAL_DANGER", "nguy hiểm"),
           ("DANGEROUS_LEFT_CURVE", "khúc cua trái"),
           ("DANGEROUS_RIGHT_CURVE", "khúc cua phải"),
           ("DOUBLE_CURVE", "đường cong liên tục"),
           ("UNEVEN_ROAD", "mặt đường gồ ghề"),
           ("SLIPPERY_ROAD", "mặt đường trơn"),
           ("ROAD_NARROWS_RIGHT", "đường hẹp bên phải"),
           ("ROAD_WORK", "công trường"),
           ("TRAFFIC_SIGNALS_AHEAD", "đèn tín hiệu phía trước"),
           ("PEDESTRIANS", "người đi bộ"),
           ("CHILDREN_CROSSING", "trẻ em qua đường"),
           ("BICYCLES_CROSSING", "xe đạp"),
           ("ICE_OR_SNOW", "băng tuyết"),
           ("WILD_ANIMALS", "thú rừng qua đường"),
       ), start=18)},
    32: Decision("END_SPEED_AND_OVERTAKING_RESTRICTIONS", "Ghi nhận kết thúc các hạn chế tốc độ và vượt"),
    33: Decision("TURN_RIGHT_ONLY", "Giới hạn hướng đi hợp lệ", (("permitted_direction", "right"),)),
    34: Decision("TURN_LEFT_ONLY", "Chỉ cho phép hướng rẽ trái", (("permitted_direction", "left"),)),
    35: Decision("STRAIGHT_ONLY", "Chỉ cho phép hướng đi thẳng", (("permitted_direction", "straight"),)),
    36: Decision("STRAIGHT_OR_RIGHT", "Ghi nhận hướng đi thẳng hoặc rẽ phải"),
    37: Decision("STRAIGHT_OR_LEFT", "Ghi nhận hướng đi thẳng hoặc rẽ trái"),
    38: Decision("KEEP_RIGHT", "Ghi nhận ràng buộc đi bên phải"),
    39: Decision("KEEP_LEFT", "Ghi nhận ràng buộc đi bên trái"),
    40: Decision("ROUNDABOUT", "Ghi nhận quy tắc đi qua vòng xuyến"),
    41: Decision("END_NO_OVERTAKING", "Ghi nhận kết thúc đoạn cấm vượt"),
    42: Decision("END_NO_TRUCK_OVERTAKING", "Ghi nhận kết thúc đoạn cấm xe tải vượt"),
}


@dataclass(frozen=True)
class SimulationEvidence:
    observation_count: int
    aggregation_score: float
    speech_evidence_block: str | None
    bbox_xyxy: tuple[int, int, int, int]
    bbox_frame_size: tuple[int, int]


@dataclass(frozen=True)
class SimulationEvent:
    event_id: str
    session_id: str
    event_type: str
    class_id: int
    class_name_vi: str
    track_id: int
    video_timestamp_ms: float
    source_frame_id: int
    confirmed: Literal[True]
    decision_status: Literal["confirmed", "withheld"]
    suggested_action: str | None
    parameters: dict[str, str | int | float]
    evidence: SimulationEvidence
    created_at: str
    schema_version: str = "1.0"


class SimulationPublisher(Protocol):
    def publish_simulation_event(self, event: SimulationEvent) -> bool: ...


class SimulationSession:
    """Bind event identity to playback epochs, independently of audio delivery."""

    def __init__(self, publisher: SimulationPublisher):
        self.publisher = publisher
        self.session_id: str | None = None
        self.generation: int | None = None
        self.last_event: SimulationEvent | None = None

    def begin(self, generation: int) -> None:
        self.finish()
        self.session_id = uuid4().hex
        self.generation = generation

    def rebind(self, generation: int) -> None:
        self.generation = generation

    def finish(self) -> None:
        self.session_id = None
        self.generation = None
        self.last_event = None

    def observe(self, frame: DisplayFrame, track: AlertTrack) -> SimulationEvent | None:
        session, label = self.session_id, track.confirmed
        if (session is None or frame.session_id != self.generation or label not in DECISIONS
                or track.simulation_session == session
                or (self.last_event and frame.timestamp_ms < self.last_event.video_timestamp_ms)):
            return None
        decision = DECISIONS[label]
        votes = [score for _, voted, score, _ in track.votes if voted == label]
        total = sum(score for _, _, score, _ in track.votes)
        block = track.speech_block
        height, width = frame.image.shape[:2]
        event = SimulationEvent(
            event_id=f"{session}:track-{track.id}", session_id=session, event_type=decision.event_type,
            class_id=label, class_name_vi=VIETNAMESE_CLASSES[label], track_id=track.id,
            video_timestamp_ms=frame.timestamp_ms, source_frame_id=frame.frame_id, confirmed=True,
            decision_status="withheld" if block else "confirmed",
            suggested_action=None if block else decision.suggested_action,
            parameters={} if block else dict(decision.parameters),
            evidence=SimulationEvidence(len(votes), sum(votes) / total if total else 0.0,
                                        block, track.box, (width, height)),
            created_at=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        )
        track.simulation_session = session
        self.last_event = event
        self.publisher.publish_simulation_event(event)
        logger.debug(
            "Simulation event generated id=%s type=%s class_id=%s track_id=%s status=%s.",
            event.event_id,
            event.event_type,
            event.class_id,
            event.track_id,
            event.decision_status,
        )
        return event


class JsonlSimulationPublisher:
    """Write each queued event on a worker, flushing it before proceeding."""

    def __init__(self, directory: Path, capacity: int = 128):
        if capacity < 1:
            raise ValueError("Export queue capacity must be positive.")
        self.directory = directory
        self._queue: Queue[SimulationEvent] = Queue(maxsize=capacity)
        self._closing = Event()
        self.done = Event()
        self.dropped = 0
        self.failures = 0
        Thread(target=self._write, name="simulation-jsonl", daemon=True).start()

    def publish_simulation_event(self, event: SimulationEvent) -> bool:
        if not self._closing.is_set():
            try:
                self._queue.put_nowait(event)
                return True
            except Full:
                pass
        self.dropped += 1
        return False

    def close(self) -> None:
        self._closing.set()

    def _write(self) -> None:
        session = None
        try:
            while True:
                try:
                    event = self._queue.get(timeout=0.05)
                except Empty:
                    if self._closing.is_set():
                        return
                    continue
                try:
                    if re.fullmatch(r"[0-9a-f]{32}", event.session_id) is None:
                        raise ValueError("Invalid simulation session identifier.")
                    self.directory.mkdir(parents=True, exist_ok=True)
                    path = self.directory / f"session-{event.session_id}.jsonl"
                    line = json.dumps(asdict(event), ensure_ascii=False, allow_nan=False) + "\n"
                    with path.open("a" if session == event.session_id else "x", encoding="utf-8", newline="\n") as stream:
                        session = event.session_id
                        stream.write(line)
                except (OSError, ValueError):
                    self.failures += 1
                    if self.failures == 1:
                        logger.exception("Simulation event export failed.")
        finally:
            self.done.set()
