from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Iterable, Iterator
import uuid


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(slots=True)
class JsonlSessionWriter:
    path: Path
    session_id: str

    @classmethod
    def create(
        cls,
        output_dir: str | os.PathLike[str],
        expected_nodes: list[int],
        dsp_config: dict,
        ml_mode: str = "disabled",
        runtime_version: str = "m1",
        host_info: dict | None = None,
        firmware_metadata: dict | None = None,
    ) -> "JsonlSessionWriter":
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        session_id = uuid.uuid4().hex
        path = output_path / f"{session_id}.jsonl"
        writer = cls(path=path, session_id=session_id)
        writer.write(
            {
                "record_type": "session_header",
                "schema_version": 1,
                "session_id": session_id,
                "started_at": utc_now_iso(),
                "expected_nodes": expected_nodes,
                "dsp_config": dsp_config,
                "ml_mode": ml_mode,
                "runtime_version": runtime_version,
                "host_info": host_info or {},
                "firmware_metadata": firmware_metadata or {},
            }
        )
        return writer

    def write(self, record: dict) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, separators=(",", ":")) + "\n")

    def close(self, summary: dict | None = None) -> None:
        self.write(
            {
                "record_type": "session_footer",
                "session_id": self.session_id,
                "ended_at": utc_now_iso(),
                "summary": summary or {},
            }
        )


def read_jsonl_records(path: str | os.PathLike[str]) -> Iterator[dict]:
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)
