"""
Logger Service

Structured logging with two categories:
- system: printed to console + CSV (technical/debug events)
- feedback: CSV only (generated feedback items)
"""
import csv
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from backend.api.serialization import json_safe
from backend.types.feedback import FeedbackItem


class LogLevel(Enum):
    """Log level hierarchy (ascending verbosity)."""
    ERROR = 4
    WARNING = 3
    INFO = 2
    DEBUG = 1


@dataclass
class LogEntry:
    timestamp: float
    level: str
    event_type: str
    data: Dict[str, Any]
    seconds_since_start: Optional[float] = None


@dataclass
class LogFeedbackItem:
    timestamp: float
    event_type: str
    feedback_item: Optional[FeedbackItem] = None
    feedback_id: Optional[str] = None
    seconds_since_start: Optional[float] = None


class LoggerService:
    _CSV_HEADERS = {
        "system":   ["timestamp", "seconds_since_start", "level", "event_type", "data"],
        "feedback": ["timestamp", "seconds_since_start", "event_type", "feedback_id", "feedback_item"],
    }

    def __init__(
        self,
        system_level: str = "INFO",
        max_entries: int = 100000,
        log_base_path: Optional[str] = None,
    ):
        self.system_logs: List[LogEntry] = []
        self.feedback_logs: List[LogFeedbackItem] = []

        self.system_level = LogLevel[system_level.upper()]
        self.max_entries = max_entries
        self.start_time: Optional[float] = None

        self._file_paths: dict[str, Optional[Path]] = {
            "system": None,
            "feedback": None,
        }
        if log_base_path:
            base = Path(log_base_path)
            stem = base.parent / base.stem
            self._file_paths = {
                "system":   Path(str(stem) + "_system.csv"),
                "feedback": Path(str(stem) + "_feedback.csv"),
            }
            for category, path in self._file_paths.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                if not path.exists():
                    with open(path, "w", newline="") as f:
                        csv.writer(f).writerow(self._CSV_HEADERS[category])

    def set_start_time(self, start_time: Optional[float] = None) -> None:
        if start_time is None:
            start_time = datetime.now(timezone.utc).timestamp()
        self.start_time = float(start_time)

    def reset(self) -> None:
        self.system_logs.clear()
        self.feedback_logs.clear()
        self.start_time = None

    def set_level(self, level: str) -> None:
        self.system_level = LogLevel[level.upper()]

    def system(
        self,
        event_type: str,
        data: Optional[Dict[str, Any]] = None,
        level: str = "INFO",
    ) -> None:
        if not self._should_log(level):
            return

        ts = datetime.now(timezone.utc).timestamp()
        entry = LogEntry(
            timestamp=ts,
            level=level.upper(),
            event_type=event_type,
            data=data or {},
            seconds_since_start=self._seconds_since_start(ts),
        )

        self.system_logs.append(entry)
        self._print_log(entry)
        self._append_csv_row("system", self._entry_to_row(entry))

        if len(self.system_logs) > self.max_entries:
            self.system_logs = self.system_logs[-self.max_entries:]

    def feedback(
        self,
        event_type: str,
        feedback_item: FeedbackItem,
    ) -> None:
        ts = datetime.now(timezone.utc).timestamp()
        seconds_since_start = self._seconds_since_start(ts)

        entry = LogFeedbackItem(
            timestamp=ts,
            event_type=event_type,
            feedback_id=feedback_item.metadata.feedback_id if feedback_item.metadata else "unknown",
            feedback_item=feedback_item,
            seconds_since_start=seconds_since_start,
        )
        self.feedback_logs.append(entry)

        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        ts_str = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        sss = round(seconds_since_start, 3) if seconds_since_start is not None else ""
        self._append_csv_row("feedback", [
            ts_str,
            sss,
            entry.event_type,
            entry.feedback_id,
            json.dumps(json_safe(entry.feedback_item or {})),
        ])

        if len(self.feedback_logs) > self.max_entries:
            self.feedback_logs = self.feedback_logs[-self.max_entries:]

    def export_system_logs(self, filepath: str) -> bool:
        try:
            filepath = filepath if filepath.endswith(".csv") else f"{filepath}.csv"
            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "seconds_since_start", "level", "event_type", "data"])
                for entry in self.system_logs:
                    dt = datetime.fromtimestamp(entry.timestamp, tz=timezone.utc)
                    writer.writerow([
                        dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                        round(entry.seconds_since_start, 3) if entry.seconds_since_start is not None else "",
                        entry.level,
                        entry.event_type,
                        json.dumps(json_safe(entry.data)),
                    ])

            self._print_log(LogEntry(
                timestamp=datetime.now(timezone.utc).timestamp(),
                level="INFO",
                event_type="export_system_logs",
                data={"filepath": str(filepath), "count": len(self.system_logs)},
            ))
            return True
        except Exception as e:
            self._print_log(LogEntry(
                timestamp=datetime.now(timezone.utc).timestamp(),
                level="ERROR",
                event_type="export_system_logs_error",
                data={"error": str(e)},
            ))
            return False

    def export_feedback_logs(self, filepath: str) -> bool:
        try:
            filepath = filepath if filepath.endswith(".csv") else f"{filepath}.csv"
            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "seconds_since_start", "event_type", "feedback_id", "feedback_item"])
                for entry in self.feedback_logs:
                    dt = datetime.fromtimestamp(entry.timestamp, tz=timezone.utc)
                    writer.writerow([
                        dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                        round(entry.seconds_since_start, 3) if entry.seconds_since_start is not None else "",
                        entry.event_type,
                        entry.feedback_id,
                        json.dumps(json_safe(entry.feedback_item or {})),
                    ])

            self._print_log(LogEntry(
                timestamp=datetime.now(timezone.utc).timestamp(),
                level="INFO",
                event_type="export_feedback_logs",
                data={"filepath": str(filepath), "count": len(self.feedback_logs)},
            ))
            return True
        except Exception as e:
            self._print_log(LogEntry(
                timestamp=datetime.now(timezone.utc).timestamp(),
                level="ERROR",
                event_type="export_feedback_logs_error",
                data={"error": str(e)},
            ))
            return False

    # --- Internal Methods ---

    def _seconds_since_start(self, ts: float) -> Optional[float]:
        if self.start_time is None:
            return None
        return ts - self.start_time

    def _append_csv_row(self, category: str, row: list) -> None:
        path = self._file_paths.get(category)
        if path is None:
            return
        try:
            with open(path, "a", newline="") as f:
                csv.writer(f).writerow(row)
        except Exception:
            pass

    def _entry_to_row(self, entry: LogEntry) -> list:
        dt = datetime.fromtimestamp(entry.timestamp, tz=timezone.utc)
        ts_str = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        sss = round(entry.seconds_since_start, 3) if entry.seconds_since_start is not None else ""
        data_str = json.dumps(json_safe(entry.data)) if entry.data else ""
        return [ts_str, sss, entry.level, entry.event_type, data_str]

    def _should_log(self, level: str) -> bool:
        try:
            return LogLevel[level.upper()].value >= self.system_level.value
        except KeyError:
            return True

    def _print_log(self, entry: LogEntry) -> None:
        timestamp = datetime.fromtimestamp(entry.timestamp, tz=timezone.utc).strftime("%H:%M:%S")
        delta_str = f" +{entry.seconds_since_start:.3f}s" if entry.seconds_since_start is not None else ""

        colors = {
            "DEBUG": "\033[36m",
            "INFO": "\033[32m",
            "WARNING": "\033[33m",
            "ERROR": "\033[31m",
        }
        reset = "\033[0m"
        color = colors.get(entry.level, "")

        data_obj = json_safe(entry.data) if entry.data else None
        data_str = json.dumps(data_obj) if data_obj else ""

        print(f"{color}[{timestamp}{delta_str}] [{entry.level}] {entry.event_type}{reset} {data_str}", flush=True)


# Global logger instance
_logger: Optional[LoggerService] = None


def get_logger() -> LoggerService:
    global _logger
    if _logger is None:
        _logger = LoggerService()
    return _logger


def initialize_logger(
    system_level: str = "INFO",
    log_base_path: Optional[str] = None,
) -> LoggerService:
    global _logger
    _logger = LoggerService(
        system_level=system_level,
        log_base_path=log_base_path,
    )
    return _logger
