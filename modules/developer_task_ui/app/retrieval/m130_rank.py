"""M130 independent BEFORE-only ranker; accepts EXACTLY issue title + full OLD tree.

No after sources, tests, patch, card, or gold can enter this process.
Only stdlib AST parsing and string operations on Python text; never execute source.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys
import warnings

from .m126_rank import rank_title_only
from .m127_symbol import rank_symbols,tokens
from .m130_context import build_context


def candidate_id(c):
    return (c['path'],c['kind'],c['qualname'],c['start'],c['end'])


def modules_from_source(path,source,window=24,stride=18):
    """Read-only old module/class/decorator regions, excluding all AST function bodies."""
    with warnings.catch_warnings(record=True):
        warnings.simplefilter('always',SyntaxWarning)
        tree=ast.parse(source,filename=path)
    lines=source.splitlines(keepends=True)
    covered=[False]*(len(lines)+1)
    for n in ast.walk(tree):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
            if n.end_lineno is None or n.lineno<1 or n.end_lineno>len(lines):
                raise ValueError('M130_INVALID_FUNCTION_AST_EXTENT')
            for i in range(n.lineno,n.end_lineno+1):covered[i]=True
    digest=hashlib.sha256(source.encode('utf-8')).hexdigest()
    output=[]
    i=1
    while i<=len(lines):
        if covered[i]:i+=1;continue
        begin=i
        while i<=len(lines) and not covered[i]:i+=1
        end=i-1
        if not any(l.strip() and not l.lstrip().startswith('#') for l in lines[begin-1:end]):
            continue
        cursor=begin
        while cursor<=end:
            stop=min(end,cursor+window-1)
            block=''.join(lines[cursor-1:stop])
            if any(l.strip() and not l.lstrip().startswith('#') for l in lines[cursor-1:stop]):
                output.append(dict(path=path,qualname=f'<module:{cursor}-{stop}>',kind='ModuleSpan',
                                   start=cursor,end=stop,scope_bytes=len(block.encode('utf-8')),
                                   old_source_sha256=digest,
                                   snippet_sha256=hashlib.sha256(block.encode('utf-8')).hexdigest(),
                                   _text=block))
            if stop==end:break
            cursor+=stride
        if len(output)>4000:raise ValueError('M130_MODULE_SPAN_COUNT_LIMIT')
    return output


def module_rank(title,scanned):
    windows=[];parse_fail=[]
    for path in sorted(scanned):
        src=scanned[path]
        try:
            windows+=modules_from_source(path,src)
        except (SyntaxError,ValueError,RecursionError) as e:
            parse_fail.append(dict(path=path,reason=type(e).__name__))
    if len(windows)>4000:raise ValueError('M130_MODULE_SPAN_COUNT_LIMIT')
    if not windows:return [],parse_fail,0
    query=list(dict.fromkeys(tokens(title)))
    content=[Counter(tokens(w['_text'])) for w in windows]
    names=[Counter(tokens(w['path'])) for w in windows]
    df=Counter(t for c in content for t in c)
    path_df=Counter(t for c in names for t in c)
    lengths=[sum(c.values()) for c in content]
    n=len(windows);avg=max(1.0,sum(lengths)/n)
    for i,w in enumerate(windows):
        score=0.0
        for t in query:
            cnt=content[i][t]
            if cnt:
                idf=math.log(1+(n-df[t]+0.5)/(df[t]+0.5))
                score+=idf*cnt*2.2/(cnt+1.2*(0.25+0.75*lengths[i]/avg))
            if names[i][t]:
                score+=0.5*math.log(1+(n-path_df[t]+0.5)/(path_df[t]+0.5))
        w['module_bm25_score']=round(score,7)
        del w['_text']
    windows.sort(key=lambda c:(-c['module_bm25_score'],c['path'],c['start'],c['end']))
    return windows[:100],parse_fail,len(windows)


def interleave_3_to_1(functions,modules,limit=100):
    """Fixed, label-free mixing (not tuned on these 14 known fixes)."""
    out=[];i=j=0
    while len(out)<limit and (i<len(functions) or j<len(modules)):
        for _ in range(3):
            if i<len(functions) and len(out)<limit:
                out.append(functions[i]);i+=1
        if j<len(modules) and len(out)<limit:out.append(modules[j]);j+=1
        if i>=len(functions):
            while j<len(modules) and len(out)<limit:out.append(modules[j]);j+=1
    if len(set(map(candidate_id,out)))!=len(out):raise ValueError('M130_CANDIDATE_DUPLICATE')
    return out


def rank(title,old_sources):
    # Strictly BEFORE-only: ranker is never given gold, after, fixed paths or tests.
    if not isinstance(old_sources,dict) or not old_sources:
        raise ValueError('M130_OLD_TREE_EMPTY')
    if not isinstance(title,str) or not title.strip() or len(title)>2048:
        raise ValueError('M130_TITLE_INVALID')
    files=rank_title_only(title,old_sources,top_n=10)
    selected={};used=0;skipped=[]
    for row in files['bm25_title_code_path']:
        p=row['path'];b=len(old_sources[p].encode('utf-8'))
        if used+b>6_000_000:
            skipped.append(dict(path=p,reason='M128_COMPATIBLE_SCOPE_SCAN_BYTES_LIMIT'))
            continue
        selected[p]=old_sources[p];used+=b
    if not selected:raise ValueError('M130_NO_SCOPE_FILES_WITHIN_LIMIT')
    sym=rank_symbols(title,selected,limit=100)
    functions=[{**c,'kind':c['kind']} for c in sym['bm25_name_body']]
    modules,mod_parse,nmodules=module_rank(title,selected)
    combined=interleave_3_to_1(functions,modules,limit=100)
    contexts={str(b):build_context(title,old_sources,combined,b,max_candidates=10)
              for b in (4096,8192)}
    return dict(schema='SKYNETVS_M130_BEFORE_ONLY_CANDIDATE_POOL_V1',
                file_candidates_full_tree=files['candidate_count'],
                file_ranks=files,
                scanned_paths=list(selected),scanned_total_bytes=used,scan_skipped=skipped,
                function_candidates_total=sym['symbol_candidates'],module_candidates_total=nmodules,
                function_parse_diagnostics=sym['parse_diagnostics'],module_parse_diagnostics=mod_parse,
                function_rank_top100=functions,module_rank_top100=modules,
                mixed_3F1M_rank_top100=combined,contexts_local_only=contexts,
                no_after_gold_test_patch_or_fix_path_consumed=True,
                oracle_file_preselection=False,trained_model=False,
                title_original_historical_text_verified=False)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',required=True);p.add_argument('--output',required=True)
    args=p.parse_args()
    data=json.loads(Path(args.input).read_text(encoding='utf-8'))
    if sorted(data)!=['before_sources','issue_title_current']:
        raise ValueError('M130_RANK_INPUT_CONTRACT_VIOLATION')
    out=rank(data['issue_title_current'],data['before_sources'])
    Path(args.output).write_text(json.dumps(out,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    print('M130_RANK_COMPLETED=TRUE; FILES='+str(out['file_candidates_full_tree']))

if __name__=='__main__':main()
