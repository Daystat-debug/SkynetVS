"""Small offline Tk window for the existing DTR-A contracts, not an executor."""
from __future__ import annotations

import json
import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from .core import (ArtifactStore, DEMO_TITLE, DEMO_INSTRUCTION, demo_snapshot, demo_response,
                   json_bytes, make_request, prompt_text, read_plain, restore_request, review_response)
from .git_source import GitSourceReader, find_git
from .patch_preview import preview_patch_in_memory
from .clipboard import ClipboardBindings
from .dtrb_receipt import inspect_m074_evidence


class QuietTk(tk.Tk):
    def readprofile(self, baseName, className):
        # Do not execute optional user .py/.tcl Tk profiles from HOME or cwd.
        return None


class DeveloperWindow:
    def __init__(self, root: tk.Tk, store: ArtifactStore, *, repository: Path = Path(r"C:\Project\SkynetVS"),
                 bundled_reference: Path | None = None):
        self.root, self.store, self.repository = root, store, repository
        self.bundled_reference = bundled_reference
        self.dtrb_view = self.dtrb_folder = None
        self.source = self.request = self.review = None
        self.imported_session = False
        self.request_folder = None
        self.static_preview = None
        self.static_folder = None
        self.events: list[dict] = []
        self.muting = False
        root.title("SkynetVS — Developer Task • M092 (в проекте)")
        root.geometry(f"{min(1130, root.winfo_screenwidth() - 60)}x{min(850, root.winfo_screenheight() - 100)}")
        root.minsize(900, 640)
        root.configure(background="#f3f5f8")
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background="#f3f5f8")
        style.configure("TLabel", background="#f3f5f8", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 8))
        style.configure("Primary.TButton", background="#2459a6", foreground="white")
        style.configure("TNotebook.Tab", padding=(18, 9), font=("Segoe UI", 10))
        header = tk.Frame(root, bg="#172a42", padx=22, pady=16)
        header.pack(fill="x")
        tk.Label(header, text="SkynetVS  /  Developer Task", bg="#172a42", fg="white",
                 font=("Segoe UI", 21, "bold")).pack(anchor="w")
        tk.Label(header, text="Задача → предложение patch → DTR-B (готовый отчёт)", bg="#172a42",
                 fg="#c5d3e5", font=("Segoe UI", 11)).pack(anchor="w", pady=(5, 0))
        bar = ttk.Frame(root, padding=(18, 10))
        bar.pack(fill="x")
        self.demo_button = ttk.Button(bar, text="Учебный пример", command=self.run_demo)
        self.demo_button.pack(side="left")
        ttk.Button(bar, text="Открыть сохранённый запрос…", command=self.open_request).pack(side="left", padx=8)
        ttk.Button(bar, text="Восстановить задачу AUDIO_DUCKING_LEVEL", command=self.restore_bundled_task).pack(side="left", padx=8)
        ttk.Label(bar, text="Без применения patch и выполнения предложенного кода").pack(side="right")
        self.tabs = ttk.Notebook(root)
        self.task_tab = ttk.Frame(self.tabs, padding=16)
        self.prompt_tab = ttk.Frame(self.tabs, padding=12)
        self.review_tab = ttk.Frame(self.tabs, padding=12)
        self.dtrb_tab = ttk.Frame(self.tabs, padding=12)
        for widget, label in [(self.task_tab, "1. Задача и исходник"), (self.prompt_tab, "2. Запрос для чата"),
                              (self.review_tab, "3. Ответ и patch"), (self.dtrb_tab, "4. Отчёт DTR-B")]:
            self.tabs.add(widget, text=label)
        self._task_widgets()
        self._prompt_widgets()
        self._review_widgets()
        self._dtrb_widgets()
        self.status = tk.StringVar(value="Начни с учебного примера или выбери один разрешённый Python-файл проекта.")
        footer = ttk.Frame(root)
        footer.pack(side="bottom", fill="x")
        ttk.Label(footer, textvariable=self.status, wraplength=1050, padding=(20, 10), foreground="#334b67").pack(fill="x")
        ttk.Label(footer, text="Режим: только подготовка и просмотр. Код не применён; поведение не проверено; promotion закрыт.",
                  wraplength=1050, padding=(20, 0, 20, 12), foreground="#805313").pack(fill="x")
        self.tabs.pack(fill="both", expand=True, padx=18)
        self.clipboard_bindings = ClipboardBindings(root, notify=lambda text: self.status.set(text))
        for widget, editable in (
            (self.title_entry, True), (self.instruction, True),
            (self.source_text, False), (self.prompt, False), (self.patch, False), (self.dtrb_text, False),
        ):
            self.clipboard_bindings.attach(widget, editable=editable)
        root.bind("<Configure>", self.resized)
        self.title_var.trace_add("write", lambda *_: self.invalidate())
        self.instruction.bind("<<Modified>>", self.instruction_changed)
        self.set_text(self.prompt, "Здесь появится файл запроса после нажатия «Подготовить запрос».")
        self.set_text(self.patch, "Здесь будет текст предложения. Он никогда не выполняется этим окном.")
        self.set_text(self.dtrb_text, "Отчёт M074 пока не импортирован.")
        self.refresh_source()

    def resized(self, event):
        if event.widget is not self.root:
            return
        width = max(500, event.width - 75)
        def visit(widget):
            for child in widget.winfo_children():
                if isinstance(child, ttk.Label) and int(child.cget("wraplength") or 0) > 0:
                    child.configure(wraplength=width)
                visit(child)
        visit(self.root)

    def _task_widgets(self):
        box = self.task_tab
        sourcebar = ttk.Frame(box)
        sourcebar.pack(fill="x")
        ttk.Label(sourcebar, text="Исходник", font=("Segoe UI", 12, "bold")).pack(side="left")
        ttk.Button(sourcebar, text="Выбрать .py из проекта…", command=self.choose_source).pack(side="right")
        self.source_info = tk.StringVar()
        ttk.Label(box, textvariable=self.source_info, wraplength=1020, foreground="#365573").pack(fill="x", pady=(8, 10))
        ttk.Label(box, text="Краткое название задачи").pack(anchor="w")
        self.title_var = tk.StringVar()
        self.title_entry = ttk.Entry(box, textvariable=self.title_var, font=("Segoe UI", 11))
        self.title_entry.pack(fill="x", pady=(4, 10))
        ttk.Label(box, text="Что нужно изменить и что необходимо сохранить").pack(anchor="w")
        self.instruction = ScrolledText(box, height=5, wrap="word", font=("Segoe UI", 11), undo=True)
        self.instruction.pack(fill="x", pady=(4, 4))
        ttk.Label(box, text="Ctrl+C/V/X/A или правая кнопка мыши — работают в полях ввода."
                  " Из исходника и patch можно только копировать.", foreground="#365573").pack(anchor="w", pady=(0, 9))
        actions = ttk.Frame(box)
        actions.pack(fill="x", pady=(0, 12))
        self.prepare_button = ttk.Button(actions, text="Подготовить запрос", style="Primary.TButton", command=self.prepare)
        self.prepare_button.pack(side="left")
        ttk.Label(actions, text="Создаёт файлы только в Downloads. Отправляешь их в чат самостоятельно.",
                  wraplength=670).pack(side="left", padx=15)
        ttk.Label(box, text="Исходный текст — просмотр, без выполнения").pack(anchor="w")
        self.source_text = ScrolledText(box, height=9, wrap="none", font=("Consolas", 10))
        self.source_text.pack(fill="both", expand=True, pady=(4, 0))

    def _prompt_widgets(self):
        bar = ttk.Frame(self.prompt_tab)
        bar.pack(fill="x")
        ttk.Button(bar, text="Скопировать запрос", command=self.copy_prompt).pack(side="left")
        ttk.Button(bar, text="Папка запроса", command=self.open_request_folder).pack(side="left", padx=8)
        self.import_button = ttk.Button(bar, text="Импортировать ответ JSON…", style="Primary.TButton", command=self.import_file)
        self.import_button.pack(side="right")
        self.prompt_path = tk.StringVar(value="Запрос ещё не подготовлен.")
        ttk.Label(self.prompt_tab, textvariable=self.prompt_path, wraplength=1020).pack(fill="x", pady=10)
        self.prompt = ScrolledText(self.prompt_tab, wrap="word", font=("Consolas", 10))
        self.prompt.pack(fill="both", expand=True)

    def _review_widgets(self):
        bar = ttk.Frame(self.review_tab)
        bar.pack(fill="x")
        ttk.Button(bar, text="Импортировать ответ JSON…", command=self.import_file).pack(side="left")
        ttk.Button(bar, text="Вставить JSON…", command=self.paste_response).pack(side="left", padx=8)
        self.static_button = ttk.Button(bar, text="Проверить patch в памяти", command=self.check_patch_preview)
        self.static_button.pack(side="left", padx=8)
        ttk.Button(bar, text="Импортировать DTR-B ZIP…", command=self.import_dtrb_file).pack(side="left", padx=8)
        self.static_button.state(["disabled"])
        self.review_summary = tk.StringVar(value="Ответ ещё не импортирован.")
        ttk.Label(self.review_tab, textvariable=self.review_summary, wraplength=1020,
                  font=("Segoe UI", 11, "bold"), foreground="#244a6f").pack(fill="x", pady=10)
        self.details = tk.StringVar(value="")
        ttk.Label(self.review_tab, textvariable=self.details, wraplength=1020).pack(fill="x", pady=(0, 10))
        self.patch = ScrolledText(self.review_tab, wrap="none", font=("Consolas", 10), height=12)
        self.patch.pack(fill="both", expand=True)
        self.patch.tag_configure("plus", foreground="#1c6b38")
        self.patch.tag_configure("minus", foreground="#a2323a")
        self.review_path = tk.StringVar()
        ttk.Label(self.review_tab, textvariable=self.review_path, wraplength=1020).pack(fill="x", pady=(10, 0))
        self.static_summary = tk.StringVar(value="Проверка текста patch: ещё не запускалась.")
        ttk.Label(self.review_tab, textvariable=self.static_summary, wraplength=1020,
                  foreground="#5d4d26").pack(fill="x", pady=(7, 0))

    def _dtrb_widgets(self):
        bar = ttk.Frame(self.dtrb_tab)
        bar.pack(fill="x")
        ttk.Button(bar, text="Показать M074 из комплекта", command=self.import_bundled_m074).pack(side="left")
        ttk.Button(bar, text="Выбрать M074 evidence ZIP…", command=self.import_dtrb_file).pack(side="left", padx=8)
        self.dtrb_summary = tk.StringVar(value="DTR-B: отчёт не загружен. Сначала подготовь запрос, импортируй ответ и проверь patch в памяти.")
        ttk.Label(self.dtrb_tab, textvariable=self.dtrb_summary, wraplength=1000,
                  font=("Segoe UI", 11, "bold"), foreground="#244a6f").pack(fill="x", pady=10)
        self.dtrb_text = ScrolledText(self.dtrb_tab, wrap="word", font=("Consolas", 10), height=18)
        self.dtrb_text.pack(fill="both", expand=True)
        ttk.Label(self.dtrb_tab, text="Только просмотр готового M074 evidence: код не выполняется, Git не вызывается. "
                  "Проверка поведения, pipeline и установка не разрешены.", wraplength=1000, foreground="#805313").pack(fill="x", pady=10)

    def reset_dtrb(self):
        self.dtrb_view = self.dtrb_folder = None
        self.dtrb_summary.set("DTR-B: нет отчёта для текущей привязки.")
        self.set_text(self.dtrb_text, "Импортируй M074 evidence только после принятого DTR-A и проверки patch в памяти.")

    def restore_bundled_task(self):
        try:
            if self.bundled_reference is None:
                raise ValueError("Архивированная задача отсутствует в данном пакете.")
            request, source = restore_request(read_plain(self.bundled_reference / "DTR_Request.json", 512 * 1024))
            self._load_request(request, source, str(self.bundled_reference / "DTR_Request.json"))
            self.accept_bytes(read_plain(self.bundled_reference / "DTR_Response.json", 256 * 1024))
            self.check_patch_preview()
            self.status.set("Архивированная задача M074 восстановлена. Снимок Git НЕ обновлялся. Перейди к отчёту DTR-B.")
            self.event("BUNDLED_M074_TASK_RESTORED", fingerprint=request.request_fingerprint)
        except Exception as exc:
            self.fail(exc)

    def import_bundled_m074(self):
        try:
            if self.bundled_reference is None:
                raise ValueError("Файл M074 evidence отсутствует в данном пакете.")
            return self._accept_dtrb_bytes(read_plain(self.bundled_reference / "M074_DTRB_Evidence.zip", 2 * 1024 * 1024))
        except Exception as exc:
            self.fail(exc)
            return None

    def import_dtrb_file(self):
        if self.request is None or self.review is None or self.static_preview is None:
            self.fail(ValueError("Сначала открой запрос, импортируй ответ и выполни проверку patch в памяти."))
            return
        filename = filedialog.askopenfilename(parent=self.root, title="Выбрать завершённый M074_DTRB_Evidence.zip",
                                             initialdir=str(Path.home() / "Downloads"), filetypes=[("ZIP", "*.zip")])
        if not filename:
            return
        try:
            return self._accept_dtrb_bytes(read_plain(Path(filename), 2 * 1024 * 1024))
        except Exception as exc:
            self.fail(exc)
            return None

    def _accept_dtrb_bytes(self, raw: bytes):
        # Exact evidence hash pinned; contextual identities and internal stages also cross-checked.
        report = inspect_m074_evidence(raw, request=self.request, review=self.review, preview=self.static_preview)
        folder = self.store.save_dtrb_view(report)
        self.dtrb_view, self.dtrb_folder = report, folder
        self.dtrb_summary.set("DTR-B: git_diff_check PASS, py_compile PASS — только по M074 evidence, NOT PROMOTABLE")
        displayed = (
            "ЦЕЛЬ: " + report["target_path"] + "\n"
            "Git commit: " + report["base_commit"] + "\n"
            "DTR-A + AST: PASS (текущая привязка)\n\n"
            "git_diff_check: PASS (по M074)\n"
            "py_compile: PASS (по M074)\n"
            "patch применён ТОЛЬКО во временной копии, по evidence\n"
            "DTR-B workspace удалён, по evidence\n"
            "pipeline(flow=check): НЕ ВЫПОЛНЕН\n"
            "Проверка поведения: НЕ ВЫПОЛНЕНА\n"
            "Исполнение изменённого кода: НЕТ\n"
            "Установка / promotion / runtime: ЗАПРЕЩЕНЫ\n\n"
            "Внимание: импортированный отчёт не является криптографической аттестацией среды или модели.\n"
            "Контрольная сумма evidence: " + report["evidence_sha256"] + "\n"
            "Отчёт для просмотра: " + str(folder / "DTRB_View.json") + "\n\n" + report["message"]
        )
        self.set_text(self.dtrb_text, displayed)
        self.tabs.select(self.dtrb_tab)
        self.status.set("DTR-B M074 показан. Новый запуск DTR-B НЕ выполнялся; проект остался нетронутым.")
        self.event("DTRB_M074_RECEIPT_VIEWED", fingerprint=report["request_fingerprint"],
                   artifact=str(folder.relative_to(self.store.root)), sha256=report["evidence_sha256"])
        return report

    @staticmethod
    def set_text(widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def event(self, name: str, **fields):
        self.events.append({"event": name, **fields})

    def fail(self, exc: Exception):
        self.status.set(str(exc))
        self.event("ERROR", type=type(exc).__name__, message=str(exc))
        messagebox.showerror("Действие не выполнено", str(exc), parent=self.root)

    def invalidate(self):
        if self.muting:
            return
        if self.request is not None:
            self.request = self.review = None
            self.request_folder = None
            self.static_preview = self.static_folder = None
            self.reset_dtrb()
            self.static_button.state(["disabled"])
            self.static_summary.set("Проверка текста patch: ещё не запускалась.")
            self.set_text(self.prompt, "Задача изменилась. Нажми «Подготовить запрос» для новой привязки.")
            self.set_text(self.patch, "Предыдущий ответ не относится к новой редакции задачи.")
            self.review_summary.set("Нужен новый запрос. Прежняя привязка сброшена.")
            self.details.set("")
            self.review_path.set("")
            self.prompt_path.set("Старые артефакты сохранены, но не используются как новый запрос.")
            self.status.set("Подготовь новый запрос перед импортом ответа.")
            self.event("REQUEST_INVALIDATED_BY_EDIT")

    def instruction_changed(self, _event=None):
        if self.instruction.edit_modified():
            self.invalidate()
            self.instruction.edit_modified(False)

    def set_task(self, title, instruction):
        self.muting = True
        self.title_var.set(title)
        self.instruction.delete("1.0", "end")
        self.instruction.insert("1.0", instruction)
        self.instruction.edit_modified(False)
        self.muting = False

    def refresh_source(self):
        if self.source is None:
            self.source_info.set("Файл не выбран. Учебный пример не читает твой репозиторий.")
            self.set_text(self.source_text, "")
            return
        demo = self.source.provenance.get("kind") == "DEMO_SYNTHETIC_NOT_REPOSITORY"
        mode = "УЧЕБНЫЙ ПРИМЕР — синтетическая база, не текущий Git" if demo else "Один файл из конкретного commit (не полный снимок репозитория)"
        if self.imported_session:
            mode += "; загружено из запроса, происхождение и текущий HEAD здесь не перепроверены"
        eol = self.source.provenance.get("working_copy_relation")
        if eol == "ONLY_WORKTREE_CRLF_TO_BLOB_LF":
            mode += "; CRLF рабочей копии / LF в точном Git blob"
        self.source_info.set(f"{self.source.path}\n{mode}\ncommit: {self.source.base_commit} • {len(self.source.content)} байт")
        self.set_text(self.source_text, self.source.content.decode("utf-8"))

    def choose_source(self):
        filename = filedialog.askopenfilename(parent=self.root, title="Выбрать один разрешённый Python-модуль",
                                             initialdir=str(self.repository / "modules"), filetypes=[("Python", "*.py")])
        if not filename:
            return
        try:
            git = find_git()
            consent = messagebox.askyesno(
                "Прочитать Git-версию выбранного файла?",
                "Будут прочитаны HEAD, tree и один Git blob. Файл не импортируется и не запускается.\n\n"
                "Нет status, checkout, commit, clone, apply, hooks или загрузки объектов из сети. "
                "Изменённый относительно HEAD файл не будет молча заменён старой версией.\n\n"
                f"Git: {git}\nФайл: {filename}\n\nПродолжить только чтение?", parent=self.root)
            if not consent:
                return
            self.status.set("Читается один Git blob; операции записи в репозиторий не выполняются…")
            self.root.update_idletasks()
            source = GitSourceReader(self.repository, git).capture(Path(filename))
            self.invalidate()
            self.source = source
            self.imported_session = False
            self.refresh_source()
            self.tabs.select(self.task_tab)
            self.status.set("Исходник выбран. Опиши задачу и подготовь запрос.")
            self.event("SOURCE_SELECTED", path=source.path, base_commit=source.base_commit, kind="OBSERVED_COMMITTED_FILE")
        except Exception as exc:
            self.fail(exc)

    def prepare(self):
        try:
            if self.source is None:
                raise ValueError("Сначала выбери исходник или нажми «Учебный пример».")
            request = make_request(self.source, self.title_var.get(), self.instruction.get("1.0", "end-1c"))
            folder = self.store.save_request(request, self.source)
            self.request, self.request_folder, self.review = request, folder, None
            self.reset_dtrb()
            self.static_preview = self.static_folder = None
            self.static_button.state(["disabled"])
            self.static_summary.set("Проверка текста patch: ещё не запускалась.")
            self.set_text(self.prompt, prompt_text(request, self.source))
            self.prompt_path.set(f"Файл для чата: {folder / 'DTR_Request.md'}\nДля повторного открытия окна: DTR_Request.json в этой же папке.")
            self.review_summary.set("Импортируй DTR_Response.json, полученный в ответ на этот запрос.")
            self.details.set("")
            self.review_path.set("")
            self.set_text(self.patch, "Ответ для этой привязки ещё не импортирован.")
            self.status.set("Запрос сохранён. Передай DTR_Request.md в чат; автоматической отправки нет.")
            self.tabs.select(self.prompt_tab)
            self.event("REQUEST_PREPARED", request_id=request.request_id, fingerprint=request.request_fingerprint,
                       artifact=str(folder.relative_to(self.store.root)))
            return True
        except Exception as exc:
            self.fail(exc)
            return False

    def copy_prompt(self):
        if self.request is None:
            self.fail(ValueError("Сначала подготовь запрос."))
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(prompt_text(self.request, self.source))
        self.status.set("Запрос скопирован. Он содержит текст только выбранного файла; не публикуй приватный код случайно.")

    def open_request_folder(self):
        if self.request_folder is None:
            self.fail(ValueError("Сначала подготовь запрос. Для восстановленного запроса используй папку выбранного DTR_Request.json."))
            return
        try:
            # Explicit user click, directory created by this app, never a model-supplied command.
            if os.name == "nt":
                os.startfile(str(self.request_folder))
            else:
                self.root.clipboard_clear()
                self.root.clipboard_append(str(self.request_folder))
                self.status.set("Путь к папке скопирован: " + str(self.request_folder))
        except Exception as exc:
            self.fail(exc)

    def _load_request(self, request, source, filename: str):
        self.invalidate()
        self.set_task(request.title, request.instruction)
        self.request, self.source, self.review = request, source, None
        self.reset_dtrb()
        self.static_preview = self.static_folder = None
        self.static_button.state(["disabled"])
        self.static_summary.set("Проверка текста patch: ещё не запускалась.")
        self.request_folder = None
        self.imported_session = True
        self.refresh_source()
        self.set_text(self.prompt, prompt_text(request, source))
        self.prompt_path.set(f"Открыт запрос: {filename}\nТекущий репозиторий не читался; входной файл не является доверенным хранилищем.")
        self.review_summary.set("Запрос восстановлен. Ответ должен иметь исходные request_id и fingerprint.")
        self.details.set("")
        self.review_path.set("")
        self.set_text(self.patch, "Ответ ещё не импортирован.")
        self.tabs.select(self.prompt_tab)
        self.status.set("Сохранённая привязка пересчитана; текущий Git и происхождение файла не проверены.")
        self.event("REQUEST_RESTORED", request_id=request.request_id)

    def open_request(self):
        filename = filedialog.askopenfilename(parent=self.root, title="Открыть DTR_Request.json",
                                             initialdir=str(self.store.root), filetypes=[("JSON", "*.json")])
        if not filename:
            return
        try:
            request, source = restore_request(read_plain(Path(filename), 512 * 1024))
            self._load_request(request, source, filename)
        except Exception as exc:
            self.fail(exc)

    def accept_bytes(self, raw: bytes):
        if self.request is None:
            raise ValueError("Сначала подготовь или открой запрос. Чужую привязку из ответа нельзя использовать вместо него.")
        report = review_response(self.request, raw)
        demo = self.source.provenance.get("kind") == "DEMO_SYNTHETIC_NOT_REPOSITORY"
        report["source_kind"] = self.source.provenance.get("kind", "UNKNOWN")
        report["demo_data"] = demo
        report["request_loaded_from_file"] = self.imported_session
        folder = self.store.save_review(self.request, self.source, raw, report)
        self.review = report
        self.reset_dtrb()
        self.static_preview = self.static_folder = None
        self.static_summary.set("Проверка текста patch: ещё не запускалась; нажми кнопку после принятой привязки.")
        self.static_button.state(["!disabled"] if report["intake"]["ok"] else ["disabled"])
        prefix = "УЧЕБНЫЙ ПРИМЕР. " if demo else ""
        self.review_summary.set(prefix + report["summary"])
        issues = report["intake"]["issues"]
        detail = "\n".join(f"{item['field']}: {item['code']} — {item['message']}" for item in issues)
        detail = detail or ("Пути внутри patch и его применимость НЕ проверены. git_diff_check, py_compile и pipeline НЕ запускались.\n"
                            "Синтаксис и поведение не подтверждены. Файл проекта не изменён; provider не аутентифицирован.\n\n"
                            + "Объяснение автора ответа: " + report["explanation"])
        # Long explanations remain in the saved report; avoid pushing the preview off-screen.
        self.details.set(detail[:1600] + ("\n… Полный текст в DTR_Review.json." if len(detail) > 1600 else ""))
        shown = report["patch_text"] if report["intake"]["ok"] else raw.decode("utf-8", "replace")
        self.set_text(self.patch, shown)
        if report["intake"]["ok"]:
            for number, line in enumerate(shown.splitlines(), 1):
                if line.startswith("+"):
                    self.patch.tag_add("plus", f"{number}.0", f"{number}.end")
                elif line.startswith("-"):
                    self.patch.tag_add("minus", f"{number}.0", f"{number}.end")
        self.review_path.set(f"Результат и исходный ответ: {folder}\nСтатус DTR-A: {report['intake']['status']} — НЕ разрешение исполнения.")
        self.tabs.select(self.review_tab)
        self.status.set("Предложение показано. Кнопок применения и запуска в этом окне нет.")
        self.event("RESPONSE_REVIEWED", request_id=self.request.request_id, status=report["intake"]["status"],
                   artifact=str(folder.relative_to(self.store.root)), demo=demo)
        return report

    def check_patch_preview(self):
        """User-invoked, in-memory preview only. No Git/check/apply/compile."""
        try:
            if self.request is None or self.source is None or self.review is None or not self.review["intake"]["ok"]:
                raise ValueError("Сначала импортируй ответ с корректной DTR-A привязкой.")
            if self.static_preview is not None:
                self.static_summary.set("Проверка этого ответа уже сохранена: " + str(self.static_folder))
                return self.static_preview
            report = preview_patch_in_memory(
                original=self.source.content, patch_text=self.review["patch_text"],
                target_path=self.request.target_path,
                request_fingerprint=self.request.request_fingerprint,
                response_sha256=self.review["response_sha256"],
            )
            folder = self.store.save_static_preview(report)
            self.static_preview = report
            self.static_folder = folder
            self.static_button.state(["disabled"])
            self.static_summary.set(
                "Текст patch: " + report["text_applicability"] + " · Python AST: " +
                report["python_ast_parse"] + "\n" + report["message"] +
                "\nОтчёт: " + str(folder / "DTR_PatchStaticPreview.json") +
                "\nНЕ выполнялись: git_diff_check, py_compile, pipeline. Нет применения в репозиторий."
            )
            self.status.set("Проверка текста в памяти завершена; обязательная DTR-B репетиция НЕ выполнялась.")
            self.event("STATIC_PREVIEW_RECORDED", request_id=self.request.request_id,
                       status=report["preview_status"], artifact=str(folder.relative_to(self.store.root)))
            return report
        except Exception as exc:
            self.fail(exc)
            return None

    def import_file(self):
        if self.request is None:
            self.fail(ValueError("Сначала подготовь или открой запрос."))
            return
        filename = filedialog.askopenfilename(parent=self.root, title="Импорт DTR_Response.json",
                                             initialdir=str(Path.home() / "Downloads"), filetypes=[("JSON", "*.json")])
        if not filename:
            return
        try:
            self.accept_bytes(read_plain(Path(filename), 256 * 1024))
        except Exception as exc:
            self.fail(exc)

    def paste_response(self):
        if self.request is None:
            self.fail(ValueError("Сначала подготовь или открой запрос."))
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Вставить один JSON-объект ответа")
        dialog.geometry("780x560")
        ttk.Label(dialog, text="Без Markdown-обёртки. Это только данные — код не выполняется.", padding=10).pack(fill="x")
        text = ScrolledText(dialog, font=("Consolas", 10), wrap="none", undo=True)
        text.pack(fill="both", expand=True, padx=10)
        self.clipboard_bindings.attach(text, editable=True)
        def submit():
            try:
                self.accept_bytes(text.get("1.0", "end-1c").encode("utf-8", "strict"))
                dialog.destroy()
            except Exception as exc:
                self.fail(exc)
        ttk.Button(dialog, text="Проверить привязку и показать", command=submit).pack(pady=10)

    def run_demo(self):
        try:
            self.invalidate()
            self.source = demo_snapshot()
            self.imported_session = False
            self.set_task(DEMO_TITLE, DEMO_INSTRUCTION)
            self.refresh_source()
            if self.prepare():
                self.accept_bytes(demo_response(self.request, self.source))
                self.status.set("Учебный маршрут завершён: запрос → готовый учебный JSON → просмотр. Это не генерация моделью и не изменение проекта.")
                self.event("DEMO_COMPLETED_NO_PROJECT_READ")
        except Exception as exc:
            self.fail(exc)
