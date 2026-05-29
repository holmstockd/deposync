import os, re, zipfile
from typing import List
from deposync.models import Line

def write(lines: List[Line], path: str,
          witness: str = 'Deponent',
          video_file: str = '',
          video_dur_sec: float = 0.0,
          exhibits=None) -> int:
    exhibits = exhibits or []
    safe   = re.sub(r'[^\w]', '_', witness)
    ptf_fn = f'{safe}.ptf'
    pages  = sorted(set(l.page for l in lines))

    # Build text entries and index
    text_entries = []
    line_idx     = {}
    seq          = 0
    prev_pg      = None
    for l in lines:
        if l.page != prev_pg:
            if prev_pg is not None:
                text_entries.append('fmt=pb')
            prev_pg = l.page
        line_idx[(l.page, l.line_num)] = seq
        text_entries.append(f'{seq}={l.text}')
        seq += 1
        text_entries.append(f'{seq}=')
        seq += 1
    if prev_pg is not None:
        text_entries.append('fmt=pb')

    pagenames = ','.join(str(p) for p in pages)
    # Build linenames
    ln_parts = []
    prev_pg  = None
    for l in lines:
        if l.page != prev_pg:
            prev_pg = l.page
        ln_parts.append(str(l.line_num))
        ln_parts.append('')

    # Exhibit annotations: one entry per linked exhibit, anchored at the line
    # where it is first referenced and hyperlinked to the bundled file.
    annot_entries = []
    bundled = []
    linked_exh = [e for e in exhibits if getattr(e, 'file_path', '')]
    for n_e, e in enumerate(linked_exh):
        fi = line_idx.get((e.page, e.line_num)) if e.page else None
        if fi is None:
            continue
        fname = os.path.basename(e.file_path)
        annot_entries += [
            'begin=Annotation',
            f'id={n_e}',
            f'lineindex={fi}',
            f'text={e.label}',
            f'link=Exhibits/{fname}',
            'end=Annotation',
        ]
        bundled.append(e.file_path)

    ptf = '\r\n'.join([
        'begin=Head', 'type=ptf', 'version=1.3', 'end=Head',
        'begin=CaseInfo', 'path=', 'name=', 'end=CaseInfo',
        'begin=TranscriptInfo',
        f'name={witness}',
        'begin=comments', 'end=comments',
        f'pagenames={pagenames}',
        f'linenames={",".join(ln_parts)}',
        f'firstpage={pages[0] if pages else 1}',
        'pagelen=25',
        'end=TranscriptInfo',
        'begin=ActiveIssues', 'end=ActiveIssues',
        'begin=DeletedIssues', 'end=DeletedIssues',
        'begin=Annotations',
    ] + annot_entries + [
        'end=Annotations',
        'begin=Text',
    ] + text_entries + ['end=Text']) + '\r\n'

    vdur = int(video_dur_sec * 1000)
    vf   = video_file or 'deposition.mpg'
    mf_lines = [
        '<XMEF LastUpdatedXMELEdition="STD" Version="1.0">',
        '  <Videos>',
        f'    <Video Filename="{vf}" Duration="{vdur}" Offset="0"/>',
        '  </Videos>',
        '  <VideoTimeCodes>',
    ]
    n = 0
    for l in lines:
        if l.timestamp_sec is None:
            continue
        fi = line_idx.get((l.page, l.line_num))
        if fi is None:
            continue
        ms = int(l.timestamp_sec * 1000)
        mf_lines.append(
            f'    <VideoTimeCode AbsolutePosition="{ms}" LineIndex="{fi}"/>')
        n += 1
    mf_lines += ['  </VideoTimeCodes>', '</XMEF>']
    manifest = '\r\n'.join(mf_lines) + '\r\n'

    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(ptf_fn, ptf.encode('utf-8'))
        zf.writestr('XMEFManifest.xml', manifest.encode('utf-8'))
        # Bundle the actual exhibit files so they travel with the export.
        for fp in bundled:
            try:
                zf.write(fp, f'Exhibits/{os.path.basename(fp)}')
            except Exception:
                pass
    return n

