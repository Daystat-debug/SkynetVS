"""Compare two authorized source captures. Only the interactive caller receives code previews."""
import ast
from difflib import SequenceMatcher
from functools import cached_property

import skynet_core_explain as app
import skynet_data_flow as flow
from skynet_working_tree import WorkingSources

QUESTION = "Что я изменил относительно Git HEAD и какие связанные участки кода стоит проверить?"
DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
LABELS = {"function":"Определение", "signature":"Заголовок или декораторы", "condition":"Условие",
          "call":"Вызов", "value":"Значение", "field":"Поле результата", "statement":"Инструкция",
          "text":"Текст при совпадающем AST", "encoding":"Представление текста"}


def shape(node):
    return ast.dump(node, include_attributes=False)


def preview(node):
    text = ast.unparse(node).split("\n", 1)[0]
    return text if len(text) <= 180 else text[:177] + "…"


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

    def emit(self, kind, owner, left, right, **details):
        if len(self.rows) >= 48:
            raise app.Rejected("review_budget")
        self.rows.append(dict(kind=kind,owner=owner,
                              before=describe_side(self.head,self.path,left),
                              after=describe_side(self.work,self.path,right), **details))

    def statements(self, left, right, owner):
        # Equal subtrees align even when their line numbers shift. Unpaired blocks remain additions/removals.
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
        self.emit("function" if defined else "statement",name,node if removed else None,None if removed else node)

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
                self.emit("condition",owner,left.test,right.test)
            self.statements(left.body,right.body,owner)
            self.statements(left.orelse,right.orelse,owner)
            return
        if (isinstance(left,ast.Return) and isinstance(right,ast.Return)
                and isinstance(left.value,ast.Dict) and isinstance(right.value,ast.Dict)):
            keys = left.value.keys
            other = right.value.keys
            if (all(isinstance(k,ast.Constant) and type(k.value) is str for k in [*keys,*other])
                    and [k.value for k in keys] == [k.value for k in other]
                    and len(set(k.value for k in keys)) == len(keys)):
                for key,old,new in zip(keys,left.value.values,right.value.values):
                    if shape(old) != shape(new):
                        self.emit("field",owner,old,new,field=key.value)
                return
        if isinstance(left,(ast.Assign,ast.Return,ast.Expr)) and type(left) == type(right):
            if not isinstance(left,ast.Assign) or list(map(shape,left.targets)) == list(map(shape,right.targets)):
                old, new = left.value, right.value
                if old is not None and new is not None:
                    self.emit("call" if isinstance(old,ast.Call) or isinstance(new,ast.Call) else "value",owner,old,new)
                    return
        self.emit("statement",owner,left,right)

    def compare(self):
        old = self.head.snapshot.sources[self.path]
        new = self.work.snapshot.sources[self.path]
        a,b = ast.parse(old),ast.parse(new)
        if shape(a) != shape(b):
            self.statements(a.body,b.body,())
            return self.rows
        # Give real ranges even for comment-only changes. On insertion there may be no old range.
        left,right = old.splitlines(),new.splitlines()
        if left == right:
            spans = [(0,1,0,1)]
            kind = "encoding"
        else:
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

    def find(self, path, row):
        owner = row["owner"]
        if len(owner) != 1:
            return []
        name, = owner
        if name not in self.callers:
            result = app.lab.cli.calls.lookup(name,self.src,app.lab.cli.refusal)
            self.callers[name] = result["claims"]
        links = []
        for claim in self.callers[name]:
            site = claim["call_site"]
            if site["definition_path"] == path:
                refs = [app.checked_item(self.src,r)["locator"] for r in claim["evidence_blocks"]]
                links.append(dict(kind="direct_call",name=site["caller"] or "__main__",site=site,refs=refs))
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
        return "Может измениться выбор ветви.", "Сравните обе ветви на значениях по обе стороны границы и при равенстве."
    if kind == "call":
        return "Может измениться результат в месте вызова.", "Сравните переданные аргументы, значение результата и его использование вызывающей функцией."
    if kind == "field":
        key = row["field"]
        return f"Потребитель поля {key!r} может получить другое значение.", f"Проверьте значение {key!r} на входе, где прежний и новый источники различаются."
    if kind in ("text","encoding"):
        return "Различий в обычном AST Python здесь не установлено.", "При необходимости проверьте директивы инструментов и правила оформления."
    if kind in ("function","signature"):
        return "Возможны изменения доступности или контракта определения.", "Проверьте импорт, аргументы и прямые и косвенные обращения к определению."
    return "Возможное влияние зависит от пути выполнения.", "Проверьте результат изменённого участка на характерном и граничном входах."


def review(root, publish=lambda report:report):
    """The callback consumes the verified result while the Working Tree publication guard is held."""
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
        return publish(report)


def display(report):
    print("Git HEAD",report["head"],"· Рабочий снимок",report["working_tree"])
    print("Обследовано файлов:",len(report["allowed_files"]))
    if not report["changes"]:
        print("В разрешённых файлах сохранённые байты совпадают с HEAD.")
    for row in report["changes"]:
        owner = ".".join(row["owner"]) or "уровень модуля"
        print(f"\n{row['path']} · {owner} · {LABELS[row['kind']]}",row.get("field",""))
        for key,label in (("before","HEAD"),("after","Сохранено")):
            side = row[key]
            print(f"  {label}:", (side.get("expression","") + " " + side["ref"]["url"]) if side else "участок отсутствует")
        for link in row["related"]:
            if link["kind"] == "direct_call":
                print("  Установлено место прямого вызова:",link["name"])
            else:
                print("  Чтение того же ключа:",link["name"],"· передача именно этого отчёта не доказана.")
            for ref in link["refs"]:
                print("   ",ref["url"])
        print(" ",row["possible_effect"],row["suggested_check"])
    print("Проверки предложены по статическому сравнению. Выполнение кода и наличие дефекта не подтверждались.")
