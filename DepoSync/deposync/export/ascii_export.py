from typing import List
from deposync.models import Line

def write(lines: List[Line], path: str) -> int:
    n = 0
    with open(path, 'w', encoding='utf-8', newline='') as f:
        for l in lines:
            if l.timestamp_sec is None:
                f.write(f"              {l.page:05d}:{l.line_num:02d}  {l.text}\r\n")
            else:
                t = l.timestamp_sec
                ts = f"{int(t//3600):02d}:{int((t%3600)//60):02d}:{t%60:06.3f}"
                f.write(f"{ts}  {l.page:05d}:{l.line_num:02d}  {l.text}\r\n")
                n += 1
    return n
