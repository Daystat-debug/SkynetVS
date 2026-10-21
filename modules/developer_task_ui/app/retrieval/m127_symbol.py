"""Read-only, deterministic lexical symbol ranker. ONLY accepts current issue title + old code.

No M119 cards, after code, patches, tests, fixed paths or gold symbols in this module.
Never import/execute input Python code. Uses the standard-library ast parser only.
"""
from __future__ import annotations
import ast
from collections import Counter
import hashlib
import math
import re
import warnings

STOP = frozenset('a an the to of in on at by from for and or is are be with when if not than that this it as can does do did after before return def class self import try except pass none true false python py error issue problem using use code new old bug has have got get its will should could would only some into while without one two my but what why how cannot cant still'.split())
WORD = re.compile(r'[A-Za-z][A-Za-z0-9_]*')
CAMEL = re.compile(r'([a-z0-9])([A-Z])')


def tokens(text):
    for match in WORD.finditer(text):
        word = CAMEL.sub(r'\1 \2', match.group(0))
        for part in re.split(r'[_\W\d]+', word):
            t=part.casefold()
            if 1 < len(t) <= 48 and t not in STOP:
                yield t


def extract_symbols(old_sources):
    """Input mapping path -> decoded BEFORE source text; no references to after data."""
    if not isinstance(old_sources,dict) or not old_sources or len(old_sources)>24:
        raise ValueError('M127_OLD_SOURCES_INVALID')
    if sum(len(v.encode('utf-8')) if isinstance(v,str) else 10000000 for v in old_sources.values())>6000000:
        raise ValueError('M127_INPUT_TOO_LARGE')
    out=[]; failures=[]
    for path,src in sorted(old_sources.items()):
        if not isinstance(path,str) or not path.endswith('.py') or '\\' in path or '\x00' in path or path.startswith('/') or '..' in path.split('/'):
            raise ValueError('M127_OLD_SOURCE_PATH_INVALID')
        if not isinstance(src,str) or len(src)>1500000:
            raise ValueError('M127_OLD_SOURCE_INVALID')
        try:
            with warnings.catch_warnings(record=True) as nonfatal:
                warnings.simplefilter('always',SyntaxWarning)
                tree=ast.parse(src, filename=path)
            for warning in nonfatal:
                failures.append({'path':path,'reason':'NONFATAL_SYNTAX_WARNING',
                                 'line':getattr(warning,'lineno',None)})
        except SyntaxError as e:
            failures.append({'path':path,'reason':'SYNTAX_NOT_PARSED','line':e.lineno});continue
        lines=src.splitlines(keepends=True)
        def walk(node,prefix=()):
            for child in ast.iter_child_nodes(node):
                pref=prefix
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    pref=(*prefix,child.name)
                if isinstance(child,(ast.FunctionDef,ast.AsyncFunctionDef)):
                    start=child.lineno;end=child.end_lineno
                    if end is None or end<start or end>len(lines):
                        raise ValueError('M127_INVALID_AST_RANGE')
                    snippet=''.join(lines[start-1:end])
                    out.append({'path':path,'qualname':'.'.join(pref),'kind':type(child).__name__,
                                'start':start,'end':end,
                                'scope_bytes':len(snippet.encode('utf-8')),
                                'old_source_sha256':hashlib.sha256(src.encode('utf-8')).hexdigest(),
                                'snippet_sha256':hashlib.sha256(snippet.encode('utf-8')).hexdigest(),
                                '_source':snippet})
                walk(child,pref)
        walk(tree)
    if len(out)>3500:raise ValueError('M127_SYMBOL_LIMIT')
    return out,failures


def rank_symbols(issue_title,old_sources,limit=40):
    if not isinstance(issue_title,str) or not issue_title.strip() or len(issue_title)>2048:
        raise ValueError('M127_TITLE_INVALID')
    if not isinstance(limit,int) or limit<1 or limit>100:
        raise ValueError('M127_TOP_LIMIT_INVALID')
    symbols,parse_errors=extract_symbols(old_sources)
    query=list(dict.fromkeys(tokens(issue_title)))
    term_freqs=[Counter(tokens(s['_source'])) for s in symbols]
    len_s=[sum(c.values()) for c in term_freqs]
    n=max(1,len(symbols));avg=max(1,sum(len_s)/n)
    df=Counter(word for c in term_freqs for word in c)
    names=[Counter(tokens(s['qualname'])) for s in symbols]
    paths=[Counter(tokens(s['path'])) for s in symbols]
    name_df=Counter(t for c in names for t in c)
    path_df=Counter(t for c in paths for t in c)
    rows=[]
    for i,s in enumerate(symbols):
        content_score=0.0; name_score=0.0
        for t in query:
            k=term_freqs[i][t]
            if k:
                idf=math.log(1+(n-df[t]+.5)/(df[t]+.5))
                content_score+=idf*k*2.2/(k+1.2*(.25+.75*len_s[i]/avg))
            if names[i][t]:
                name_score+=3.0*math.log(1+(n-name_df[t]+.5)/(name_df[t]+.5))
            if paths[i][t]:
                name_score+=0.5*math.log(1+(n-path_df[t]+.5)/(path_df[t]+.5))
        ident={k:s[k] for k in ('path','qualname','kind','start','end','scope_bytes','old_source_sha256','snippet_sha256')}
        row={**ident,'bm25_name_body_score':round(content_score+name_score,7),
             'name_path_only_score':round(name_score,7)}
        rows.append(row)
    def order(key):
        return sorted(rows,key=lambda s:(-s[key],s['path'],s['start'],s['end'],s['qualname']))
    raw_order=sorted(rows,key=lambda s:(s['path'],s['start'],s['end'],s['qualname']))
    def pick(items):
        return [dict(s) for s in items[:limit]]
    return {'schema':'SKYNETVS_M127_SYMBOL_RETRIEVAL_V1','symbol_candidates':len(rows),
            'source_file_count':len(old_sources),'query_token_count':len(query),'parse_diagnostics':parse_errors,
            'bm25_name_body':pick(order('bm25_name_body_score')),
            'name_path_only':pick(order('name_path_only_score')),
            'source_order':pick(raw_order),
            'only_old_source_and_current_title_used':True,'oracle_file_conditional':True,
            'no_after_or_gold_consumed':True}
