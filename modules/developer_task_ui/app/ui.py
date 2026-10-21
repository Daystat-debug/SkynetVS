"""Small offline Tk window for the existing DTR-A contracts, not an executor."""
from __future__ import annotations

import json
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText

from .core import (ArtifactStore, DEMO_TITLE, DEMO_INSTRUCTION, demo_snapshot, demo_response,
                   json_bytes, make_request, prompt_text, read_plain, restore_request, review_response)
from .git_source import GitSourceReader, find_git
from .patch_preview import preview_patch_in_memory
from .clipboard import ClipboardBindings
from .dtrb_receipt import inspect_m074_evidence
from .self_review import DEFAULT_MODEL, format_report, review_repository, save_report
from .own_analyzer import (SCHEMA as OWN_SCHEMA, analyze_repository, format_own_report,
                           save_own_report, save_feedback, train_ranker, user_analyzer_directory)
from .proposals import propose_from_finding
from .approved_patch import verify_candidate, apply_approved, rollback_approved, _changes_root
from .context_search import search_repository, format_context, receipt_without_source


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
        self.ai_busy = False
        self.ai_queue = queue.Queue()
        self.ai_report = None
        self.ai_proposal = None
        self.ai_proposal_finding_id = None
        self.ai_apply_checked = None
        self.ai_last_receipt = None
        self.ai_context_text = None  # only memory; never save source excerpts in evidence
        root.title("SkynetVS — AI-разработка")
        root.geometry(f"{min(1130, root.winfo_screenwidth() - 60)}x{min(780, root.winfo_screenheight() - 100)}")
        root.minsize(790, 560)
        root.configure(background="#f3f5f8")
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background="#f3f5f8")
        style.configure("TLabel", background="#f3f5f8", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10), padding=(9, 6))
        style.configure("Primary.TButton", background="#2459a6", foreground="white")
        style.configure("TNotebook.Tab", padding=(12, 7), font=("Segoe UI", 10))

        header = tk.Frame(root, bg="#172a42", padx=18, pady=10)
        header.pack(fill="x")
        self.legacy_button = ttk.Button(header, text="Показать инструменты DTR",
                                        command=self.toggle_legacy_tools)
        self.legacy_button.pack(side="right", padx=(10, 0))
        tk.Label(header, text="SkynetVS / AI-разработка", bg="#172a42", fg="white",
                 font=("Segoe UI", 17, "bold")).pack(side="left")

        self.tabs = ttk.Notebook(root)
        self.ai_tab = ttk.Frame(self.tabs, padding=(12, 10))
        self.task_tab = ttk.Frame(self.tabs, padding=12)
        self.prompt_tab = ttk.Frame(self.tabs, padding=12)
        self.review_tab = ttk.Frame(self.tabs, padding=12)
        self.dtrb_tab = ttk.Frame(self.tabs, padding=12)
        self.tools_tab = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(self.ai_tab, text="AI-разработка")
        self._legacy_tabs = [(self.task_tab, "Задача и исходник"),
                             (self.prompt_tab, "Запрос для чата"),
                             (self.review_tab, "Ответ и patch"),
                             (self.dtrb_tab, "Отчёт DTR-B"),
                             (self.tools_tab, "Учебные инструменты")]
        for tab, name in self._legacy_tabs:
            self.tabs.add(tab, text=name)
        self._legacy_visible = False
        for tab, _ in self._legacy_tabs:
            self.tabs.hide(tab)
        tools = self.tools_tab
        ttk.Label(tools, text="Учебные и исторические функции DTR",
                  font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 12))
        ttk.Label(tools, text="Функции сохранены для совместимости. Они не нужны для обычного AI-анализа и проверки исправления.",
                  wraplength=930).pack(anchor="w", pady=(0, 12))
        self.demo_button = ttk.Button(tools, text="Учебный пример", command=self.run_demo)
        self.demo_button.pack(anchor="w", pady=4)
        ttk.Button(tools, text="Открыть сохранённый запрос…", command=self.open_request).pack(anchor="w", pady=4)
        ttk.Button(tools, text="Восстановить задачу AUDIO_DUCKING_LEVEL",
                   command=self.restore_bundled_task).pack(anchor="w", pady=4)

        self._task_widgets()
        self._prompt_widgets()
        self._review_widgets()
        self._dtrb_widgets()
        self._ai_widgets()
        self.status = tk.StringVar(value="Готово. Анализ не изменяет исходники; применение требует отдельного подтверждения.")
        footer = ttk.Frame(root)
        footer.pack(side="bottom", fill="x")
        ttk.Label(footer, textvariable=self.status, wraplength=1030,
                  padding=(14, 6), foreground="#334b67").pack(fill="x")
        self.tabs.pack(fill="both", expand=True, padx=12, pady=(0, 2))
        self.tabs.select(self.ai_tab)
        self.clipboard_bindings = ClipboardBindings(root, notify=lambda text: self.status.set(text))
        for widget, editable in (
            (self.title_entry, True), (self.instruction, True),
            (self.source_text, False), (self.prompt, False), (self.patch, False), (self.dtrb_text, False),
            (self.ai_text, False),
        ):
            self.clipboard_bindings.attach(widget, editable=editable)
        root.bind("<Configure>", self.resized)
        self.title_var.trace_add("write", lambda *_: self.invalidate())
        self.instruction.bind("<<Modified>>", self.instruction_changed)
        self.set_text(self.prompt, "Здесь появится файл запроса после нажатия «Подготовить запрос».")
        self.set_text(self.patch, "Здесь будет текст предложения. Он никогда не выполняется этим окном.")
        self.set_text(self.dtrb_text, "Отчёт M074 пока не импортирован.")
        self.set_text(self.ai_text, "Режим по умолчанию: собственный AST-анализатор без Ollama. Он читает Git HEAD и выдаёт проверяемые гипотезы, которые можно оценить и использовать для локального обучения ранжирования.\nКод не меняется.")
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
        ttk.Label(actions, text="Сохраняет запрос в LocalAppData. При необходимости отправляешь его в чат сам.",
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

    def toggle_legacy_tools(self):
        """Show/hide legacy tabs only; never delete modules, artifacts or user data."""
        self._legacy_visible = not self._legacy_visible
        if self._legacy_visible:
            for tab, title in self._legacy_tabs:
                self.tabs.add(tab, text=title)
            self.legacy_button.configure(text="Скрыть инструменты DTR")
        else:
            self.tabs.select(self.ai_tab)
            for tab, _ in self._legacy_tabs:
                self.tabs.hide(tab)
            self.legacy_button.configure(text="Показать инструменты DTR")

    def _ai_widgets(self):
        frame = self.ai_tab
        ttk.Label(frame, text="Анализ своего кода", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Исходники только из Git HEAD · AST-находки — гипотезы · изменение кода лишь после проверки и согласия",
                  foreground="#365573", wraplength=940).pack(anchor="w", pady=(2, 5))

        modebar = ttk.Frame(frame)
        modebar.pack(fill="x", pady=(0, 4))
        self.ai_backend = tk.StringVar(value="own")
        ttk.Radiobutton(modebar, text="Собственный анализатор", variable=self.ai_backend,
                        value="own", command=self._ai_backend_changed).pack(side="left")
        ttk.Radiobutton(modebar, text="Локальная LLM", variable=self.ai_backend,
                        value="ollama", command=self._ai_backend_changed).pack(side="left", padx=(16, 0))
        self.ai_model_bar = ttk.Frame(frame)
        ttk.Label(self.ai_model_bar, text="Модель:").pack(side="left")
        self.ai_model = tk.StringVar(value=DEFAULT_MODEL)
        self.ai_model_entry = ttk.Entry(self.ai_model_bar, textvariable=self.ai_model, width=27)
        self.ai_model_entry.pack(side="left", padx=(6, 12))
        self.ai_model_entry.state(["disabled"])
        self.ai_mode_hint = tk.StringVar(value="Свой движок: AST и локальное ранжирование без интернета.")
        ttk.Label(self.ai_model_bar, textvariable=self.ai_mode_hint,
                  foreground="#5a6474").pack(side="left")

        self.ai_goal_section = ttk.Frame(frame)
        self.ai_goal_section.pack(fill="x", pady=(1, 5))
        ttk.Label(self.ai_goal_section, text="Цель анализа:").pack(anchor="w")
        self.ai_goal = ScrolledText(self.ai_goal_section, wrap="word", height=2,
                                    font=("Segoe UI", 10), undo=True)
        self.ai_goal.pack(fill="x", pady=(2, 0))
        self.ai_goal.insert("1.0", "Проверь архитектуру голосовых команд и NLU, найди потенциальные проблемы и предложи практичные улучшения с доказательствами из исходников.")

        # Keep every change-control button above the expanding report.
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", pady=(2, 5))
        self.ai_button = ttk.Button(toolbar, text="1. Анализировать", style="Primary.TButton",
                                    command=self.start_ai_review)
        self.ai_button.pack(side="left")
        self.ai_proposal_button = ttk.Button(toolbar, text="2. Предложить diff",
                                             command=self.propose_own_finding)
        self.ai_proposal_button.pack(side="left", padx=(6, 0))
        self.ai_proposal_button.state(["disabled"])
        self.ai_verify_button = ttk.Button(toolbar, text="3. Проверить (mock)",
                                           command=self.verify_own_proposal)
        self.ai_verify_button.pack(side="left", padx=(6, 0))
        self.ai_verify_button.state(["disabled"])
        self.ai_apply_button = ttk.Button(toolbar, text="4. Применить с согласия…",
                                          command=self.apply_own_proposal)
        self.ai_apply_button.pack(side="left", padx=(6, 0))
        self.ai_apply_button.state(["disabled"])

        contextbar = ttk.Frame(frame)
        contextbar.pack(fill="x", pady=(0, 4))
        self.ai_context_button = ttk.Button(contextbar, text="Найти код задачи (Git HEAD)",
                                            command=self.start_context_search)
        self.ai_context_button.pack(side="left")
        self.ai_context_copy_button = ttk.Button(contextbar, text="Копировать контекст",
                                                 command=self.copy_context)
        self.ai_context_copy_button.pack(side="left", padx=(6, 0))
        self.ai_context_copy_button.state(["disabled"])
        ttk.Label(contextbar, text="Только чтение · 8 КБ · не создает diff",
                  foreground="#365573").pack(side="left", padx=(12, 0))

        feedbackbar = ttk.Frame(frame)
        feedbackbar.pack(fill="x", pady=(1, 4))
        ttk.Label(feedbackbar, text="Находка:").pack(side="left")
        self.ai_finding_choice = ttk.Combobox(feedbackbar, state="disabled", width=37,
                                               values=())
        self.ai_finding_choice.pack(side="left", padx=(6, 10))
        ttk.Label(feedbackbar, text="Оценка:").pack(side="left")
        self.ai_feedback_choice = ttk.Combobox(feedbackbar, state="readonly", width=17,
                                                values=("Полезная", "Ложная тревога", "Несущественная"))
        self.ai_feedback_choice.current(0)
        self.ai_feedback_choice.pack(side="left", padx=(5, 4))
        self.ai_feedback_button = ttk.Button(feedbackbar, text="Сохранить", command=self.record_own_feedback)
        self.ai_feedback_button.pack(side="left")
        self.ai_feedback_button.state(["disabled"])

        secondary = ttk.Frame(frame)
        secondary.pack(fill="x", pady=(0, 4))
        ttk.Button(secondary, text="Копировать отчёт", command=self.copy_ai_report).pack(side="left")
        self.ai_proposal_copy_button = ttk.Button(secondary, text="Копировать diff", command=self.copy_own_proposal)
        self.ai_proposal_copy_button.pack(side="left", padx=(6, 0))
        self.ai_proposal_copy_button.state(["disabled"])
        ttk.Button(secondary, text="Вернуть отчёт", command=self.show_own_report_again).pack(side="left", padx=(6, 0))
        self.ai_rollback_button = ttk.Button(secondary, text="Откатить M101…", command=self.rollback_own_proposal)
        self.ai_rollback_button.pack(side="left", padx=(6, 0))
        self.ai_extras_button = ttk.Button(secondary, text="Обучение и сведения ▾", command=self.toggle_ai_extras)
        self.ai_extras_button.pack(side="left", padx=(6, 0))

        self.ai_extra_bar = ttk.Frame(frame)
        ttk.Button(self.ai_extra_bar, text="Обучить ранжировщик на оценках",
                   command=self.train_own_feedback_ranker).pack(side="left")
        ttk.Label(self.ai_extra_bar, text="Нужно минимум 20 разных оценок. Это не обучение генеративной LLM.",
                  foreground="#805313").pack(side="left", padx=10)
        self.ai_extras_visible = False

        self.ai_info = tk.StringVar(value="Готово. Собственный анализатор не требует Ollama.")
        self.ai_info_label = ttk.Label(frame, textvariable=self.ai_info, wraplength=960,
                                       foreground="#244a6f")
        self.ai_info_label.pack(fill="x", pady=(3, 5))
        self.ai_text = ScrolledText(frame, wrap="word", height=8, font=("Consolas", 10))
        self.ai_text.pack(fill="both", expand=True)

    def toggle_ai_extras(self):
        self.ai_extras_visible = not self.ai_extras_visible
        if self.ai_extras_visible:
            self.ai_extra_bar.pack(fill="x", pady=(2, 4), before=self.ai_info_label)
            self.ai_extras_button.configure(text="Скрыть обучение ▴")
        else:
            self.ai_extra_bar.pack_forget()
            self.ai_extras_button.configure(text="Обучение и сведения ▾")

    def _ai_backend_changed(self):
        if self.ai_backend.get() == "ollama":
            self.ai_model_entry.state(["!disabled"])
            self.ai_mode_hint.set("Локальная модель через 127.0.0.1; внешние API не используются.")
            self.ai_model_bar.pack(fill="x", before=self.ai_goal_section, pady=(0, 4))
        else:
            self.ai_model_entry.state(["disabled"])
            self.ai_mode_hint.set("Свой движок: AST и локальное обучение приоритетов.")
            self.ai_model_bar.pack_forget()

    def _populate_own_findings(self, report):
        findings = report.get("findings", []) if report.get("schema") == OWN_SCHEMA else []
        self.ai_finding_choice["values"] = [
            f"{i + 1}. {f['file']}:{f['line']} ({f['rule_id']})"
            for i, f in enumerate(findings)]
        if findings:
            self.ai_finding_choice.configure(state="readonly")
            self.ai_finding_choice.current(0)
            self.ai_feedback_button.state(["!disabled"])
            self.ai_proposal_button.state(["!disabled"])
        else:
            self.ai_finding_choice.set("")
            self.ai_finding_choice.configure(state="disabled")
            self.ai_feedback_button.state(["disabled"])
            self.ai_proposal_button.state(["disabled"])
        self.ai_verify_button.state(["disabled"])
        self.ai_apply_button.state(["disabled"])

    def propose_own_finding(self):
        """Explicit click: verify committed source, create in-memory proposal; NEVER apply."""
        try:
            report = self.ai_report
            if not report or report.get("schema") != OWN_SCHEMA:
                raise ValueError("Сначала запусти собственный AST-анализатор.")
            index = self.ai_finding_choice.current()
            if not 0 <= index < len(report.get("findings", [])):
                raise ValueError("Выбери конкретную находку для предложения.")
            finding = report["findings"][index]
            path = finding["file"]
            from .core import validate_target, json_bytes
            validate_target(path)
            if not messagebox.askyesno(
                    "Подготовить предложение (без применения)?",
                    "SkynetVS проверит Git HEAD и рабочую копию одного файла: "
                    + path + "\n\nСоздаст отдельный diff и AST-проверку только при наличии "
                    "строгого рецепта. DTR-A/DTR-B и проверка поведения не выполняются. "
                    "Изменённый относительно HEAD файл отклоняется.\n\nПродолжить?",
                    parent=self.root):
                return
            source = GitSourceReader(self.repository, find_git()).capture(
                self.repository / path, allow_proposal_lf_worktree=True)
            candidate = propose_from_finding(report, finding, source)
            folder = self.store._folder("own_proposal_")
            self.store.write(folder, "M100_Proposal.json", json_bytes(candidate))
            self.store.write(folder, "M100_PatchPreview.txt", candidate["patch_text"].encode("utf-8"))
            self.ai_proposal = candidate
            self.ai_proposal_finding_id = finding["id"]
            self.ai_apply_checked = None
            self.ai_verify_button.state(["!disabled"])
            self.ai_apply_button.state(["disabled"])
            self.ai_proposal_copy_button.state(["!disabled"])
            shown = ("SkynetVS — собственный ограниченный AST-рецепт (не LLM)\n"
                     + "Источник: " + source.path + " @ " + source.base_commit + "\n"
                     + "Новый исходник SHA-256: " + candidate["proposed_sha256"] + "\n"
                     + "DTR-A/DTR-B: НЕ ЗАПУСКАЛИСЬ. Проверка Windows-звука: НЕ ВЫПОЛНЯЛАСЬ.\n"
                     + "Разрешение пользователя на изменение: НЕ ПОЛУЧЕНО. Код не менялся.\n\n"
                     + candidate["explanation"] + "\n\n" + candidate["patch_text"])
            self.set_text(self.ai_text, shown)
            self.ai_info.set("Предложение сохранено вне Git: " + str(folder) + " — только просмотр.")
            self.status.set("SkynetVS самостоятельно подготовил один ограниченный diff. Оцени его; применение закрыто.")
            self.event("M100_OWN_PROPOSAL_PREPARED", recipe=candidate["recipe_id"],
                       finding_id=candidate["finding_id"], target=source.path,
                       approval_state="NOT_APPROVED")
        except Exception as exc:
            self.fail(exc)

    def _m101_finding(self):
        report = self.ai_report
        if not self.ai_proposal or not report or report.get("schema") != OWN_SCHEMA:
            raise ValueError("Сначала запусти AST-анализ и подготовь проверенное предложение.")
        matches = [f for f in report.get("findings", [])
                   if f.get("id") == self.ai_proposal_finding_id]
        if len(matches) != 1:
            raise ValueError("Исходная находка изменилась. Повтори анализ.")
        return report, matches[0]

    def verify_own_proposal(self):
        try:
            if self.ai_busy:
                raise ValueError("Дождись завершения анализа.")
            report, finding = self._m101_finding()
            checked = verify_candidate(self.repository, report, finding, self.ai_proposal)
            self.ai_apply_checked = (checked["before_sha256"], checked["after_sha256"])
            self.ai_apply_button.state(["!disabled"])
            shown = ("M101 — проверка ограниченного изменения (без записи)\n"
                     + "Файл: " + checked["path"] + "\n"
                     + "Источник: " + checked["base_commit"] + "\n"
                     + "SHA исходника: " + checked["before_sha256"] + "\n"
                     + "SHA ожидаемого результата: " + checked["after_sha256"] + "\n\n"
                     + "Mock-сценарии: " + str(len(checked["scenarios"])) + " PASS\n"
                     + "\n".join("  ✓ " + name for name in checked["scenarios"]) + "\n\n"
                     + "ВАЖНО: это тест с подставными audio sessions, не реальный Windows-звук. "
                       "Защита ОС, DTR-B и анализ неизвестных patch не проводились.\n\n"
                     + self.ai_proposal["patch_text"])
            self.set_text(self.ai_text, shown)
            self.ai_info.set("Проверки пройдены. Код не изменён. Применение возможно только после отдельного ввода подтверждения.")
            self.event("M101_MOCK_VERIFIED", target=checked["path"], tests=len(checked["scenarios"]),
                       after_sha=checked["after_sha256"])
            return checked
        except Exception as exc:
            self.ai_apply_checked = None
            self.ai_apply_button.state(["disabled"])
            self.fail(exc)
            return None

    def apply_own_proposal(self):
        try:
            if self.ai_busy or self.ai_apply_checked is None:
                raise ValueError("Сначала нажми «Проверить предложение» и дождись PASS.")
            report, finding = self._m101_finding()
            checked = verify_candidate(self.repository, report, finding, self.ai_proposal)
            if (checked["before_sha256"], checked["after_sha256"]) != self.ai_apply_checked:
                self.ai_apply_button.state(["disabled"])
                raise ValueError("Файл или предложение изменились. Повтори проверку.")
            if not messagebox.askyesno(
                    "M101 — изменение своего кода",
                    "РАЗРЕШАЕТСЯ изменение ровно одного файла: modules/tts_edge.py\n"
                    "Действие: pass → continue при ошибке GetMute().\n\n"
                    "Mock-тесты: 8 PASS. Реальный Windows TTS не проверен.\n"
                    "После записи SkynetVS нужно перезапустить.\n"
                    "Точная резервная копия останется в LOCALAPPDATA; Git не затрагивается.\n"
                    "Никакие иные файлы или изменения LLM не разрешаются.\n\n"
                    "Продолжить к ручному подтверждению?", parent=self.root):
                return
            typed = simpledialog.askstring(
                "Подтверждение M101",
                "Для применения к modules/tts_edge.py введи точно:\nПРИМЕНИТЬ M101",
                parent=self.root)
            if typed is None:
                return
            # Explicit typed consent alone does not override a changed source.
            receipt = apply_approved(self.repository, report, finding, self.ai_proposal, typed)
            self.ai_last_receipt = receipt
            self.ai_apply_checked = None
            self.ai_apply_button.state(["disabled"])
            self.ai_verify_button.state(["disabled"])
            self.ai_info.set("Изменение применено после явного согласия: " + str(receipt) + ". Перезапусти SkynetVS.")
            self.set_text(self.ai_text, "M101: APPROVED_AND_APPLIED (один файл)\n"
                          + "Receipt: " + str(receipt) + "\n"
                          + "Перезапусти SkynetVS; проверь голос и восстановление громкости.\n"
                          + "При необходимости воспользуйся кнопкой «Откатить M101…».\n\n"
                          + self.ai_proposal["patch_text"])
            self.event("M101_ONE_FILE_APPLIED", path='modules/tts_edge.py',
                       after_sha=checked["after_sha256"], approval="TYPED_IN_UI")
        except Exception as exc:
            self.fail(exc)

    def rollback_own_proposal(self):
        try:
            receipt = self.ai_last_receipt
            if receipt is None:
                filename = filedialog.askopenfilename(parent=self.root,
                    title="Выбери M101_Applied.json из каталога Changes",
                    initialdir=str(_changes_root()), filetypes=[("M101 receipt", "*.json")])
                if not filename:
                    return
                receipt = Path(filename)
            if not messagebox.askyesno(
                    "M101 — подтверждение отката",
                    "Откат восстанавливает только исходные байты tts_edge.py, "
                    "если файл не изменялся после M101.\nДругие правки не затрагиваются. "
                    "После отката нужен перезапуск SkynetVS. Продолжить?", parent=self.root):
                return
            typed = simpledialog.askstring("Подтверждение отката M101",
                "Для восстановления исходного файла введи точно:\nОТКАТ M101", parent=self.root)
            if typed is None:
                return
            result = rollback_approved(self.repository, receipt, typed)
            self.ai_last_receipt = None
            self.ai_apply_checked = None
            self.ai_apply_button.state(["disabled"])
            self.ai_info.set("M101 откатил только собственное изменение: " + str(result))
            self.status.set("Восстановлен старый tts_edge.py. Перезапусти SkynetVS.")
            self.event("M101_ONE_FILE_ROLLED_BACK", path='modules/tts_edge.py')
        except Exception as exc:
            self.fail(exc)

    def copy_own_proposal(self):
        if not self.ai_proposal:
            self.ai_info.set("Сначала создай предложение из находки.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self.ai_proposal["patch_text"])
        self.ai_info.set("Diff скопирован только для просмотра. Не применялся.")

    def show_own_report_again(self):
        if not self.ai_report:
            return
        text = (format_own_report(self.ai_report) if self.ai_report.get("schema") == OWN_SCHEMA
                else format_report(self.ai_report))
        self.set_text(self.ai_text, text)
        self.ai_info.set("Показан исходный отчёт. Предложения не применялись.")

    def record_own_feedback(self):
        try:
            report = self.ai_report
            if not report or report.get("schema") != OWN_SCHEMA:
                raise ValueError("Сначала запусти собственный анализатор.")
            index = self.ai_finding_choice.current()
            if not 0 <= index < len(report["findings"]):
                raise ValueError("Выбери замечание для оценки.")
            labels = {"Полезная": "confirmed", "Ложная тревога": "false_positive",
                      "Несущественная": "low_priority"}
            label = labels.get(self.ai_feedback_choice.get())
            if label is None:
                raise ValueError("Выбери допустимую оценку.")
            row = report["findings"][index]
            saved = save_feedback(user_analyzer_directory(), report, row["id"], label)
            self.ai_info.set("Оценка сохранена локально: " + str(saved) + ". Веса не меняются до отдельного обучения.")
            self.event("M097_OWN_FEEDBACK_SAVED", finding_id=row["id"], label=label)
        except Exception as exc:
            self.fail(exc)

    def train_own_feedback_ranker(self):
        try:
            result = train_ranker(user_analyzer_directory())
            if result["weights_written"]:
                message = ("Собственный ранжировщик обучен: " + str(result["total"]) +
                           " оценок. Дальнейший анализ будет менять только порядок находок. "
                           "Независимая точность ещё не измерена.")
            else:
                message = ("Пока недостаточно человеческих оценок: " + str(result["total"]) +
                           ". Нужно 20 разных, оба класса, три файла и два правила.")
            self.ai_info.set(message)
            self.event("M097_OWN_RANKER_TRAIN", status=result["status"], total=result["total"])
        except Exception as exc:
            self.fail(exc)

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

    def start_context_search(self):
        """Explicit read-only opt-in; never enables any code-apply controls."""
        if self.ai_busy:
            return
        goal = self.ai_goal.get("1.0", "end-1c").strip()
        self.ai_busy = True
        self.ai_report = None
        self.ai_proposal = None
        self.ai_proposal_finding_id = None
        self.ai_apply_checked = None
        self.ai_context_text = None
        self._populate_own_findings({})
        self.ai_verify_button.state(["disabled"])
        self.ai_apply_button.state(["disabled"])
        self.ai_proposal_copy_button.state(["disabled"])
        self.ai_context_copy_button.state(["disabled"])
        self.ai_button.state(["disabled"])
        self.ai_context_button.state(["disabled"])
        self.ai_info.set("Ищу подходящие участки Git HEAD (только чтение)…")
        self.set_text(self.ai_text, "Поиск идёт в фоновом потоке. Рабочая копия и код не изменяются.")

        def worker():
            try:
                result = search_repository(self.repository, goal,
                    notify=lambda msg: self.ai_queue.put(("progress", msg)))
                self.ai_queue.put(("context", result))
            except Exception as exc:
                self.ai_queue.put(("error", str(exc)))
        threading.Thread(target=worker, daemon=True).start()
        self.root.after(150, self.poll_ai_review)

    def copy_context(self):
        if not self.ai_context_text or self.ai_busy:
            self.ai_info.set("Сначала выполни поиск кода и дождись завершения.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self.ai_context_text)
        self.ai_info.set("Контекст скопирован вручную. Ничего не отправлено и не применено.")

    def start_ai_review(self):
        if self.ai_busy:
            return
        goal = self.ai_goal.get("1.0", "end-1c").strip()
        model = self.ai_model.get().strip()
        backend = self.ai_backend.get()
        self.ai_busy = True
        self.ai_report = None
        self.ai_context_text = None
        self.ai_context_copy_button.state(["disabled"])
        self.ai_context_button.state(["disabled"])
        self.ai_proposal = None
        self.ai_proposal_finding_id = None
        self.ai_apply_checked = None
        self.ai_verify_button.state(["disabled"])
        self.ai_apply_button.state(["disabled"])
        self.ai_proposal_copy_button.state(["disabled"])
        self._populate_own_findings({})
        self.ai_button.state(["disabled"])
        self.ai_info.set("Проверяю исходники Git HEAD…")
        self.set_text(self.ai_text, "Анализ выполняется в фоновом потоке. Код не изменяется.")

        def worker():
            try:
                if backend == "own":
                    report = analyze_repository(self.repository, goal,
                        data_directory=user_analyzer_directory(),
                        notify=lambda msg: self.ai_queue.put(("progress", msg)))
                else:
                    report = review_repository(self.repository, goal, model,
                        notify=lambda msg: self.ai_queue.put(("progress", msg)))
                self.ai_queue.put(("report", report))
            except Exception as exc:
                self.ai_queue.put(("error", str(exc)))
        threading.Thread(target=worker, daemon=True).start()
        self.root.after(150, self.poll_ai_review)

    def poll_ai_review(self):
        finished = False
        while True:
            try:
                kind, value = self.ai_queue.get_nowait()
            except queue.Empty:
                break
            if kind == "progress":
                self.ai_info.set(value)
            elif kind == "context":
                finished = True
                try:
                    receipt = receipt_without_source(value)
                    folder = self.store._folder("context_search_")
                    self.store.write(folder, "M134_ContextReceipt.json", json_bytes(receipt))
                    self.ai_context_text = format_context(value)
                    self.set_text(self.ai_text, self.ai_context_text)
                    self.ai_context_copy_button.state(["!disabled"])
                    self.ai_info.set("Контекст готов (не патч). Полученные исходники видны только в окне; квитанция: " + str(folder))
                    self.event("M134_READONLY_CONTEXT_FOUND", commit=value["git_commit"],
                               windows=len(value["contexts_metadata"]["8192"]["ranges"]),
                               goal_sha256=value["goal_sha256"])
                except Exception as exc:
                    self.ai_info.set("Не удалось оформить контекст: " + str(exc))
            elif kind == "report":
                finished = True
                self.ai_report = value
                try:
                    if value.get("schema") == OWN_SCHEMA:
                        folder = save_own_report(self.store, value)
                        shown = format_own_report(value)
                        self._populate_own_findings(value)
                        self.event("M097_OWN_ANALYSIS_CREATED", findings=len(value["findings"]),
                                   commit=value["git_commit"])
                    else:
                        folder = save_report(self.store, value)
                        shown = format_report(value)
                        self._populate_own_findings({})
                        self.event("M095_LOCAL_AI_REVIEW_CREATED", findings=len(value["findings"]),
                                   rejected=value["rejected_ungrounded_findings"],
                                   commit=value["git_commit"], model=value["model"])
                    self.set_text(self.ai_text, shown)
                    self.ai_info.set("Отчёт сохранён: " + str(folder))
                except Exception as exc:
                    self.ai_info.set("Не удалось сохранить отчёт: " + str(exc))
            elif kind == "error":
                finished = True
                self.ai_info.set("Анализ не выполнен: " + value)
                self.set_text(self.ai_text, "Ошибка: " + value + "\nНичего не изменено.")
                self.event("M097_ANALYSIS_REFUSED", reason=value[:300])
        if finished:
            self.ai_busy = False
            self.ai_button.state(["!disabled"])
            self.ai_context_button.state(["!disabled"])
        elif self.ai_busy:
            self.root.after(150, self.poll_ai_review)

    def copy_ai_report(self):
        if self.ai_report is None:
            self.ai_info.set("Сначала выполни анализ.")
            return
        displayed = (format_own_report(self.ai_report)
                     if self.ai_report.get("schema") == OWN_SCHEMA
                     else format_report(self.ai_report))
        self.root.clipboard_clear()
        self.root.clipboard_append(displayed)
        self.ai_info.set("Отчёт скопирован. Код не изменён.")

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
