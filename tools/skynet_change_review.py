"""Compare two authorized source captures. Only the interactive caller receives code previews."""
import ast
from difflib import SequenceMatcher
from functools import cached_property

import skynet_core_explain as app
import skynet_data_flow as flow
from skynet_working_tree import WorkingSources

DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
LABELS = {"function":"Определение", "signature":"Заголовок или декораторы", "condition":"Условие",
          "call":"Вызов", "value":"Значение", "field":"Поле результата", "statement":"Инструкция",
          "text":"Текст при совпадающем AST", "encoding":"Представление текста"}


def shape(node):
    return ast.dump(node, include_attributes=False)


def preview(node):
    text = ast.unparse(node).split("\n", 1)[0]
    return text if len(text) <= 180 else text[:177] + "…"


def logical_lines(text):
    lines = text.replace("\r\n","\n").replace("\r","\n").split("\n")
    if lines[-1] == "":
        lines.pop()
    return lines


def equality_change(old, new):
    if not (isinstance(old,ast.Compare) and isinstance(new,ast.Compare)
            and len(old.ops) == len(new.ops) == 1 and shape(old.left) == shape(new.left)
            and shape(old.comparators[0]) == shape(new.comparators[0])):
        return {}
    ops = type(old.ops[0]),type(new.ops[0])
    if set(ops) in ({ast.Gt,ast.GtE},{ast.Lt,ast.LtE}):
        return {"numeric_equality_now_true":ops[1] in (ast.GtE,ast.LtE)}
    return {}


def checked_ref(src, path, lo, hi):
    ref = app.lab.cli.calls.cited(src,path,lo,hi)
    return app.checked_item(src,ref)["locator"]


def describe_side(src, path, node):
    if node is None:
        return None
    first = min([node.lineno, *(n.lineno for n in getattr(node, "decorator_list", []))])
    return dict(expression=preview(node), ref=checked_ref(src,path,first,node.end_lineno))


