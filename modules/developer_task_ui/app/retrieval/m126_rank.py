"""Deterministic text retrieval over BEFORE-ONLY whole-tree Python files.

This module has NO access to reference fixes, after snapshots, test names,
patches, M119 cards, or Git. Its input is one issue title and a mapping of
production filenames -> UTF-8/PEP263-compatible decoded old source texts.
"""
from __future__ import annotations
import collections
import math
import re

STOP={
 'a','an','the','to','of','in','on','at','by','from','for','and','or','is','are','be','with',
 'when','if','not','than','that','this','it','as','can','does','do','did','after','before',
 'return','def','class','self','import','from','try','except','pass','none','true','false',
 'python','py','error','issue','problem','using','use','code','new','old','bug',
 'has','have','got','get','its','will','should','could','would','only','some','into',
 'while','without','one','two','my','but','what','why','how','cannot','cant','still',
}
WORD=re.compile(r'[A-Za-z][A-Za-z0-9_]*')
CAMEL=re.compile(r'([a-z0-9])([A-Z])')


def tokens(text):
    # Statically analyze characters, never import or evaluate supplied source.
    for match in WORD.finditer(text):
        word=CAMEL.sub(r'\1 \2',match.group(0))
        for piece in re.split(r'[_\W\d]+',word):
            t=piece.casefold()
            if len(t)>1 and t not in STOP and len(t)<=48:
                yield t


def rank_title_only(title, before_files, top_n=10):
    """Pure search: no after/fix data accepted or read here.

    before_files is {full_prod_source_path: source_text}. File contents may be
    different encodings but must already have been decoded strictly upstream.
    """
    if not isinstance(title,str) or not title.strip() or len(title)>2048:
        raise ValueError('M126_QUERY_INVALID')
    if not isinstance(before_files,dict) or not before_files or len(before_files)>800:
        raise ValueError('M126_FILES_LIMIT')
    if not isinstance(top_n,int) or top_n<1 or top_n>50:
        raise ValueError('M126_TOP_N_INVALID')
    query=list(dict.fromkeys(tokens(title)))
    tf={};path_tf={};lengths={}
    for path,source in before_files.items():
        if not isinstance(path,str) or not path.endswith('.py') or '\\' in path or '..' in path.split('/'):
            raise ValueError('M126_PATH_INVALID')
        if not isinstance(source,str) or len(source)>2_500_000:
            raise ValueError('M126_SOURCE_INVALID')
        counter=collections.Counter(tokens(source))
        tf[path]=counter
        path_tf[path]=collections.Counter(tokens(path.replace('/',' ')))
        lengths[path]=sum(counter.values())
    total=len(tf);avg=max(1,sum(lengths.values())/total)
    df=collections.Counter(w for c in tf.values() for w in c)
    dfpath=collections.Counter(w for c in path_tf.values() for w in c)
    def textscore(p):
        size=lengths[p];s=0.0
        for q in query:
            n=tf[p][q]
            if not n:continue
            idf=math.log(1+(total-df[q]+.5)/(df[q]+.5))
            s+=idf*n*2.2/(n+1.2*(.25+.75*size/avg))
        return s
    def pathscore(p):
        s=0.0
        for q in query:
            n=path_tf[p][q]
            if n:
                idf=math.log(1+(total-dfpath[q]+.5)/(dfpath[q]+.5))
                s+=2.0*idf*min(n,2)
        return s
    primary=[(p,textscore(p)+pathscore(p)) for p in tf]
    primary.sort(key=lambda v:(-v[1],v[0]))
    path_only=sorted(tf,key=lambda p:(-pathscore(p),p))
    alphabetical=sorted(tf)
    def top_list(items):
        return [{'path':p,'score':round(s,7),
                 'matching_title_tokens':[t for t in query if tf[p][t] or path_tf[p][t]]}
                for p,s in items[:top_n]]
    return {'schema':'SKYNETVS_M126_TITLE_ONLY_RANK_V1',
            'title_token_count':len(query),'candidate_count':total,
            'nonzero_scores':sum(s>0 for _,s in primary),
            'retrieval_confidence':'LEXICAL_MATCH_EXISTS' if primary[0][1]>0 else 'NO_LEXICAL_MATCH',
            'bm25_title_code_path':top_list(primary),
            'path_only':[{'path':p,'score':round(pathscore(p),7)} for p in path_only[:top_n]],
            'alphabetic_baseline':alphabetical[:top_n],
            'no_gold_or_after_consumed':True}


if __name__=='__main__':
    import argparse,json,pathlib
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',required=True)
    parser.add_argument('--output',required=True)
    a=parser.parse_args()
    packet=json.loads(pathlib.Path(a.input).read_text(encoding='utf-8'))
    if sorted(packet)!=['before_sources','issue_title_current']:
        raise ValueError('M126_RANK_INPUT_MUST_HAVE_ONLY_TITLE_AND_OLD_SOURCES')
    result=rank_title_only(packet['issue_title_current'],packet['before_sources'])
    pathlib.Path(a.output).write_text(json.dumps(result,sort_keys=True,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
