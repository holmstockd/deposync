from dataclasses import dataclass
from typing import Optional

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