class Changes:
    def __init__(self, path, head, work):
        self.path, self.head, self.work = path, head, work
        self.rows = []

    def returned_fields(self, tree, owner, expr):
        if isinstance(expr,ast.Dict):
            return flow.fields(None,expr)
        if len(owner) == 1 and isinstance(expr,ast.Call):
            defs = [n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name == owner[0]]
            if len(defs) == 1:
                return flow.fields(flow.Function(self.path,tree,defs[0]),expr)
        return {}

    def emit(self, kind, owner, left, right, **details):
        if len(self.rows) >= 48:
            raise app.Rejected("review_budget")
        self.rows.append(dict(kind=kind,owner=owner,
                              before=describe_side(self.head,self.path,left),
                              after=describe_side(self.work,self.path,right), **details))

    def statements(self, left, right, owner):
        # Equal subtrees align even when their line numbers shift. Unpaired blocks remain additions/removals.
        if len(left) * len(right) > 1_000_000:
            raise app.Rejected("review_budget")
        matcher = SequenceMatcher(None, [shape(n) for n in left], [shape(n) for n in right], autojunk=False)
        for tag,a,b,c,d in matcher.get_opcodes():
            if tag == "equal":
                continue
            if tag == "replace" and b-a == d-c:
                for old,new in zip(left[a:b], right[c:d]):
                    self.statement(old,new,owner)
            else:
                for old in left[a:b]:
                    self.single(old,owner,removed=True)
                for new in right[c:d]:
                    self.single(new,owner,removed=False)

    def single(self, node, owner, *, removed):
        defined = isinstance(node, DEFINITIONS)
        name = (*owner,node.name) if defined else owner
        details = {}
        if defined:
            other = self.new_tree if removed else self.old_tree
            if not any(isinstance(n,DEFINITIONS) and n.name == node.name for n in ast.walk(other)):
                details["definition_delta"] = "removed" if removed else "added"
        self.emit("function" if defined else "statement",name,node if removed else None,None if removed else node,**details)

    def statement(self, left, right, owner):
        if isinstance(left, DEFINITIONS) or isinstance(right, DEFINITIONS):
            if type(left) != type(right) or left.name != right.name:
                self.single(left,owner,removed=True)
                self.single(right,owner,removed=False)
                return
            owner = (*owner,left.name)
            def header(n):
                return ast.dump(type(n)(**{k:([] if k == "body" else v) for k,v in ast.iter_fields(n)}))
            if header(left) != header(right):
                self.emit("signature",owner,left,right)
            self.statements(left.body,right.body,owner)
            return
        if isinstance(left,(ast.If,ast.While)) and type(left) == type(right):
            if shape(left.test) != shape(right.test):
                self.emit("condition",owner,left.test,right.test,**equality_change(left.test,right.test))
            self.statements(left.body,right.body,owner)
            self.statements(left.orelse,right.orelse,owner)
            return
        # Descend through an unchanged enclosing header, e.g. an if inside a for/with/try.
        # If handlers/patterns also changed, keep a conservative statement-level diff.
        suites = ("body","orelse","finalbody")
        if type(left) == type(right) and isinstance(getattr(left,"body",None),list):
            def shell(node):
                return shape(type(node)(**{k:([] if k in suites else v) for k,v in ast.iter_fields(node)}))
            if shell(left) == shell(right):
                for k in suites:
                    self.statements(getattr(left,k,[]),getattr(right,k,[]),owner)
                return
        if isinstance(left,ast.Return) and isinstance(right,ast.Return) and type(left.value) == type(right.value):
            keys = self.returned_fields(self.old_tree,owner,left.value)
            other = self.returned_fields(self.new_tree,owner,right.value)
            if keys and list(keys) == list(other):
                changed = False
                for key,(_,old) in keys.items():
                    new = other[key][1]
                    if shape(old) != shape(new):
                        self.emit("field",owner,old,new,field=key)
                        changed = True
                if changed:
                    return
        if isinstance(left,(ast.Assign,ast.Return,ast.Expr)) and type(left) == type(right):
            if not isinstance(left,ast.Assign) or list(map(shape,left.targets)) == list(map(shape,right.targets)):
                old, new = left.value, right.value
                if old is not None and new is not None:
                    details = {}
                    if (isinstance(new,ast.Call) and isinstance(new.func,ast.Name)):
                        details["call_expression"] = dict(name=new.func.id,line=new.lineno,column=new.col_offset,
                            end_line=new.end_lineno,end_column=new.end_col_offset)
                    if isinstance(left,ast.Assign):
                        details["assignment"] = ", ".join(preview(t) for t in right.targets)
                    self.emit("call" if isinstance(old,ast.Call) or isinstance(new,ast.Call) else "value",
                              owner,old,new,**details)
                    return
        self.emit("statement",owner,left,right)
        # The first line of a compound statement can be unchanged. Show an actual differing line.
        old = ast.unparse(left).splitlines()
        new = ast.unparse(right).splitlines()
        for i in range(min(len(old),len(new))):
            if old[i] != new[i]:
                self.rows[-1]["before"]["expression"] = old[i].strip()[:180]
                self.rows[-1]["after"]["expression"] = new[i].strip()[:180]
                break

    def compare(self):
        old = self.head.snapshot.sources[self.path]
        new = self.work.snapshot.sources[self.path]
        self.old_tree, self.new_tree = a,b = ast.parse(old),ast.parse(new)
        if any(sum(1 for _ in ast.walk(t)) > 16000 for t in (a,b)):
            raise app.Rejected("review_budget")
        if shape(a) != shape(b):
            self.statements(a.body,b.body,())
            return self.rows
        # Give real ranges even for comment-only changes. On insertion there may be no old range.
        left,right = logical_lines(old),logical_lines(new)
        if left == right:
            spans = [(0,min(1,len(left)),0,min(1,len(right)))]
            kind = "encoding"
        else:
            if len(left) * len(right) > 8_000_000:
                raise app.Rejected("review_budget")
            spans = [(a,b,c,d) for tag,a,b,c,d in SequenceMatcher(None,left,right).get_opcodes() if tag != "equal"]
            kind = "text"
        if len(spans) > 48:
            raise app.Rejected("review_budget")
        for a,b,c,d in spans:
            self.rows.append(dict(kind=kind,owner=(),
                before={"ref":checked_ref(self.head,self.path,a+1,b)} if b>a else None,
                after={"ref":checked_ref(self.work,self.path,c+1,d)} if d>c else None))
        return self.rows


class Related:
    def __init__(self, src):
        self.src = src
        self.callers = {}

    @cached_property
    def fields(self):
        return flow.Slice(self.src)

    def calls(self,name):
        if name not in self.callers:
            result = app.lab.cli.calls.lookup(name,self.src,app.lab.cli.refusal)
            self.callers[name] = result["claims"]
        return self.callers[name]

    def find(self, path, row):
        owner = row["owner"]
        if len(owner) != 1:
            return []
        name, = owner
        links = []
        for claim in self.calls(name):
            site = claim["call_site"]
            if site["definition_path"] == path:
                refs = [app.checked_item(self.src,r)["locator"] for r in claim["evidence_blocks"]]
                links.append(dict(kind="direct_call",name=site["caller"] or "__main__",site=site,refs=refs))
        expr = row.get("call_expression")
        if expr:
            for claim in self.calls(expr["name"]):
                site = claim["call_site"]
                if site["path"] == path and all(site[k] == expr[k] for k in ("line","column","end_line","end_column")):
                    refs = [app.checked_item(self.src,r)["locator"] for r in claim["evidence_blocks"]]
                    links.append(dict(kind="direct_target",name=expr["name"],site=site,refs=refs))
        key = row.get("field")
        if key is not None:
            producers = self.fields.producers.get(key, [])
            if len(producers) == 1 and (producers[0][0].path,producers[0][0].node.name) == (path,name):
                for fn,label,read in self.fields.users[key]:
                    links.append(dict(kind="same_key_read",name=fn.node.name,label=label,
                                      refs=[checked_ref(self.src,fn.path,read.lineno,read.end_lineno)]))
        return links


