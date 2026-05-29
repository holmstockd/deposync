from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

@dataclass
class Line:
    page:          int
    line_num:      int
    text:          str
    timestamp_sec: Optional[float] = None
    confidence:    float = 0.0
    manually_set:  bool  = False

    @property
    def hms(self) -> str:
        if self.timestamp_sec is None:
            return ""
        t = self.timestamp_sec
        h, m, s = int(t//3600), int((t%3600)//60), t%60
        return f"{h:02d}:{m:02d}:{s:06.3f}"

@dataclass
class Word:
    text:  str
    start: float
    end:   float


@dataclass
class Exhibit:
    """An exhibit referenced in a transcript and/or a linked exhibit file."""
    label:       str = ""
    number:      str = ""
    page:        Optional[int] = None
    line_num:    Optional[int] = None
    ref_count:   int = 0
    file_path:   str = ""
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Exhibit":
        fields = {
            "label", "number", "page", "line_num",
            "ref_count", "file_path", "description",
        }
        return cls(**{k: v for k, v in (d or {}).items() if k in fields})


def line_to_dict(line: "Line") -> Dict[str, Any]:
    """Serialize a Line for JSON storage."""
    return {
        "page":          line.page,
        "line_num":      line.line_num,
        "text":          line.text,
        "timestamp_sec": line.timestamp_sec,
        "confidence":    line.confidence,
        "manually_set":  line.manually_set,
    }


def line_from_dict(d: Dict[str, Any]) -> "Line":
    """Reconstruct a Line from stored JSON."""
    return Line(
        page=d.get("page", 0),
        line_num=d.get("line_num", 0),
        text=d.get("text", ""),
        timestamp_sec=d.get("timestamp_sec"),
        confidence=d.get("confidence", 0.0),
        manually_set=d.get("manually_set", False),
    )
