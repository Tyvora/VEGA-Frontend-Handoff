"""Bounded keyset retrieval utility. Enable only after server ordering verification."""
from typing import Callable, Any

def retrieve_batches(fetch: Callable, max_pages: int = 10) -> tuple[list[dict[str,Any]],bool,str]:
    rows=[]; seen=set(); cursor=None
    for _ in range(max_pages):
        try: batch,overflow=fetch(cursor)
        except Exception as exc: return rows,False,str(exc)
        if not batch: return rows,not overflow,'empty final page' if not overflow else 'overflow without progress'
        keys=[r.get('artifactid') for r in batch]
        if any(not isinstance(k,str) for k in keys): return rows,False,'missing identity'
        if keys!=sorted(keys): return rows,False,'unstable ordering'
        for row,key in zip(batch,keys):
            if key not in seen: rows.append(row); seen.add(key)
        next_cursor=keys[-1]
        if cursor is not None and next_cursor<=cursor: return rows,False,'cursor did not advance'
        cursor=next_cursor
        if not overflow: return rows,True,'final page'
    return rows,False,'page limit'