def advice(row):
    kind = row["kind"]
    if kind == "condition":
        if "numeric_equality_now_true" in row:
            value = "истинно" if row["numeric_equality_now_true"] else "ложно"
            return (f"При равенстве обычных числовых операндов условие теперь {value}.",
                    "Проверьте выбор ветви при точном равенстве и на ближайших значениях ниже и выше границы.")
        return "Может измениться выбор ветви.", "Сравните обе ветви на значениях по обе стороны границы и при равенстве."
    if kind == "call":
        return "Может измениться результат в месте вызова.", "Сравните переданные аргументы, значение результата и его использование вызывающей функцией."
    if kind == "field":
        key = row["field"]
        return f"Потребитель поля {key!r} может получить другое значение.", f"Проверьте значение {key!r} на входе, где прежний и новый источники различаются."
    if kind == "encoding":
        return ("Содержимое строк совпадает. Возможная причина — правила перевода строк при checkout.",
                "При необходимости сверьте политику переводов строк и завершающий перевод строки.")
    if kind == "text":
        return "Различий в обычном AST Python здесь не установлено.", "При необходимости проверьте директивы инструментов и правила оформления."
    if kind in ("function","signature"):
        return "Возможны изменения доступности или контракта определения.", "Проверьте импорт, аргументы и прямые и косвенные обращения к определению."
    return "Возможное влияние зависит от пути выполнения.", "Проверьте результат изменённого участка на характерном и граничном входах."


def review(root):
    """Accept a coherent pair under the publication guard. Rendering performs no source reads."""
    with app._runtime_lock:
        core, launch, _ = app._runtime()
    reader = app.lab.Objects(launch,root=root,at_head=True)
    head = app.lab.Sources(reader,core,reader.scope)
    work = WorkingSources(root)
    related = {False:Related(head), True:Related(work)}
    changes = []
    for path in sorted(app.lab.SCOPE):
        if head.raw[path] == work.raw[path]:
            continue
        for row in Changes(path,head,work).compare():
            if len(changes) >= 48:
                raise app.Rejected("review_budget")
            links = related[row["after"] is not None].find(path,row)
            impact, check = advice(row)
            changes.append(dict(row,path=path,related=links,possible_effect=impact,suggested_check=check))
    report = dict(head=head.commit,working_tree=work.commit,allowed_files=sorted(app.lab.SCOPE),
                  changes=changes,execution_observed=False,project_exhaustive=False)
    with work.publication_guard():
        if reader._run("rev-parse","--verify","HEAD^{commit}").decode("ascii").strip() != head.commit:
            raise app.Rejected("review_head_changed")
        return report


def display(report):
    print("Git HEAD",report["head"],"· Рабочий снимок",report["working_tree"])
    print("Обследовано файлов:",len(report["allowed_files"]))
    if not report["changes"]:
        print("В разрешённых файлах сохранённые байты совпадают с HEAD.")
    representation = [r["path"] for r in report["changes"] if r["kind"] == "encoding"]
    if representation:
        print("Совпадают текст строк и обычный AST; отличается байтовое представление:",", ".join(representation))
        print("Возможная причина — преобразование переводов строк при checkout.")
    for row in report["changes"]:
        if row["kind"] == "encoding":
            continue
        owner = ".".join(row["owner"]) or "уровень модуля"
        delta = {"added":"добавлено", "removed":"удалено"}.get(row.get("definition_delta"),"")
        print(f"\n{row['path']} · {owner} · {LABELS[row['kind']]}",row.get("field",""),delta)
        if "assignment" in row:
            print("  Получатель:",row["assignment"])
        for key,label in (("before","HEAD"),("after","Сохранено")):
            side = row[key]
            print(f"  {label}:", (side.get("expression","") + " " + side["ref"]["url"]) if side else "нет сопоставленного фрагмента")
        for link in row["related"]:
            if link["kind"] == "direct_call":
                print("  Установлено место прямого вызова:",link["name"])
            elif link["kind"] == "direct_target":
                print("  Разрешена цель изменённого вызова:",link["name"])
            else:
                print("  Чтение того же ключа:",link["name"],"· передача именно этого отчёта не доказана.")
            for ref in link["refs"]:
                print("   ",ref["url"])
        print(" ",row["possible_effect"],row["suggested_check"])
    print("Связи ограничены пятью файлами и поддерживаемыми прямыми вызовами и чтениями полей. "
          "Проверки предложены по исходникам. Выполнение кода и наличие дефекта не подтверждались.")
