"""Pure BEFORE-only bounded context builder. No gold, patches or execution."""
from __future__ import annotations
import hashlib
from .m126_rank import tokens


def _n(text):
    return len(text.encode('utf-8'))


def _line(text, limit):
    if _n(text)<=limit:return text
    out=[]; used=0
    for char in text:
        b=_n(char)
        if used+b>max(0,limit-4):break
        out.append(char);used+=b
    return ''.join(out)+'…\n'


def excerpt(source, symbol, title, available):
    """Return (annotated OLD source, inclusive source-line ranges)."""
    lines=source.splitlines(keepends=True)
    start,end=symbol['start'],symbol['end']
    if start<1 or end>len(lines) or start>end or available<40:
        return '',[]
    def rendered(i):return f'L{i:05d} '+lines[i-1].rstrip('\r\n')+'\n'
    all_lines=''.join(rendered(i) for i in range(start,end+1))
    if _n(all_lines)<=available:return all_lines,[[start,end]]
    query=set(tokens(title))
    # Line scores use ONLY issue-title lexical overlap with OLD code.
    scores=[]
    for line in range(start,end+1):
        hits=set(tokens(lines[line-1]))&query
        scores.append((len(hits),-abs(line-start),-line,line))
    best=max(scores)[-1] if scores else start
    # Always show signature if possible. Then a concise contiguous window at best match.
    out=''; positions=[]
    line1=rendered(start)
    if _n(line1)<available//2:
        out=line1;positions.append(start)
    remaining=available-_n(out)
    if remaining<24:return out,[[start,start]] if out else []
    # Starting from the best matching line, expand forward and then backward locally.
    center=best
    indexes=[center]
    k=1
    while center-k>=start or center+k<=end:
        if center+k<=end:indexes.append(center+k)
        if center-k>=start:indexes.append(center-k)
        k+=1
    accepted=[]
    for i in indexes:
        if i==start and out:continue
        s=rendered(i)
        if _n(s)>remaining:
            if not accepted and not out:
                s=_line(s,remaining)
                if _n(s)<=remaining:
                    accepted.append((i,s));remaining-=_n(s)
            continue
        accepted.append((i,s));remaining-=_n(s)
        if remaining<20:break
    accepted.sort()
    out+= ''.join(s for _,s in accepted)
    positions += [i for i,_ in accepted]
    positions=sorted(set(positions))
    ranges=[]
    for i in positions:
        if not ranges or i>ranges[-1][1]+1:ranges.append([i,i])
        else:ranges[-1][1]=i
    return out,ranges


def build(title,old_sources,ranked_symbols,budget=4096,max_scopes=3):
    """Never receives gold. Output strings are OLD source only plus provenance markers."""
    if not isinstance(budget,int) or budget<256 or budget>16384:
        raise ValueError('M128_CONTEXT_BUDGET_INVALID')
    if not isinstance(title,str) or not title.strip() or _n(title)>4096:
        raise ValueError('M128_CONTEXT_TITLE_INVALID')
    if not isinstance(max_scopes,int) or max_scopes<1 or max_scopes>5:
        raise ValueError('M128_SCOPE_COUNT_INVALID')
    head='ISSUE (CURRENT TITLE, HISTORIC WORDING UNVERIFIED): '+title+'\nOLD PYTHON SOURCE, NONEXECUTABLE EXCERPTS:\n'
    if _n(head)>=budget-32:
        # Never silently truncate the issue title.
        return {'status':'ISSUE_HEADER_EXCEEDS_BUDGET','budget_bytes':budget,'used_bytes':0,
                'text':'','ranges':[],'source_sha256':None}
    chosen=ranked_symbols[:max_scopes]
    if not chosen:
        return {'status':'NO_FUNCTION_CANDIDATES','budget_bytes':budget,
                'used_bytes':0,'text':'','ranges':[],'source_sha256':None}
    text=head;ranges=[]
    for idx,scope in enumerate(chosen):
        path=scope['path']
        source=old_sources.get(path)
        if source is None:raise ValueError('M128_RANKED_SCOPE_MISSING_FROM_OLD_TREE')
        if scope['old_source_sha256']!=hashlib.sha256(source.encode('utf-8')).hexdigest():
            raise ValueError('M128_RANKED_SCOPE_SOURCE_SHA_MISMATCH')
        remaining_scopes=len(chosen)-idx
        section=f"FILE: {path}\nSCOPE: {scope['qualname']} OLD LINES {scope['start']}-{scope['end']}\n"
        if _n(text)+_n(section)+40>budget:break
        text+=section
        available=(budget-_n(text))//remaining_scopes
        segment,selected=excerpt(source,scope,title,available)
        if not segment:
            continue
        text+=segment
        ranges.append({'path':path,'qualname':scope['qualname'],
                       'start':scope['start'],'end':scope['end'],
                       'selected_line_ranges':selected})
    if _n(text)>budget:raise ValueError('M128_CONTEXT_OVERSIZE_INTERNAL')
    return {'status':'OLD_SCOPE_EXCERPTS' if ranges else 'NO_SNIPPET_FIT',
            'budget_bytes':budget,'used_bytes':_n(text),'text':text,
            'ranges':ranges,
            'source_sha256':hashlib.sha256(text.encode('utf-8')).hexdigest()}
