from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal, TextIO
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_LOG_DIR = PROJECT_ROOT / "data" / "logs" / "pipeline"


@dataclass(frozen=True)
class Step:
    name: str
    cmd: list[str]
    interactive: bool = False


# These evaluators explicitly skip with exit 0 on non-Windows hosts.
# Keep this registry separate from available_flows: inventory consumers parse
# its literal Step calls. Hard-failing platform gates and portable checks are
# deliberately not listed, even if their filenames end in "_windows.py".
WINDOWS_SKIP_SCRIPTS = frozenset({
    "tools/eval_audio_control_windows.py",
    "tools/eval_developer_task_execution_boundary_crypto_windows.py",
    "tools/eval_developer_task_execution_boundary_worker_windows.py",
    "tools/eval_developer_task_execution_compile_ast_claim_transaction_windows.py",
    "tools/eval_developer_task_execution_compile_ast_composition_windows.py",
    "tools/eval_developer_task_execution_compile_ast_controller_worker_windows.py",
    "tools/eval_developer_task_execution_compile_ast_plan_windows.py",
    "tools/eval_developer_task_execution_compile_ast_verifier_windows.py",
    "tools/eval_developer_task_execution_environment_inventory_windows.py",
    "tools/eval_developer_task_execution_runtime_attestation_crypto_windows.py",
    "tools/eval_developer_task_execution_runtime_attestation_windows.py",
    "tools/eval_developer_task_execution_runtime_bundle_windows.py",
    "tools/eval_developer_task_execution_runtime_lease_windows.py",
    "tools/eval_developer_task_execution_toolchain_observation_windows.py",
    "tools/eval_developer_task_execution_workspace_snapshot_windows.py",
})

StepStatus = Literal["PASS", "FAIL", "SKIP", "NOT_RUN"]


@dataclass(frozen=True)
class StepResult:
    name: str
    status: StepStatus
    returncode: int | None
    reason: str = ""
    reason_code: str = ""


FlowStatus = Literal["PASS", "FAIL", "INCOMPLETE"]


@dataclass(frozen=True)
class FlowResult:
    flow: str
    steps: tuple[StepResult, ...]
    returncode: int
    reason_code: str = ""
    run_id: str = field(default_factory=lambda: uuid4().hex)

    @property
    def status(self) -> FlowStatus:
        if self.returncode != 0 or not self.steps or any(
                step.status == "FAIL" for step in self.steps):
            return "FAIL"
        if any(step.status != "PASS" for step in self.steps):
            return "INCOMPLETE"
        return "PASS"

    @property
    def counts(self) -> dict[str, int]:
        counts = {status: sum(step.status == status for step in self.steps)
                  for status in ("PASS", "FAIL", "SKIP", "NOT_RUN")}
        counts["TOTAL"] = len(self.steps)
        return counts

    def to_dict(self) -> dict[str, object]:
        """Versioned result metadata; raw output, commands and paths stay in logs."""
        return {
            "kind": "SKYNETVS_PIPELINE_RESULT_V1",
            "schema_version": 1,
            "run_id": self.run_id,
            "flow": self.flow,
            "status": self.status,
            "all_steps_passed": self.status == "PASS",
            "returncode": self.returncode,
            "reason_code": self.reason_code,
            "counts": self.counts,
            "steps": [
                {"index": index, "name": step.name, "status": step.status,
                 "returncode": step.returncode, "reason_code": step.reason_code}
                for index, step in enumerate(self.steps, 1)
            ],
        }


@dataclass(frozen=True)
class CommandEffects:
    effects: tuple[str, ...]
    description: str
    default_inputs: tuple[str, ...] = ()
    default_outputs: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


# Descriptions of known application effects for these exact default commands.
# This is an explanation, not an execution policy or a read-only guarantee.
# Keep it outside available_flows: static inventory consumes that literal AST.
COMMAND_EFFECTS: dict[str, CommandEffects] = {
    "tools/command_audit.py": CommandEffects(
        ("READ_DATA", "READ_SOURCE", "REPORT_STDOUT"),
        "Read the command registry, templates and Actions source text; print findings.",
        ("data/intents.json", "data/say_templates.json", "modules/actions.py"),
        notes=("Actions source is read as text, not imported or executed.",)),
    "tools/learning_report.py": CommandEffects(
        ("READ_DATA", "REPORT_STDOUT"),
        "Read learning records and print analysis reports.",
        ("data/learning/command_history.jsonl", "data/learning/nlu_hard_cases.jsonl",
         "data/learning/action_failures.jsonl", "data/learning/resolver_candidates.jsonl")),
    "tools/build_correction_memory.py": CommandEffects(
        ("READ_DATA", "WRITE_DATA", "REPORT_STDOUT"),
        "Build or update correction memory from learning records.",
        ("data/learning/command_history.jsonl", "data/learning/nlu_hard_cases.jsonl",
         "data/learning/action_failures.jsonl", "data/learning/resolver_candidates.jsonl",
         "data/learning/correction_memory.jsonl"),
        ("data/learning/correction_memory.jsonl",),
        ("Repeated upserts can increase seen_count for existing evidence.",)),
    "tools/correction_memory_report.py": CommandEffects(
        ("READ_DATA", "REPORT_STDOUT"),
        "Read correction memory and print candidate summaries.",
        ("data/learning/correction_memory.jsonl",)),
    "tools/promotion_report.py": CommandEffects(
        ("READ_DATA", "REPORT_STDOUT"),
        "Read correction memory and print promotion suggestions.",
        ("data/learning/correction_memory.jsonl",)),
    "tools/export_promotions.py": CommandEffects(
        ("READ_DATA", "WRITE_DATA", "REPORT_STDOUT"),
        "Export promotion suggestions; rewrite the inbox and suggestion files.",
        ("data/learning/correction_memory.jsonl", "data/intents.json", "data/inbox_unlabeled.jsonl",
         "data/learning/alias_suggestions.jsonl", "data/learning/phrase_correction_suggestions.jsonl"),
        ("data/inbox_unlabeled.jsonl", "data/learning/alias_suggestions.jsonl",
         "data/learning/phrase_correction_suggestions.jsonl"),
        ("Output files are rewritten even when no new suggestions are added.",)),
    "tools/export_learning_to_inbox.py": CommandEffects(
        ("READ_DATA", "WRITE_DATA", "REPORT_STDOUT"),
        "Export raw learning cases and rewrite the unlabeled inbox.",
        ("data/learning/nlu_hard_cases.jsonl", "data/learning/resolver_candidates.jsonl",
         "data/inbox_unlabeled.jsonl"),
        ("data/inbox_unlabeled.jsonl",),
        ("The inbox is rewritten even when no new cases are added.",)),
    "tools/label_inbox.py": CommandEffects(
        ("READ_DATA", "WRITE_DATA", "INTERACTIVE", "REPORT_STDOUT"),
        "Interactively label pending cases and update training examples and labeled records.",
        ("data/intents.json", "data/inbox_unlabeled.jsonl", "data/inbox_labeled.jsonl"),
        ("data/intents.json", "data/inbox_labeled.jsonl"),
        ("With pending cases, quit or skip can still reach the final file rewrites.",)),
    "train/train_nlu.py": CommandEffects(
        ("READ_DATA", "TRAIN_MODEL", "WRITE_MODEL", "REPORT_STDOUT"),
        "Fit the NLU model and overwrite the active model before the printed quick test.",
        ("data/intents.json", "data/nlu_training_recipe.json"),
        ("models/nlu_intent.joblib",),
        ("Training has no interactive confirmation in this command.",)),
    "tools/eval_nlu.py": CommandEffects(
        ("READ_CONFIG", "READ_DATA", "LOAD_MODEL", "REPORT_STDOUT"),
        "Evaluate NLU predictions using configuration, examples and the current model.",
        (".env", "data/intents.json", "data/say_templates.json",
         "data/inbox_labeled.jsonl", "models/nlu_intent.joblib"),
        notes=("Predicts intents; it does not dispatch the predicted desktop actions.",)),
    "tools/eval_nlu_diagnostics.py": CommandEffects(
        ("READ_CONFIG", "READ_DATA", "LOAD_MODEL", "REPORT_STDOUT"),
        "Print NLU candidate diagnostics using the current configuration and model.",
        (".env", "data/intents.json", "data/say_templates.json",
         "data/inbox_labeled.jsonl", "models/nlu_intent.joblib")),
    "tools/eval_nlu_risk_report.py": CommandEffects(
        ("READ_CONFIG", "READ_DATA", "LOAD_MODEL", "REPORT_STDOUT"),
        "Print NLU risk results using the current configuration and model.",
        (".env", "data/intents.json", "data/say_templates.json",
         "data/inbox_labeled.jsonl", "models/nlu_intent.joblib")),
    "tools/eval_nlu_risk_guard.py": CommandEffects(
        ("READ_CONFIG", "READ_DATA", "LOAD_MODEL", "REPORT_STDOUT"),
        "Evaluate the NLU risk guard using the current configuration and model.",
        (".env", "data/intents.json", "data/say_templates.json",
         "data/inbox_labeled.jsonl", "models/nlu_intent.joblib")),
    "tools/eval_reply_builder.py": CommandEffects(
        ("READ_CONFIG", "REPORT_STDOUT"),
        "Read configuration and run reply-builder cases with fake routers.",
        (".env",),
        notes=("Current fake-router cases do not call model prediction.",)),
}


def describe_flow(flow_name: str) -> dict[str, object]:
    """Describe known effects without importing or executing a child command."""
    steps = available_flows().get(flow_name)
    descriptions = []
    for index, step in enumerate(steps or (), 1):
        canonical = len(step.cmd) == 2 and step.cmd[0] == sys.executable
        effects = COMMAND_EFFECTS.get(step.cmd[1]) if canonical else None
        descriptions.append({
            "index": index,
            "name": step.name,
            "review": "REVIEWED" if effects is not None else "UNREVIEWED",
            "effects": list(effects.effects) if effects is not None else ["UNREVIEWED"],
            "description": effects.description if effects is not None else
                "Effects of this exact command have not been reviewed; inspect its source before use.",
            "default_inputs": list(effects.default_inputs) if effects is not None else [],
            "default_outputs": list(effects.default_outputs) if effects is not None else [],
            "notes": list(effects.notes) if effects is not None else [],
            "interactive": step.interactive,
        })
    reviewed = sum(item["review"] == "REVIEWED" for item in descriptions)
    return {
        "kind": "SKYNETVS_PIPELINE_DESCRIPTION_V1",
        "schema_version": 1,
        "flow": flow_name,
        "known_flow": bool(steps),
        "execution": "NOT_RUN",
        "reason_code": "" if steps else "unknown_flow",
        "counts": {"REVIEWED": reviewed, "UNREVIEWED": len(descriptions) - reviewed,
                   "TOTAL": len(descriptions)},
        "effects": sorted({effect for item in descriptions for effect in item["effects"]}),
        "steps": descriptions,
        "notes": [
            "These are known effects of exact default commands, not an exhaustive filesystem guarantee.",
            "Paths show defaults from the project root; configuration can affect runtime behavior.",
            "Inputs may be conditional; .env is discovered by python-dotenv and LOAD_MODEL means potential loading.",
            "Ordinary Python commands may also create bytecode caches or diagnostic logs.",
            "--no-log controls only the runner text log, not the actions of child commands.",
        ],
    }


def print_flow_description(flow_name: str) -> int:
    description = describe_flow(flow_name)
    if not description["known_flow"]:
        _emit(f"[FAIL] Unknown flow: {flow_name}; no steps executed.")
        return 2
    _emit(f"[DESCRIBE] Flow '{flow_name}'; execution=NOT_RUN")
    counts = description["counts"]
    _emit("Coverage: " + "; ".join(f"{name}={value}" for name, value in counts.items()))
    _emit("Known potential effects: " + ", ".join(description["effects"]))
    for item in description["steps"]:
        _emit(f"{item['index']}. {item['name']} [{item['review']}]")
        _emit("   " + item["description"])
        _emit("   Effects: " + ", ".join(item["effects"]))
        if item["default_inputs"]:
            _emit("   Default inputs: " + ", ".join(item["default_inputs"]))
        if item["default_outputs"]:
            _emit("   Default outputs: " + ", ".join(item["default_outputs"]))
        for note in item["notes"]:
            _emit("   " + note)
    for note in description["notes"]:
        _emit("Note: " + note)
    _emit("No steps executed. No pipeline log or JSON result file created.")
    return 0


def _is_windows() -> bool:
    return os.name == "nt" and sys.platform == "win32"


def _skip_reason(step: Step) -> str:
    # Match the exact registered command shape, not arbitrary child output or
    # a path that happens to appear among another command's arguments.
    if (len(step.cmd) == 2 and step.cmd[0] == sys.executable
            and step.cmd[1] in WINDOWS_SKIP_SCRIPTS and not _is_windows()):
        return "requires Windows; not run on this platform"
    return ""


def _step_result(step: Step, status: StepStatus, returncode: int | None,
                 reason: str, log_file: TextIO | None, *,
                 reason_code: str = "") -> StepResult:
    suffix = f": {reason}" if reason else ""
    _emit(f"[{status}] {step.name}{suffix}", log_file)
    return StepResult(step.name, status, returncode, reason, reason_code)


def _python_cmd(*args: str) -> list[str]:
    return [sys.executable, *args]


def available_flows() -> dict[str, list[Step]]:
    return {
        "audit": [
            Step("Command audit", _python_cmd("tools/command_audit.py")),
        ],
        "check": [
            Step("Command audit", _python_cmd("tools/command_audit.py")),
            Step("Evaluate intent rule policy", _python_cmd("tools/eval_intent_rule_policy.py")),
            Step("Evaluate NLU config contract", _python_cmd("tools/eval_nlu_config_contract.py")),
            Step("Evaluate entity registry", _python_cmd("tools/eval_entity_registry.py")),
            Step("Evaluate actions registry integration", _python_cmd("tools/eval_actions_registry.py")),
            Step("Evaluate registry cleanup", _python_cmd("tools/eval_registry_cleanup.py")),
            Step("Evaluate NLU", _python_cmd("tools/eval_nlu.py")),
            Step("Evaluate dictation intent separation", _python_cmd("tools/eval_dictation_intent_separation.py")),
            Step("Evaluate backspace intent separation", _python_cmd("tools/eval_backspace_intent_separation.py")),
            Step("NLU risk guard", _python_cmd("tools/eval_nlu_risk_guard.py")),
            Step("Evaluate command decision", _python_cmd("tools/eval_command_decision.py")),
            Step("Evaluate confirmation", _python_cmd("tools/eval_confirmation.py")),
            Step("Evaluate dictation commands", _python_cmd("tools/eval_dictation_commands.py")),
            Step("Evaluate hotword utils", _python_cmd("tools/eval_hotword_utils.py")),
            Step("Evaluate command fragments", _python_cmd("tools/eval_command_fragments.py")),
            Step("Evaluate duration parser", _python_cmd("tools/eval_duration_parser.py")),
            Step("Evaluate timer service", _python_cmd("tools/eval_timer_service.py")),
            Step("Evaluate timer actions", _python_cmd("tools/eval_timer_actions.py")),
            Step("Evaluate timer command runtime", _python_cmd("tools/eval_timer_command_runtime.py")),
            Step("Evaluate reminder repository", _python_cmd("tools/eval_reminder_repository.py")),
            Step("Evaluate reminder datetime parser", _python_cmd("tools/eval_reminder_datetime.py")),
            Step("Evaluate reminder service", _python_cmd("tools/eval_reminder_service.py")),
            Step("Evaluate reminder command parser", _python_cmd("tools/eval_reminder_command_parser.py")),
            Step("Evaluate reminder actions", _python_cmd("tools/eval_reminder_actions.py")),
            Step("Evaluate reminder runtime wiring", _python_cmd("tools/eval_reminder_runtime.py")),
            Step("Evaluate TTS settings", _python_cmd("tools/eval_tts_settings.py")),
            Step("Evaluate TTS runtime", _python_cmd("tools/eval_tts_runtime.py")),
            Step("Evaluate TTS lifecycle", _python_cmd("tools/eval_tts_lifecycle.py")),
            Step("Evaluate TTS health integration", _python_cmd("tools/eval_tts_health_runtime.py")),
            Step("Evaluate audio control", _python_cmd("tools/eval_audio_control.py")),
            Step("Evaluate audio control Windows smoke", _python_cmd("tools/eval_audio_control_windows.py")),
            Step("Evaluate audio control actions", _python_cmd("tools/eval_audio_control_actions.py")),
            Step("Evaluate audio control health integration", _python_cmd("tools/eval_audio_control_health_runtime.py")),
            Step("Evaluate audio output", _python_cmd("tools/eval_audio_output.py")),
            Step("Evaluate audio output actions", _python_cmd("tools/eval_audio_output_actions.py")),
            Step("Evaluate operation telemetry", _python_cmd("tools/eval_operation_telemetry.py")),
            Step("Evaluate weather service", _python_cmd("tools/eval_weather_service.py")),
            Step("Evaluate weather health integration", _python_cmd("tools/eval_weather_health_runtime.py")),
            Step("Evaluate runtime service health", _python_cmd("tools/eval_runtime_service_health.py")),
            Step("Evaluate runtime service health runtime", _python_cmd("tools/eval_runtime_service_health_runtime.py")),
            Step("Evaluate runtime health monitor", _python_cmd("tools/eval_runtime_service_health_monitor.py")),
            Step("Evaluate runtime service health command", _python_cmd("tools/eval_runtime_service_health_command.py")),
            Step("Evaluate speech IO", _python_cmd("tools/eval_speech_io.py")),
            Step("Evaluate STT refinement", _python_cmd("tools/eval_stt_refinement.py")),
            Step("Evaluate STT lifecycle", _python_cmd("tools/eval_stt_lifecycle.py")),
            Step("Evaluate STT health integration", _python_cmd("tools/eval_stt_health_runtime.py")),
            Step("Evaluate STT diagnostics", _python_cmd("tools/eval_stt_diagnostics.py")),
            Step("Evaluate STT missing slots trigger", _python_cmd("tools/eval_stt_missing_slots_trigger.py")),
            Step("Evaluate STT Whisper subprocess sandbox", _python_cmd("tools/eval_stt_whisper_subprocess.py")),
            Step("Evaluate reply builder", _python_cmd("tools/eval_reply_builder.py")),
            Step("Evaluate command understanding", _python_cmd("tools/eval_command_understanding.py")),
            Step("Evaluate command outcome", _python_cmd("tools/eval_command_outcome.py")),
            Step("Evaluate command learning", _python_cmd("tools/eval_command_learning.py")),
            Step("Evaluate speech interrupt", _python_cmd("tools/eval_speech_interrupt.py")),
            Step("Evaluate phrase guards", _python_cmd("tools/eval_phrase_guards.py")),
            Step("Evaluate dictation runtime", _python_cmd("tools/eval_dictation_runtime.py")),
            Step("Evaluate confirmation runtime", _python_cmd("tools/eval_confirmation_runtime.py")),
            Step("Evaluate hotword activation runtime", _python_cmd("tools/eval_hotword_activation_runtime.py")),
            Step("Evaluate command window runtime", _python_cmd("tools/eval_command_window_runtime.py")),
            Step("Evaluate command runtime", _python_cmd("tools/eval_command_runtime.py")),
            Step("Evaluate command processor", _python_cmd("tools/eval_command_processor.py")),
            Step("Evaluate phrase event processor", _python_cmd("tools/eval_phrase_event_processor.py")),
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate SCM01 host worker source contract", _python_cmd("tools/eval_scm01_host_worker.py")),
            Step("Evaluate action execution boundary", _python_cmd("-I", "-S", "-B", "tools/eval_action_execution_boundary.py")),
            Step("Evaluate HWA02-B1 timer action runtime", _python_cmd("tools/eval_timer_action_runtime.py")),
            Step("Evaluate HWA02-B2 volume action runtime", _python_cmd("tools/eval_volume_action_runtime.py")),
            Step("Evaluate developer task contract", _python_cmd("tools/eval_developer_task_contract.py")),
            Step("Evaluate developer task proposal intake", _python_cmd("tools/eval_developer_task_proposal_intake.py")),
            Step("Evaluate developer task static rehearsal", _python_cmd("tools/eval_developer_task_rehearsal.py")),
            Step("Evaluate developer task repository preflight", _python_cmd("tools/eval_developer_task_preflight.py")),
            Step("Evaluate developer task patch integrity preflight", _python_cmd("tools/eval_developer_task_patch_integrity.py")),
            Step("Evaluate developer task isolated patch index preflight", _python_cmd("tools/eval_developer_task_patch_index.py")),
            Step("Evaluate developer task patch scope policy preflight", _python_cmd("tools/eval_developer_task_patch_scope.py")),
            Step("Evaluate developer task complete preflight composition", _python_cmd("tools/eval_developer_task_preflight_composition.py")),
            Step("Evaluate developer task independent repository workspace", _python_cmd("tools/eval_developer_task_workspace.py")),
            Step("Evaluate developer task workspace cleanup lifecycle", _python_cmd("tools/eval_developer_task_workspace_cleanup.py")),
            Step("Evaluate developer task patch apply", _python_cmd("tools/eval_developer_task_patch_apply.py")),
            Step("Evaluate developer task static check evidence", _python_cmd("tools/eval_developer_task_check_static.py")),
            Step("Evaluate developer task execution backend host capability", _python_cmd("tools/eval_developer_task_execution_backend_host.py")),
            Step("Evaluate developer task execution backend lifecycle", _python_cmd("tools/eval_developer_task_execution_backend_lifecycle.py")),
            Step("Evaluate developer task signed transcript verifier", _python_cmd("tools/eval_developer_task_execution_boundary_verifier.py")),
            Step("Evaluate developer task standard-user worker isolation bundle", _python_cmd("tools/eval_developer_task_execution_boundary_worker.py")),
            Step("Evaluate developer task active signed boundary composition", _python_cmd("tools/eval_developer_task_execution_boundary_composition.py")),
            Step("Evaluate developer task deterministic trusted runtime bundle", _python_cmd("tools/eval_developer_task_execution_runtime_bundle.py")),
            Step("Evaluate developer task trusted runtime attestation contract and payload", _python_cmd("tools/eval_developer_task_execution_runtime_attestation.py")),
            Step("Evaluate developer task signed runtime transcript verifier", _python_cmd("tools/eval_developer_task_execution_runtime_attestation_verifier.py")),
            Step("Evaluate developer task active trusted runtime composition", _python_cmd("tools/eval_developer_task_execution_runtime_composition.py")),
            Step("Evaluate developer task same-run runtime capability lease", _python_cmd("tools/eval_developer_task_execution_runtime_lease.py")),
            Step("Evaluate developer task executable environment inventory", _python_cmd("tools/eval_developer_task_execution_environment_inventory.py")),
            Step("Evaluate developer task canonical host toolchain observation", _python_cmd("tools/eval_developer_task_execution_toolchain_observation.py")),
            Step("Evaluate developer task canonical dependency profile target contract", _python_cmd("tools/eval_developer_task_execution_dependency_profile.py")),
            Step("Evaluate developer task non-network dependency acquisition contract", _python_cmd("tools/eval_developer_task_execution_dependency_acquisition.py")),
            Step("Evaluate developer task canonical patched workspace snapshot", _python_cmd("tools/eval_developer_task_execution_workspace_snapshot.py")),
            Step("Evaluate developer task typed compile AST plan capability", _python_cmd("tools/eval_developer_task_execution_compile_ast_plan.py")),
            Step("Evaluate developer task canonical compile AST contract", _python_cmd("tools/eval_developer_task_execution_compile_ast_contract.py")),
            Step("Evaluate developer task fixed compile AST guest runner bundle", _python_cmd("tools/eval_developer_task_execution_compile_ast_runner.py")),
            Step("Evaluate developer task signed compile AST transcript verifier", _python_cmd("tools/eval_developer_task_execution_compile_ast_verifier.py")),
            Step("Evaluate developer task process-local compile AST claim transaction", _python_cmd("tools/eval_developer_task_execution_compile_ast_claim_transaction.py")),
            Step("Evaluate developer task fixed compile AST controller-worker bundle", _python_cmd("tools/eval_developer_task_execution_compile_ast_controller_worker.py")),
            Step("Evaluate developer task active compile AST Sandbox composition", _python_cmd("tools/eval_developer_task_execution_compile_ast_composition.py")),
            Step("Evaluate developer task V1C2C3 live acceptance contract", _python_cmd("tools/eval_developer_task_execution_compile_ast_live_acceptance.py")),
            Step("Evaluate runtime architecture audit", _python_cmd("tools/eval_runtime_architecture_audit.py")),
        ],
        "decision": [
            Step("Evaluate command decision", _python_cmd("tools/eval_command_decision.py")),
        ],
        "confirmation": [
            Step("Evaluate confirmation", _python_cmd("tools/eval_confirmation.py")),
        ],
        "analyze": [
            Step("Learning report", _python_cmd("tools/learning_report.py")),
            Step("Build correction memory", _python_cmd("tools/build_correction_memory.py")),
            Step("Correction memory report", _python_cmd("tools/correction_memory_report.py")),
            Step("Promotion report", _python_cmd("tools/promotion_report.py")),
            Step("Evaluate reply builder", _python_cmd("tools/eval_reply_builder.py")),
        ],
        "promote": [
            Step("Export promotions", _python_cmd("tools/export_promotions.py")),
        ],
        "raw_inbox": [
            Step("Export learning to inbox", _python_cmd("tools/export_learning_to_inbox.py")),
        ],
        "label": [
            Step("Label inbox", _python_cmd("tools/label_inbox.py"), interactive=True),
        ],
        "train": [
            Step("Train NLU", _python_cmd("train/train_nlu.py")),
        ],
        "eval": [
            Step("Evaluate NLU", _python_cmd("tools/eval_nlu.py")),
        ],
        "nlu_diag": [
            Step("Evaluate NLU diagnostics", _python_cmd("tools/eval_nlu_diagnostics.py")),
        ],
        "nlu_risk": [
            Step("NLU risk report", _python_cmd("tools/eval_nlu_risk_report.py")),
        ],
        "nlu_risk_guard": [
            Step("NLU risk guard", _python_cmd("tools/eval_nlu_risk_guard.py")),
        ],
        "full": [
            Step("Learning report", _python_cmd("tools/learning_report.py")),
            Step("Build correction memory", _python_cmd("tools/build_correction_memory.py")),
            Step("Correction memory report", _python_cmd("tools/correction_memory_report.py")),
            Step("Promotion report", _python_cmd("tools/promotion_report.py")),
            Step("Export promotions", _python_cmd("tools/export_promotions.py")),
        ],
        "dictation": [
            Step("Evaluate dictation commands", _python_cmd("tools/eval_dictation_commands.py")),
        ],
        "dictation_intent": [
            Step("Evaluate dictation intent separation", _python_cmd("tools/eval_dictation_intent_separation.py")),
        ],
        "backspace_intent": [
            Step("Evaluate backspace intent separation", _python_cmd("tools/eval_backspace_intent_separation.py")),
        ],
        "hotword": [
            Step("Evaluate hotword utils", _python_cmd("tools/eval_hotword_utils.py")),
        ],
        "fragments": [
            Step("Evaluate command fragments", _python_cmd("tools/eval_command_fragments.py")),
        ],
        "speech": [
            Step("Evaluate speech IO", _python_cmd("tools/eval_speech_io.py")),
        ],
        "main_inventory": [
            Step("Main.py inventory", _python_cmd("tools/main_inventory.py")),
        ],
        "stt_refinement": [
            Step("Evaluate STT refinement", _python_cmd("tools/eval_stt_refinement.py")),
        ],
        "stt_diagnostics": [
            Step("Evaluate STT diagnostics", _python_cmd("tools/eval_stt_diagnostics.py")),
        ],
        "stt_lifecycle": [
            Step("Evaluate STT lifecycle", _python_cmd("tools/eval_stt_lifecycle.py")),
            Step("Evaluate STT health integration", _python_cmd("tools/eval_stt_health_runtime.py")),
        ],
        "stt_missing_slots": [
            Step("Evaluate STT missing slots trigger", _python_cmd("tools/eval_stt_missing_slots_trigger.py")),
        ],
        "stt_whisper_subprocess": [
            Step("Evaluate STT Whisper subprocess sandbox", _python_cmd("tools/eval_stt_whisper_subprocess.py")),
        ],
        "stt_runtime_report": [
            Step("STT runtime report", _python_cmd("tools/stt_runtime_report.py", "--only-problems")),
        ],
        "stt_quality": [
            Step("Run STT quality baseline", _python_cmd("tools/stt_quality_session.py", "run",), interactive=True,),
        ],
        "stt_quality_report": [
            Step("Show latest STT quality baseline", _python_cmd("tools/stt_quality_session.py", "report", )),
        ],
        "reply": [
            Step("Evaluate reply builder", _python_cmd("tools/eval_reply_builder.py")),
        ],
        "understanding": [
            Step("Evaluate command understanding", _python_cmd("tools/eval_command_understanding.py")),
        ],
        "outcome": [
            Step("Evaluate command outcome", _python_cmd("tools/eval_command_outcome.py")),
        ],
        "learning": [
            Step("Evaluate command learning", _python_cmd("tools/eval_command_learning.py")),
        ],
        "speech_interrupt": [
            Step("Evaluate speech interrupt", _python_cmd("tools/eval_speech_interrupt.py")),
        ],
        "phrase_guards": [
            Step("Evaluate phrase guards", _python_cmd("tools/eval_phrase_guards.py")),
        ],
        "dictation_runtime": [
            Step("Evaluate dictation runtime", _python_cmd("tools/eval_dictation_runtime.py")),
        ],
        "confirmation_runtime": [
            Step("Evaluate confirmation runtime", _python_cmd("tools/eval_confirmation_runtime.py")),
        ],
        "hotword_activation": [
            Step("Evaluate hotword activation runtime", _python_cmd("tools/eval_hotword_activation_runtime.py")),
        ],
        "command_window": [
            Step("Evaluate command window runtime", _python_cmd("tools/eval_command_window_runtime.py")),
        ],
        "command_runtime": [
            Step("Evaluate command runtime", _python_cmd("tools/eval_command_runtime.py")),
        ],
        "command_processor": [
            Step("Evaluate command processor", _python_cmd("tools/eval_command_processor.py")),
        ],
        "phrase_event": [
            Step("Evaluate phrase event processor", _python_cmd("tools/eval_phrase_event_processor.py")),
        ],
        "registry": [
            Step("Evaluate entity registry", _python_cmd("tools/eval_entity_registry.py")),
        ],
        "actions_registry": [
            Step("Evaluate actions registry integration", _python_cmd("tools/eval_actions_registry.py")),
        ],
        "registry_cleanup": [
            Step("Evaluate registry cleanup", _python_cmd("tools/eval_registry_cleanup.py")),
        ],
        "duration": [
            Step("Evaluate duration parser", _python_cmd("tools/eval_duration_parser.py")),
        ],
        "timer_service": [
            Step("Evaluate timer service", _python_cmd("tools/eval_timer_service.py")),
        ],
        "timer_actions": [
            Step("Evaluate timer actions", _python_cmd("tools/eval_timer_actions.py" )),
        ],
        "timer_command_runtime": [
            Step("Evaluate timer command runtime", _python_cmd("tools/eval_timer_command_runtime.py")),
        ],
        "reminder_repository": [
            Step("Evaluate reminder repository", _python_cmd("tools/eval_reminder_repository.py")),
        ],
        "reminder_datetime": [
            Step("Evaluate reminder datetime parser", _python_cmd("tools/eval_reminder_datetime.py")),
        ],
        "reminder_service": [
            Step("Evaluate reminder service", _python_cmd("tools/eval_reminder_service.py")),
        ],
        "reminder_command_parser": [
            Step("Evaluate reminder command parser", _python_cmd("tools/eval_reminder_command_parser.py")),
        ],
        "reminder_actions": [
            Step("Evaluate reminder actions", _python_cmd("tools/eval_reminder_actions.py")),
        ],
        "reminder_runtime": [
            Step("Evaluate reminder runtime wiring", _python_cmd("tools/eval_reminder_runtime.py")),
        ],
        "tts_settings": [
            Step("Evaluate TTS settings", _python_cmd("tools/eval_tts_settings.py")),
        ],
        "tts_runtime": [
            Step("Evaluate TTS runtime", _python_cmd("tools/eval_tts_runtime.py")),
            Step("Evaluate TTS lifecycle", _python_cmd("tools/eval_tts_lifecycle.py")),
            Step("Evaluate TTS health integration", _python_cmd("tools/eval_tts_health_runtime.py")),
        ],
        "audio_control": [
            Step("Evaluate audio control", _python_cmd("tools/eval_audio_control.py")),
            Step("Evaluate audio control Windows smoke", _python_cmd("tools/eval_audio_control_windows.py")),
            Step("Evaluate audio control actions", _python_cmd("tools/eval_audio_control_actions.py")),
            Step("Evaluate audio control health integration", _python_cmd("tools/eval_audio_control_health_runtime.py")),
        ],
        "audio_control_actions": [
            Step("Evaluate audio control actions", _python_cmd("tools/eval_audio_control_actions.py")),
        ],
        "audio_control_health": [
            Step("Evaluate audio control health integration", _python_cmd("tools/eval_audio_control_health_runtime.py")),
        ],
        "audio_output": [
            Step("Evaluate audio output", _python_cmd("tools/eval_audio_output.py")),
        ],
        "audio_output_actions": [
            Step("Evaluate audio output actions", _python_cmd("tools/eval_audio_output_actions.py")),
        ],
        "weather_telemetry": [
            Step("Evaluate operation telemetry", _python_cmd("tools/eval_operation_telemetry.py")),
            Step("Evaluate weather service", _python_cmd("tools/eval_weather_service.py")),
            Step("Evaluate weather health integration", _python_cmd("tools/eval_weather_health_runtime.py")),
        ],
        "runtime_health_monitor": [
            Step("Evaluate runtime health monitor", _python_cmd("tools/eval_runtime_service_health_monitor.py")),
        ],
        "runtime_service_health": [
            Step("Evaluate runtime service health", _python_cmd("tools/eval_runtime_service_health.py")),
            Step("Evaluate runtime service health runtime", _python_cmd("tools/eval_runtime_service_health_runtime.py")),
            Step("Evaluate runtime health monitor", _python_cmd("tools/eval_runtime_service_health_monitor.py")),
            Step("Evaluate STT health integration", _python_cmd("tools/eval_stt_health_runtime.py")),
            Step("Evaluate TTS health integration", _python_cmd("tools/eval_tts_health_runtime.py")),
            Step("Evaluate audio control health integration", _python_cmd("tools/eval_audio_control_health_runtime.py")),
            Step("Evaluate weather health integration", _python_cmd("tools/eval_weather_health_runtime.py")),
            Step("Evaluate runtime service health command", _python_cmd("tools/eval_runtime_service_health_command.py")),
        ],
        "runtime_architecture_audit": [
            Step("Evaluate runtime architecture audit", _python_cmd("tools/eval_runtime_architecture_audit.py")),
        ],
        "action_execution_boundary": [
            Step("Evaluate action execution boundary", _python_cmd("-I", "-S", "-B", "tools/eval_action_execution_boundary.py")),
        ],
        "timer_action_runtime": [
            Step("Evaluate HWA02-B1 timer action runtime", _python_cmd("tools/eval_timer_action_runtime.py")),
        ],
        "volume_action_runtime": [
            Step("Evaluate HWA02-B2 volume action runtime", _python_cmd("tools/eval_volume_action_runtime.py")),
        ],
        "scm01_host_worker": [
            Step("Evaluate SCM01 host worker source contract", _python_cmd("tools/eval_scm01_host_worker.py")),
        ],
        "developer_task_contract": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task contract", _python_cmd("tools/eval_developer_task_contract.py")),
        ],
        "developer_task_proposal_intake": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task contract", _python_cmd("tools/eval_developer_task_contract.py")),
            Step("Evaluate developer task proposal intake", _python_cmd("tools/eval_developer_task_proposal_intake.py")),
        ],
        "developer_task_rehearsal": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task contract", _python_cmd("tools/eval_developer_task_contract.py")),
            Step("Evaluate developer task proposal intake", _python_cmd("tools/eval_developer_task_proposal_intake.py")),
            Step("Evaluate developer task complete preflight composition", _python_cmd("tools/eval_developer_task_preflight_composition.py")),
            Step("Evaluate developer task independent repository workspace", _python_cmd("tools/eval_developer_task_workspace.py")),
            Step("Evaluate developer task workspace cleanup lifecycle", _python_cmd("tools/eval_developer_task_workspace_cleanup.py")),
            Step("Evaluate developer task patch apply", _python_cmd("tools/eval_developer_task_patch_apply.py")),
            Step("Evaluate developer task static check evidence", _python_cmd("tools/eval_developer_task_check_static.py")),
            Step("Evaluate DTR-B static rehearsal orchestrator", _python_cmd("tools/eval_developer_task_rehearsal.py")),
        ],
        "developer_task_preflight": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task contract", _python_cmd("tools/eval_developer_task_contract.py")),
            Step("Evaluate developer task repository preflight", _python_cmd("tools/eval_developer_task_preflight.py")),
            Step("Evaluate developer task patch integrity preflight", _python_cmd("tools/eval_developer_task_patch_integrity.py")),
            Step("Evaluate developer task isolated patch index preflight", _python_cmd("tools/eval_developer_task_patch_index.py")),
            Step("Evaluate developer task patch scope policy preflight", _python_cmd("tools/eval_developer_task_patch_scope.py")),
            Step("Evaluate developer task complete preflight composition", _python_cmd("tools/eval_developer_task_preflight_composition.py")),
        ],
        "developer_task_workspace": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task contract", _python_cmd("tools/eval_developer_task_contract.py")),
            Step("Evaluate developer task repository preflight", _python_cmd("tools/eval_developer_task_preflight.py")),
            Step("Evaluate developer task patch integrity preflight", _python_cmd("tools/eval_developer_task_patch_integrity.py")),
            Step("Evaluate developer task isolated patch index preflight", _python_cmd("tools/eval_developer_task_patch_index.py")),
            Step("Evaluate developer task patch scope policy preflight", _python_cmd("tools/eval_developer_task_patch_scope.py")),
            Step("Evaluate developer task complete preflight composition", _python_cmd("tools/eval_developer_task_preflight_composition.py")),
            Step("Evaluate developer task independent repository workspace", _python_cmd("tools/eval_developer_task_workspace.py")),
        ],
        "developer_task_workspace_cleanup": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task contract", _python_cmd("tools/eval_developer_task_contract.py")),
            Step("Evaluate developer task repository preflight", _python_cmd("tools/eval_developer_task_preflight.py")),
            Step("Evaluate developer task patch integrity preflight", _python_cmd("tools/eval_developer_task_patch_integrity.py")),
            Step("Evaluate developer task isolated patch index preflight", _python_cmd("tools/eval_developer_task_patch_index.py")),
            Step("Evaluate developer task patch scope policy preflight", _python_cmd("tools/eval_developer_task_patch_scope.py")),
            Step("Evaluate developer task complete preflight composition", _python_cmd("tools/eval_developer_task_preflight_composition.py")),
            Step("Evaluate developer task independent repository workspace", _python_cmd("tools/eval_developer_task_workspace.py")),
            Step("Evaluate developer task workspace cleanup lifecycle", _python_cmd("tools/eval_developer_task_workspace_cleanup.py")),
        ],
        "developer_task_patch_apply": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task contract", _python_cmd("tools/eval_developer_task_contract.py")),
            Step("Evaluate developer task repository preflight", _python_cmd("tools/eval_developer_task_preflight.py")),
            Step("Evaluate developer task patch integrity preflight", _python_cmd("tools/eval_developer_task_patch_integrity.py")),
            Step("Evaluate developer task isolated patch index preflight", _python_cmd("tools/eval_developer_task_patch_index.py")),
            Step("Evaluate developer task patch scope policy preflight", _python_cmd("tools/eval_developer_task_patch_scope.py")),
            Step("Evaluate developer task complete preflight composition", _python_cmd("tools/eval_developer_task_preflight_composition.py")),
            Step("Evaluate developer task independent repository workspace", _python_cmd("tools/eval_developer_task_workspace.py")),
            Step("Evaluate developer task workspace cleanup lifecycle", _python_cmd("tools/eval_developer_task_workspace_cleanup.py")),
            Step("Evaluate developer task patch apply", _python_cmd("tools/eval_developer_task_patch_apply.py")),
        ],
        "developer_task_check_static": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task contract", _python_cmd("tools/eval_developer_task_contract.py")),
            Step("Evaluate developer task repository preflight", _python_cmd("tools/eval_developer_task_preflight.py")),
            Step("Evaluate developer task patch integrity preflight", _python_cmd("tools/eval_developer_task_patch_integrity.py")),
            Step("Evaluate developer task isolated patch index preflight", _python_cmd("tools/eval_developer_task_patch_index.py")),
            Step("Evaluate developer task patch scope policy preflight", _python_cmd("tools/eval_developer_task_patch_scope.py")),
            Step("Evaluate developer task complete preflight composition", _python_cmd("tools/eval_developer_task_preflight_composition.py")),
            Step("Evaluate developer task independent repository workspace", _python_cmd("tools/eval_developer_task_workspace.py")),
            Step("Evaluate developer task workspace cleanup lifecycle", _python_cmd("tools/eval_developer_task_workspace_cleanup.py")),
            Step("Evaluate developer task patch apply", _python_cmd("tools/eval_developer_task_patch_apply.py")),
            Step("Evaluate developer task static check evidence", _python_cmd("tools/eval_developer_task_check_static.py")),
        ],
        "developer_task_execution_backend_host": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task contract", _python_cmd("tools/eval_developer_task_contract.py")),
            Step("Evaluate developer task repository preflight", _python_cmd("tools/eval_developer_task_preflight.py")),
            Step("Evaluate developer task patch integrity preflight", _python_cmd("tools/eval_developer_task_patch_integrity.py")),
            Step("Evaluate developer task isolated patch index preflight", _python_cmd("tools/eval_developer_task_patch_index.py")),
            Step("Evaluate developer task patch scope policy preflight", _python_cmd("tools/eval_developer_task_patch_scope.py")),
            Step("Evaluate developer task complete preflight composition", _python_cmd("tools/eval_developer_task_preflight_composition.py")),
            Step("Evaluate developer task independent repository workspace", _python_cmd("tools/eval_developer_task_workspace.py")),
            Step("Evaluate developer task workspace cleanup lifecycle", _python_cmd("tools/eval_developer_task_workspace_cleanup.py")),
            Step("Evaluate developer task patch apply", _python_cmd("tools/eval_developer_task_patch_apply.py")),
            Step("Evaluate developer task static check evidence", _python_cmd("tools/eval_developer_task_check_static.py")),
            Step("Evaluate developer task execution backend host capability", _python_cmd("tools/eval_developer_task_execution_backend_host.py")),
            Step("Evaluate developer task execution backend Windows host", _python_cmd("tools/eval_developer_task_execution_backend_host_windows.py")),
        ],
        "developer_task_execution_backend_lifecycle": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task contract", _python_cmd("tools/eval_developer_task_contract.py")),
            Step("Evaluate developer task repository preflight", _python_cmd("tools/eval_developer_task_preflight.py")),
            Step("Evaluate developer task patch integrity preflight", _python_cmd("tools/eval_developer_task_patch_integrity.py")),
            Step("Evaluate developer task isolated patch index preflight", _python_cmd("tools/eval_developer_task_patch_index.py")),
            Step("Evaluate developer task patch scope policy preflight", _python_cmd("tools/eval_developer_task_patch_scope.py")),
            Step("Evaluate developer task complete preflight composition", _python_cmd("tools/eval_developer_task_preflight_composition.py")),
            Step("Evaluate developer task independent repository workspace", _python_cmd("tools/eval_developer_task_workspace.py")),
            Step("Evaluate developer task workspace cleanup lifecycle", _python_cmd("tools/eval_developer_task_workspace_cleanup.py")),
            Step("Evaluate developer task patch apply", _python_cmd("tools/eval_developer_task_patch_apply.py")),
            Step("Evaluate developer task static check evidence", _python_cmd("tools/eval_developer_task_check_static.py")),
            Step("Evaluate developer task execution backend host capability", _python_cmd("tools/eval_developer_task_execution_backend_host.py")),
            Step("Evaluate developer task execution backend Windows host", _python_cmd("tools/eval_developer_task_execution_backend_host_windows.py")),
            Step("Evaluate developer task execution backend lifecycle", _python_cmd("tools/eval_developer_task_execution_backend_lifecycle.py")),
            Step("Evaluate developer task execution backend Windows lifecycle", _python_cmd("tools/eval_developer_task_execution_backend_lifecycle_windows.py")),
        ],
        "developer_task_execution_boundary_verifier": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task contract", _python_cmd("tools/eval_developer_task_contract.py")),
            Step("Evaluate developer task repository preflight", _python_cmd("tools/eval_developer_task_preflight.py")),
            Step("Evaluate developer task patch integrity preflight", _python_cmd("tools/eval_developer_task_patch_integrity.py")),
            Step("Evaluate developer task isolated patch index preflight", _python_cmd("tools/eval_developer_task_patch_index.py")),
            Step("Evaluate developer task patch scope policy preflight", _python_cmd("tools/eval_developer_task_patch_scope.py")),
            Step("Evaluate developer task complete preflight composition", _python_cmd("tools/eval_developer_task_preflight_composition.py")),
            Step("Evaluate developer task independent repository workspace", _python_cmd("tools/eval_developer_task_workspace.py")),
            Step("Evaluate developer task workspace cleanup lifecycle", _python_cmd("tools/eval_developer_task_workspace_cleanup.py")),
            Step("Evaluate developer task patch apply", _python_cmd("tools/eval_developer_task_patch_apply.py")),
            Step("Evaluate developer task static check evidence", _python_cmd("tools/eval_developer_task_check_static.py")),
            Step("Evaluate developer task execution backend host capability", _python_cmd("tools/eval_developer_task_execution_backend_host.py")),
            Step("Evaluate developer task execution backend lifecycle", _python_cmd("tools/eval_developer_task_execution_backend_lifecycle.py")),
            Step("Evaluate developer task signed transcript verifier", _python_cmd("tools/eval_developer_task_execution_boundary_verifier.py")),
            Step("Evaluate developer task signed transcript Windows CNG", _python_cmd("tools/eval_developer_task_execution_boundary_crypto_windows.py")),
        ],
        "developer_task_execution_boundary_worker": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task contract", _python_cmd("tools/eval_developer_task_contract.py")),
            Step("Evaluate developer task repository preflight", _python_cmd("tools/eval_developer_task_preflight.py")),
            Step("Evaluate developer task patch integrity preflight", _python_cmd("tools/eval_developer_task_patch_integrity.py")),
            Step("Evaluate developer task isolated patch index preflight", _python_cmd("tools/eval_developer_task_patch_index.py")),
            Step("Evaluate developer task patch scope policy preflight", _python_cmd("tools/eval_developer_task_patch_scope.py")),
            Step("Evaluate developer task complete preflight composition", _python_cmd("tools/eval_developer_task_preflight_composition.py")),
            Step("Evaluate developer task independent repository workspace", _python_cmd("tools/eval_developer_task_workspace.py")),
            Step("Evaluate developer task workspace cleanup lifecycle", _python_cmd("tools/eval_developer_task_workspace_cleanup.py")),
            Step("Evaluate developer task patch apply", _python_cmd("tools/eval_developer_task_patch_apply.py")),
            Step("Evaluate developer task static check evidence", _python_cmd("tools/eval_developer_task_check_static.py")),
            Step("Evaluate developer task execution backend host capability", _python_cmd("tools/eval_developer_task_execution_backend_host.py")),
            Step("Evaluate developer task execution backend lifecycle", _python_cmd("tools/eval_developer_task_execution_backend_lifecycle.py")),
            Step("Evaluate developer task signed transcript verifier", _python_cmd("tools/eval_developer_task_execution_boundary_verifier.py")),
            Step("Evaluate developer task signed transcript Windows CNG", _python_cmd("tools/eval_developer_task_execution_boundary_crypto_windows.py")),
            Step("Evaluate developer task standard-user worker isolation bundle", _python_cmd("tools/eval_developer_task_execution_boundary_worker.py")),
            Step("Evaluate developer task standard-user worker Windows compile", _python_cmd("tools/eval_developer_task_execution_boundary_worker_windows.py")),
        ],
        "developer_task_execution_boundary_composition": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task contract", _python_cmd("tools/eval_developer_task_contract.py")),
            Step("Evaluate developer task repository preflight", _python_cmd("tools/eval_developer_task_preflight.py")),
            Step("Evaluate developer task patch integrity preflight", _python_cmd("tools/eval_developer_task_patch_integrity.py")),
            Step("Evaluate developer task isolated patch index preflight", _python_cmd("tools/eval_developer_task_patch_index.py")),
            Step("Evaluate developer task patch scope policy preflight", _python_cmd("tools/eval_developer_task_patch_scope.py")),
            Step("Evaluate developer task complete preflight composition", _python_cmd("tools/eval_developer_task_preflight_composition.py")),
            Step("Evaluate developer task independent repository workspace", _python_cmd("tools/eval_developer_task_workspace.py")),
            Step("Evaluate developer task workspace cleanup lifecycle", _python_cmd("tools/eval_developer_task_workspace_cleanup.py")),
            Step("Evaluate developer task patch apply", _python_cmd("tools/eval_developer_task_patch_apply.py")),
            Step("Evaluate developer task static check evidence", _python_cmd("tools/eval_developer_task_check_static.py")),
            Step("Evaluate developer task execution backend host capability", _python_cmd("tools/eval_developer_task_execution_backend_host.py")),
            Step("Evaluate developer task execution backend Windows host", _python_cmd("tools/eval_developer_task_execution_backend_host_windows.py")),
            Step("Evaluate developer task execution backend lifecycle", _python_cmd("tools/eval_developer_task_execution_backend_lifecycle.py")),
            Step("Evaluate developer task signed transcript verifier", _python_cmd("tools/eval_developer_task_execution_boundary_verifier.py")),
            Step("Evaluate developer task signed transcript Windows CNG", _python_cmd("tools/eval_developer_task_execution_boundary_crypto_windows.py")),
            Step("Evaluate developer task standard-user worker isolation bundle", _python_cmd("tools/eval_developer_task_execution_boundary_worker.py")),
            Step("Evaluate developer task standard-user worker Windows compile", _python_cmd("tools/eval_developer_task_execution_boundary_worker_windows.py")),
            Step("Evaluate developer task active signed boundary composition", _python_cmd("tools/eval_developer_task_execution_boundary_composition.py")),
            Step("Evaluate developer task active signed boundary Windows composition", _python_cmd("tools/eval_developer_task_execution_boundary_composition_windows.py")),
        ],
        "developer_task_execution_runtime_bundle": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task contract", _python_cmd("tools/eval_developer_task_contract.py")),
            Step("Evaluate developer task repository preflight", _python_cmd("tools/eval_developer_task_preflight.py")),
            Step("Evaluate developer task patch integrity preflight", _python_cmd("tools/eval_developer_task_patch_integrity.py")),
            Step("Evaluate developer task isolated patch index preflight", _python_cmd("tools/eval_developer_task_patch_index.py")),
            Step("Evaluate developer task patch scope policy preflight", _python_cmd("tools/eval_developer_task_patch_scope.py")),
            Step("Evaluate developer task complete preflight composition", _python_cmd("tools/eval_developer_task_preflight_composition.py")),
            Step("Evaluate developer task independent repository workspace", _python_cmd("tools/eval_developer_task_workspace.py")),
            Step("Evaluate developer task workspace cleanup lifecycle", _python_cmd("tools/eval_developer_task_workspace_cleanup.py")),
            Step("Evaluate developer task patch apply", _python_cmd("tools/eval_developer_task_patch_apply.py")),
            Step("Evaluate developer task static check evidence", _python_cmd("tools/eval_developer_task_check_static.py")),
            Step("Evaluate developer task execution backend host capability", _python_cmd("tools/eval_developer_task_execution_backend_host.py")),
            Step("Evaluate developer task execution backend lifecycle", _python_cmd("tools/eval_developer_task_execution_backend_lifecycle.py")),
            Step("Evaluate developer task signed transcript verifier", _python_cmd("tools/eval_developer_task_execution_boundary_verifier.py")),
            Step("Evaluate developer task standard-user worker isolation bundle", _python_cmd("tools/eval_developer_task_execution_boundary_worker.py")),
            Step("Evaluate developer task active signed boundary composition", _python_cmd("tools/eval_developer_task_execution_boundary_composition.py")),
            Step("Evaluate developer task deterministic trusted runtime bundle", _python_cmd("tools/eval_developer_task_execution_runtime_bundle.py")),
            Step("Evaluate developer task deterministic trusted runtime Windows bundle", _python_cmd("tools/eval_developer_task_execution_runtime_bundle_windows.py")),
        ],
        "developer_task_execution_runtime_attestation": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task contract", _python_cmd("tools/eval_developer_task_contract.py")),
            Step("Evaluate developer task repository preflight", _python_cmd("tools/eval_developer_task_preflight.py")),
            Step("Evaluate developer task patch integrity preflight", _python_cmd("tools/eval_developer_task_patch_integrity.py")),
            Step("Evaluate developer task isolated patch index preflight", _python_cmd("tools/eval_developer_task_patch_index.py")),
            Step("Evaluate developer task patch scope policy preflight", _python_cmd("tools/eval_developer_task_patch_scope.py")),
            Step("Evaluate developer task complete preflight composition", _python_cmd("tools/eval_developer_task_preflight_composition.py")),
            Step("Evaluate developer task independent repository workspace", _python_cmd("tools/eval_developer_task_workspace.py")),
            Step("Evaluate developer task workspace cleanup lifecycle", _python_cmd("tools/eval_developer_task_workspace_cleanup.py")),
            Step("Evaluate developer task patch apply", _python_cmd("tools/eval_developer_task_patch_apply.py")),
            Step("Evaluate developer task static check evidence", _python_cmd("tools/eval_developer_task_check_static.py")),
            Step("Evaluate developer task execution backend host capability", _python_cmd("tools/eval_developer_task_execution_backend_host.py")),
            Step("Evaluate developer task execution backend lifecycle", _python_cmd("tools/eval_developer_task_execution_backend_lifecycle.py")),
            Step("Evaluate developer task signed transcript verifier", _python_cmd("tools/eval_developer_task_execution_boundary_verifier.py")),
            Step("Evaluate developer task standard-user worker isolation bundle", _python_cmd("tools/eval_developer_task_execution_boundary_worker.py")),
            Step("Evaluate developer task active signed boundary composition", _python_cmd("tools/eval_developer_task_execution_boundary_composition.py")),
            Step("Evaluate developer task deterministic trusted runtime bundle", _python_cmd("tools/eval_developer_task_execution_runtime_bundle.py")),
            Step("Evaluate developer task trusted runtime attestation contract and payload", _python_cmd("tools/eval_developer_task_execution_runtime_attestation.py")),
            Step("Evaluate developer task trusted runtime attestation Windows compile-only payload", _python_cmd("tools/eval_developer_task_execution_runtime_attestation_windows.py")),
        ],
        "developer_task_execution_runtime_attestation_verifier": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task contract", _python_cmd("tools/eval_developer_task_contract.py")),
            Step("Evaluate developer task repository preflight", _python_cmd("tools/eval_developer_task_preflight.py")),
            Step("Evaluate developer task patch integrity preflight", _python_cmd("tools/eval_developer_task_patch_integrity.py")),
            Step("Evaluate developer task isolated patch index preflight", _python_cmd("tools/eval_developer_task_patch_index.py")),
            Step("Evaluate developer task patch scope policy preflight", _python_cmd("tools/eval_developer_task_patch_scope.py")),
            Step("Evaluate developer task complete preflight composition", _python_cmd("tools/eval_developer_task_preflight_composition.py")),
            Step("Evaluate developer task independent repository workspace", _python_cmd("tools/eval_developer_task_workspace.py")),
            Step("Evaluate developer task workspace cleanup lifecycle", _python_cmd("tools/eval_developer_task_workspace_cleanup.py")),
            Step("Evaluate developer task patch apply", _python_cmd("tools/eval_developer_task_patch_apply.py")),
            Step("Evaluate developer task static check evidence", _python_cmd("tools/eval_developer_task_check_static.py")),
            Step("Evaluate developer task execution backend host capability", _python_cmd("tools/eval_developer_task_execution_backend_host.py")),
            Step("Evaluate developer task execution backend lifecycle", _python_cmd("tools/eval_developer_task_execution_backend_lifecycle.py")),
            Step("Evaluate developer task signed transcript verifier", _python_cmd("tools/eval_developer_task_execution_boundary_verifier.py")),
            Step("Evaluate developer task standard-user worker isolation bundle", _python_cmd("tools/eval_developer_task_execution_boundary_worker.py")),
            Step("Evaluate developer task active signed boundary composition", _python_cmd("tools/eval_developer_task_execution_boundary_composition.py")),
            Step("Evaluate developer task deterministic trusted runtime bundle", _python_cmd("tools/eval_developer_task_execution_runtime_bundle.py")),
            Step("Evaluate developer task trusted runtime attestation contract and payload", _python_cmd("tools/eval_developer_task_execution_runtime_attestation.py")),
            Step("Evaluate developer task signed runtime transcript verifier", _python_cmd("tools/eval_developer_task_execution_runtime_attestation_verifier.py")),
            Step("Evaluate developer task trusted runtime attestation Windows compile-only payload", _python_cmd("tools/eval_developer_task_execution_runtime_attestation_windows.py")),
            Step("Evaluate developer task signed runtime transcript Windows CNG", _python_cmd("tools/eval_developer_task_execution_runtime_attestation_crypto_windows.py")),
        ],
        "developer_task_execution_runtime_composition": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task contract", _python_cmd("tools/eval_developer_task_contract.py")),
            Step("Evaluate developer task repository preflight", _python_cmd("tools/eval_developer_task_preflight.py")),
            Step("Evaluate developer task patch integrity preflight", _python_cmd("tools/eval_developer_task_patch_integrity.py")),
            Step("Evaluate developer task isolated patch index preflight", _python_cmd("tools/eval_developer_task_patch_index.py")),
            Step("Evaluate developer task patch scope policy preflight", _python_cmd("tools/eval_developer_task_patch_scope.py")),
            Step("Evaluate developer task complete preflight composition", _python_cmd("tools/eval_developer_task_preflight_composition.py")),
            Step("Evaluate developer task independent repository workspace", _python_cmd("tools/eval_developer_task_workspace.py")),
            Step("Evaluate developer task workspace cleanup lifecycle", _python_cmd("tools/eval_developer_task_workspace_cleanup.py")),
            Step("Evaluate developer task patch apply", _python_cmd("tools/eval_developer_task_patch_apply.py")),
            Step("Evaluate developer task static check evidence", _python_cmd("tools/eval_developer_task_check_static.py")),
            Step("Evaluate developer task execution backend host capability", _python_cmd("tools/eval_developer_task_execution_backend_host.py")),
            Step("Evaluate developer task execution backend Windows host", _python_cmd("tools/eval_developer_task_execution_backend_host_windows.py")),
            Step("Evaluate developer task execution backend lifecycle", _python_cmd("tools/eval_developer_task_execution_backend_lifecycle.py")),
            Step("Evaluate developer task signed transcript verifier", _python_cmd("tools/eval_developer_task_execution_boundary_verifier.py")),
            Step("Evaluate developer task standard-user worker isolation bundle", _python_cmd("tools/eval_developer_task_execution_boundary_worker.py")),
            Step("Evaluate developer task active signed boundary composition", _python_cmd("tools/eval_developer_task_execution_boundary_composition.py")),
            Step("Evaluate developer task deterministic trusted runtime bundle", _python_cmd("tools/eval_developer_task_execution_runtime_bundle.py")),
            Step("Evaluate developer task trusted runtime attestation contract and payload", _python_cmd("tools/eval_developer_task_execution_runtime_attestation.py")),
            Step("Evaluate developer task signed runtime transcript verifier", _python_cmd("tools/eval_developer_task_execution_runtime_attestation_verifier.py")),
            Step("Evaluate developer task trusted runtime attestation Windows compile-only payload", _python_cmd("tools/eval_developer_task_execution_runtime_attestation_windows.py")),
            Step("Evaluate developer task signed runtime transcript Windows CNG", _python_cmd("tools/eval_developer_task_execution_runtime_attestation_crypto_windows.py")),
            Step("Evaluate developer task active trusted runtime composition", _python_cmd("tools/eval_developer_task_execution_runtime_composition.py")),
            Step("Evaluate developer task active trusted runtime Windows composition", _python_cmd("tools/eval_developer_task_execution_runtime_composition_windows.py")),
        ],
        "developer_task_execution_runtime_lease": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task contract", _python_cmd("tools/eval_developer_task_contract.py")),
            Step("Evaluate developer task repository preflight", _python_cmd("tools/eval_developer_task_preflight.py")),
            Step("Evaluate developer task patch integrity preflight", _python_cmd("tools/eval_developer_task_patch_integrity.py")),
            Step("Evaluate developer task isolated patch index preflight", _python_cmd("tools/eval_developer_task_patch_index.py")),
            Step("Evaluate developer task patch scope policy preflight", _python_cmd("tools/eval_developer_task_patch_scope.py")),
            Step("Evaluate developer task complete preflight composition", _python_cmd("tools/eval_developer_task_preflight_composition.py")),
            Step("Evaluate developer task independent repository workspace", _python_cmd("tools/eval_developer_task_workspace.py")),
            Step("Evaluate developer task workspace cleanup lifecycle", _python_cmd("tools/eval_developer_task_workspace_cleanup.py")),
            Step("Evaluate developer task patch apply", _python_cmd("tools/eval_developer_task_patch_apply.py")),
            Step("Evaluate developer task static check evidence", _python_cmd("tools/eval_developer_task_check_static.py")),
            Step("Evaluate developer task execution backend host capability", _python_cmd("tools/eval_developer_task_execution_backend_host.py")),
            Step("Evaluate developer task execution backend Windows host", _python_cmd("tools/eval_developer_task_execution_backend_host_windows.py")),
            Step("Evaluate developer task execution backend lifecycle", _python_cmd("tools/eval_developer_task_execution_backend_lifecycle.py")),
            Step("Evaluate developer task signed transcript verifier", _python_cmd("tools/eval_developer_task_execution_boundary_verifier.py")),
            Step("Evaluate developer task standard-user worker isolation bundle", _python_cmd("tools/eval_developer_task_execution_boundary_worker.py")),
            Step("Evaluate developer task active signed boundary composition", _python_cmd("tools/eval_developer_task_execution_boundary_composition.py")),
            Step("Evaluate developer task deterministic trusted runtime bundle", _python_cmd("tools/eval_developer_task_execution_runtime_bundle.py")),
            Step("Evaluate developer task deterministic trusted runtime Windows bundle", _python_cmd("tools/eval_developer_task_execution_runtime_bundle_windows.py")),
            Step("Evaluate developer task trusted runtime attestation contract and payload", _python_cmd("tools/eval_developer_task_execution_runtime_attestation.py")),
            Step("Evaluate developer task signed runtime transcript verifier", _python_cmd("tools/eval_developer_task_execution_runtime_attestation_verifier.py")),
            Step("Evaluate developer task active trusted runtime composition", _python_cmd("tools/eval_developer_task_execution_runtime_composition.py")),
            Step("Evaluate developer task trusted runtime attestation Windows compile-only payload", _python_cmd("tools/eval_developer_task_execution_runtime_attestation_windows.py")),
            Step("Evaluate developer task signed runtime transcript Windows CNG", _python_cmd("tools/eval_developer_task_execution_runtime_attestation_crypto_windows.py")),
            Step("Evaluate developer task same-run runtime capability lease", _python_cmd("tools/eval_developer_task_execution_runtime_lease.py")),
            Step("Evaluate developer task same-run runtime capability lease Windows host-only smoke", _python_cmd("tools/eval_developer_task_execution_runtime_lease_windows.py")),
        ],
        "developer_task_execution_environment_inventory": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task contract", _python_cmd("tools/eval_developer_task_contract.py")),
            Step("Evaluate developer task repository preflight", _python_cmd("tools/eval_developer_task_preflight.py")),
            Step("Evaluate developer task executable environment inventory", _python_cmd("tools/eval_developer_task_execution_environment_inventory.py")),
            Step("Evaluate developer task executable environment inventory Windows host-only smoke", _python_cmd("tools/eval_developer_task_execution_environment_inventory_windows.py")),
        ],
        "developer_task_execution_toolchain_observation": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task contract", _python_cmd("tools/eval_developer_task_contract.py")),
            Step("Evaluate developer task repository preflight", _python_cmd("tools/eval_developer_task_preflight.py")),
            Step("Evaluate developer task executable environment inventory", _python_cmd("tools/eval_developer_task_execution_environment_inventory.py")),
            Step("Evaluate developer task canonical host toolchain observation", _python_cmd("tools/eval_developer_task_execution_toolchain_observation.py")),
            Step("Evaluate developer task canonical host toolchain observation Windows smoke", _python_cmd("tools/eval_developer_task_execution_toolchain_observation_windows.py")),
        ],
        "developer_task_execution_dependency_profile": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task contract", _python_cmd("tools/eval_developer_task_contract.py")),
            Step("Evaluate developer task repository preflight", _python_cmd("tools/eval_developer_task_preflight.py")),
            Step("Evaluate developer task executable environment inventory", _python_cmd("tools/eval_developer_task_execution_environment_inventory.py")),
            Step("Evaluate developer task canonical host toolchain observation", _python_cmd("tools/eval_developer_task_execution_toolchain_observation.py")),
            Step("Evaluate developer task canonical dependency profile target contract", _python_cmd("tools/eval_developer_task_execution_dependency_profile.py")),
            Step("Evaluate developer task canonical dependency profile Windows host-only smoke", _python_cmd("tools/eval_developer_task_execution_dependency_profile_windows.py")),
        ],
        "developer_task_execution_dependency_acquisition": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task contract", _python_cmd("tools/eval_developer_task_contract.py")),
            Step("Evaluate developer task repository preflight", _python_cmd("tools/eval_developer_task_preflight.py")),
            Step("Evaluate developer task executable environment inventory", _python_cmd("tools/eval_developer_task_execution_environment_inventory.py")),
            Step("Evaluate developer task canonical host toolchain observation", _python_cmd("tools/eval_developer_task_execution_toolchain_observation.py")),
            Step("Evaluate developer task canonical dependency profile target contract", _python_cmd("tools/eval_developer_task_execution_dependency_profile.py")),
            Step("Evaluate developer task canonical dependency profile Windows host-only smoke", _python_cmd("tools/eval_developer_task_execution_dependency_profile_windows.py")),
            Step("Evaluate developer task non-network dependency acquisition contract", _python_cmd("tools/eval_developer_task_execution_dependency_acquisition.py")),
            Step("Evaluate developer task non-network dependency acquisition Windows host-only smoke", _python_cmd("tools/eval_developer_task_execution_dependency_acquisition_windows.py")),
        ],
        "developer_task_execution_workspace_snapshot": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task contract", _python_cmd("tools/eval_developer_task_contract.py")),
            Step("Evaluate developer task repository preflight", _python_cmd("tools/eval_developer_task_preflight.py")),
            Step("Evaluate developer task patch integrity preflight", _python_cmd("tools/eval_developer_task_patch_integrity.py")),
            Step("Evaluate developer task isolated patch index preflight", _python_cmd("tools/eval_developer_task_patch_index.py")),
            Step("Evaluate developer task patch scope policy preflight", _python_cmd("tools/eval_developer_task_patch_scope.py")),
            Step("Evaluate developer task complete preflight composition", _python_cmd("tools/eval_developer_task_preflight_composition.py")),
            Step("Evaluate developer task independent repository workspace", _python_cmd("tools/eval_developer_task_workspace.py")),
            Step("Evaluate developer task workspace cleanup lifecycle", _python_cmd("tools/eval_developer_task_workspace_cleanup.py")),
            Step("Evaluate developer task patch apply", _python_cmd("tools/eval_developer_task_patch_apply.py")),
            Step("Evaluate developer task static check evidence", _python_cmd("tools/eval_developer_task_check_static.py")),
            Step("Evaluate developer task canonical patched workspace snapshot", _python_cmd("tools/eval_developer_task_execution_workspace_snapshot.py")),
            Step("Evaluate developer task canonical patched workspace snapshot Windows smoke", _python_cmd("tools/eval_developer_task_execution_workspace_snapshot_windows.py")),
        ],
        "developer_task_execution_compile_ast_plan": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task contract", _python_cmd("tools/eval_developer_task_contract.py")),
            Step("Evaluate developer task repository preflight", _python_cmd("tools/eval_developer_task_preflight.py")),
            Step("Evaluate developer task patch integrity preflight", _python_cmd("tools/eval_developer_task_patch_integrity.py")),
            Step("Evaluate developer task isolated patch index preflight", _python_cmd("tools/eval_developer_task_patch_index.py")),
            Step("Evaluate developer task patch scope policy preflight", _python_cmd("tools/eval_developer_task_patch_scope.py")),
            Step("Evaluate developer task complete preflight composition", _python_cmd("tools/eval_developer_task_preflight_composition.py")),
            Step("Evaluate developer task independent repository workspace", _python_cmd("tools/eval_developer_task_workspace.py")),
            Step("Evaluate developer task workspace cleanup lifecycle", _python_cmd("tools/eval_developer_task_workspace_cleanup.py")),
            Step("Evaluate developer task patch apply", _python_cmd("tools/eval_developer_task_patch_apply.py")),
            Step("Evaluate developer task static check evidence", _python_cmd("tools/eval_developer_task_check_static.py")),
            Step("Evaluate developer task canonical patched workspace snapshot", _python_cmd("tools/eval_developer_task_execution_workspace_snapshot.py")),
            Step("Evaluate developer task typed compile AST plan capability", _python_cmd("tools/eval_developer_task_execution_compile_ast_plan.py")),
            Step("Evaluate developer task typed compile AST plan Windows smoke", _python_cmd("tools/eval_developer_task_execution_compile_ast_plan_windows.py")),
        ],
        "developer_task_execution_compile_ast_contract": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task typed compile AST plan capability", _python_cmd("tools/eval_developer_task_execution_compile_ast_plan.py")),
            Step("Evaluate developer task canonical compile AST contract", _python_cmd("tools/eval_developer_task_execution_compile_ast_contract.py")),
            Step("Evaluate developer task canonical compile AST contract Windows smoke", _python_cmd("tools/eval_developer_task_execution_compile_ast_contract_windows.py")),
        ],
        "developer_task_execution_compile_ast_runner": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task canonical compile AST contract", _python_cmd("tools/eval_developer_task_execution_compile_ast_contract.py")),
            Step("Evaluate developer task fixed compile AST guest runner bundle", _python_cmd("tools/eval_developer_task_execution_compile_ast_runner.py")),
            Step("Evaluate developer task fixed compile AST guest runner bundle Windows smoke", _python_cmd("tools/eval_developer_task_execution_compile_ast_runner_windows.py")),
        ],
        "developer_task_execution_compile_ast_verifier": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task canonical compile AST contract", _python_cmd("tools/eval_developer_task_execution_compile_ast_contract.py")),
            Step("Evaluate developer task fixed compile AST guest runner bundle", _python_cmd("tools/eval_developer_task_execution_compile_ast_runner.py")),
            Step("Evaluate developer task signed compile AST transcript verifier", _python_cmd("tools/eval_developer_task_execution_compile_ast_verifier.py")),
            Step("Evaluate developer task signed compile AST transcript Windows CNG", _python_cmd("tools/eval_developer_task_execution_compile_ast_verifier_windows.py")),
        ],
        "developer_task_execution_compile_ast_claim_transaction": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task typed compile AST plan capability", _python_cmd("tools/eval_developer_task_execution_compile_ast_plan.py")),
            Step("Evaluate developer task same-run runtime capability lease", _python_cmd("tools/eval_developer_task_execution_runtime_lease.py")),
            Step("Evaluate developer task process-local compile AST claim transaction", _python_cmd("tools/eval_developer_task_execution_compile_ast_claim_transaction.py")),
            Step("Evaluate developer task process-local compile AST claim transaction Windows smoke", _python_cmd("tools/eval_developer_task_execution_compile_ast_claim_transaction_windows.py")),
        ],
        "developer_task_execution_compile_ast_controller_worker": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task canonical compile AST contract", _python_cmd("tools/eval_developer_task_execution_compile_ast_contract.py")),
            Step("Evaluate developer task fixed compile AST guest runner bundle", _python_cmd("tools/eval_developer_task_execution_compile_ast_runner.py")),
            Step("Evaluate developer task signed compile AST transcript verifier", _python_cmd("tools/eval_developer_task_execution_compile_ast_verifier.py")),
            Step("Evaluate developer task process-local compile AST claim transaction", _python_cmd("tools/eval_developer_task_execution_compile_ast_claim_transaction.py")),
            Step("Evaluate developer task fixed compile AST controller-worker bundle", _python_cmd("tools/eval_developer_task_execution_compile_ast_controller_worker.py")),
            Step("Evaluate developer task fixed compile AST controller-worker Windows compile smoke", _python_cmd("tools/eval_developer_task_execution_compile_ast_controller_worker_windows.py")),
        ],
        "developer_task_execution_compile_ast_composition": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task canonical compile AST contract", _python_cmd("tools/eval_developer_task_execution_compile_ast_contract.py")),
            Step("Evaluate developer task fixed compile AST guest runner bundle", _python_cmd("tools/eval_developer_task_execution_compile_ast_runner.py")),
            Step("Evaluate developer task signed compile AST transcript verifier", _python_cmd("tools/eval_developer_task_execution_compile_ast_verifier.py")),
            Step("Evaluate developer task process-local compile AST claim transaction", _python_cmd("tools/eval_developer_task_execution_compile_ast_claim_transaction.py")),
            Step("Evaluate developer task fixed compile AST controller-worker bundle", _python_cmd("tools/eval_developer_task_execution_compile_ast_controller_worker.py")),
            Step("Evaluate developer task fixed compile AST controller-worker Windows compile smoke", _python_cmd("tools/eval_developer_task_execution_compile_ast_controller_worker_windows.py")),
            Step("Evaluate developer task active compile AST Sandbox composition", _python_cmd("tools/eval_developer_task_execution_compile_ast_composition.py")),
            Step("Evaluate developer task active compile AST Sandbox composition Windows smoke", _python_cmd("tools/eval_developer_task_execution_compile_ast_composition_windows.py")),
        ],
        "developer_task_execution_compile_ast_live_acceptance": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate developer task canonical compile AST contract", _python_cmd("tools/eval_developer_task_execution_compile_ast_contract.py")),
            Step("Evaluate developer task fixed compile AST guest runner bundle", _python_cmd("tools/eval_developer_task_execution_compile_ast_runner.py")),
            Step("Evaluate developer task signed compile AST transcript verifier", _python_cmd("tools/eval_developer_task_execution_compile_ast_verifier.py")),
            Step("Evaluate developer task process-local compile AST claim transaction", _python_cmd("tools/eval_developer_task_execution_compile_ast_claim_transaction.py")),
            Step("Evaluate developer task fixed compile AST controller-worker bundle", _python_cmd("tools/eval_developer_task_execution_compile_ast_controller_worker.py")),
            Step("Evaluate developer task active compile AST Sandbox composition", _python_cmd("tools/eval_developer_task_execution_compile_ast_composition.py")),
            Step("Evaluate developer task V1C2C3 live acceptance contract", _python_cmd("tools/eval_developer_task_execution_compile_ast_live_acceptance.py")),
        ],
        "package_boundaries": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
        ],
        "core_package": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Evaluate NLU config contract", _python_cmd("tools/eval_nlu_config_contract.py")),
            Step("Evaluate operation telemetry", _python_cmd("tools/eval_operation_telemetry.py")),
            Step("Evaluate TTS settings", _python_cmd("tools/eval_tts_settings.py")),
            Step("Evaluate TTS lifecycle", _python_cmd("tools/eval_tts_lifecycle.py")),
            Step("Evaluate weather service", _python_cmd("tools/eval_weather_service.py")),
            Step("Evaluate runtime service health runtime", _python_cmd("tools/eval_runtime_service_health_runtime.py")),
        ],
        "runtime_package": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Import runtime package", _python_cmd("-c", "from modules.runtime.mode_manager import ModeManager; from modules.runtime.runtime_shutdown import shutdown_runtime_services; print('[OK] runtime package imports')")),
            Step("Import main composition root", _python_cmd("-c", "import main; print('[OK] main import')")),
            Step("Evaluate runtime architecture audit", _python_cmd("tools/eval_runtime_architecture_audit.py")),
        ],
        "learning_package": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Import learning package", _python_cmd("-c", "from modules.learning.correction_memory import CorrectionMemory; from modules.learning.feedback_analyzer import FeedbackAnalyzer; from modules.learning.learning_memory import LearningMemory; from modules.learning.promotion_engine import build_report, read_jsonl, norm; print('[OK] learning package imports')")),
            Step("Compile learning consumers", _python_cmd("-m", "py_compile", "tools/build_correction_memory.py", "tools/export_promotions.py", "tools/learning_report.py", "tools/promotion_report.py")),
            Step("Learning report", _python_cmd("tools/learning_report.py")),
            Step("Promotion report", _python_cmd("tools/promotion_report.py")),
            Step("Import main composition root", _python_cmd("-c", "import main; print('[OK] main import')")),
        ],
        "desktop_package": [
            Step("Evaluate package boundaries", _python_cmd("tools/eval_package_boundaries.py")),
            Step("Import desktop package", _python_cmd("-c",
                                                       "from modules.desktop.screenshot import ScreenshotService; from modules.desktop.typing_service import TypingService; from modules.desktop.window_context_service import ActiveWindowInfo, WindowContextService; print('[OK] desktop package imports')")),
            Step("Compile root desktop consumer", _python_cmd("-m", "py_compile", "test.py")),
            Step("Import main composition root", _python_cmd("-c", "import main; print('[OK] main import')")),
            Step("Evaluate runtime architecture audit", _python_cmd("tools/eval_runtime_architecture_audit.py")),
        ],
        "intent_rule_policy": [
            Step("Evaluate intent rule policy", _python_cmd("tools/eval_intent_rule_policy.py")),
        ],
        "nlu_config_contract": [
            Step("Evaluate NLU config contract", _python_cmd("tools/eval_nlu_config_contract.py")),
        ],
    }


def _emit(message: str = "", log_file: TextIO | None = None) -> None:
    print(message)
    if log_file is not None:
        log_file.write(message + "\n")
        log_file.flush()


def _emit_raw(message: str, log_file: TextIO | None = None) -> None:
    print(message, end="")
    if log_file is not None:
        log_file.write(message)
        log_file.flush()


def _safe_log_name_part(value: str) -> str:
    value = (value or "pipeline").strip().lower()
    value = re.sub(r"[^a-z0-9а-яё_-]+", "_", value, flags=re.IGNORECASE)
    value = value.strip("_")
    return value or "pipeline"


def _select_log_path(flow_name: str, explicit_path: str | None = None) -> Path:
    if explicit_path:
        path = Path(explicit_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_flow = _safe_log_name_part(flow_name)
        path = PIPELINE_LOG_DIR / f"{ts}_{safe_flow}.log"

    return path


def _make_log_path(flow_name: str, explicit_path: str | None = None) -> Path:
    path = _select_log_path(flow_name, explicit_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _build_child_env(cwd: Path) -> dict[str, str]:
    env = dict(os.environ)

    old_pythonpath = env.get("PYTHONPATH", "").strip()
    if old_pythonpath:
        env["PYTHONPATH"] = str(cwd) + os.pathsep + old_pythonpath
    else:
        env["PYTHONPATH"] = str(cwd)

    # Чтобы кириллица из дочерних Python-скриптов нормально попадала в log-файл.
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    return env


def print_help(log_file: TextIO | None = None) -> None:
    _emit("SkynetVS tools pipeline", log_file)
    _emit("", log_file)
    _emit("Usage:", log_file)
    _emit("  python tools/pipeline.py <flow> [options]", log_file)
    _emit("", log_file)
    _emit("Flows:", log_file)
    _emit("  decision   Run command decision eval only", log_file)
    _emit("  audit      Read registry data and source text; print consistency findings", log_file)
    _emit("  check      Run broad evaluations, including model and platform checks", log_file)
    _emit("  confirmation Run confirmation phrase eval only", log_file)
    _emit("  analyze    Print reports, update correction memory, evaluate reply composition", log_file)
    _emit("  promote    Rewrite inbox and promotion suggestion files", log_file)
    _emit("  raw_inbox  Rewrite inbox with raw learning cases (rescue/manual path)", log_file)
    _emit("  label      Interactively label cases; update training examples and labeled history", log_file)
    _emit("  train      Fit NLU and replace models/nlu_intent.joblib", log_file)
    _emit("  eval       Evaluate NLU predictions with the current model/configuration", log_file)
    _emit("  nlu_diag   Run NLU diagnostics with top-k candidates", log_file)
    _emit("  nlu_risk   Run NLU risk report", log_file)
    _emit("  nlu_risk_guard Run NLU risk guard", log_file)
    _emit("  full       Print reports, update correction memory, export promotions", log_file)
    _emit("  dictation   Run dictation command eval only", log_file)
    _emit("  dictation_intent Run dictation ON/OFF model separation eval only", log_file)
    _emit("  backspace_intent Run backspace model separation eval only", log_file)
    _emit("  hotword    Run hotword utility eval only", log_file)
    _emit("  fragments  Run command fragments eval only", log_file)
    _emit("  speech     Run speech IO eval only", log_file)
    _emit("  main_inventory Run main.py structure inventory", log_file)
    _emit("  stt_refinement Run STT refinement eval only", log_file)
    _emit("  stt_lifecycle Run STT lifecycle and health evals", log_file)
    _emit("  stt_diagnostics Run STT diagnostics eval only", log_file)
    _emit("  stt_missing_slots Run STT missing-slots refinement trigger eval only", log_file)
    _emit("  stt_whisper_subprocess Run STT Whisper subprocess sandbox eval only", log_file)
    _emit("  stt_runtime_report Show recent STT runtime diagnostic problems", log_file)
    _emit("  reply      Run reply builder eval only", log_file)
    _emit("  understanding Run command understanding eval only", log_file)
    _emit("  outcome    Run command outcome eval only", log_file)
    _emit("  learning   Run command learning eval only", log_file)
    _emit("  speech_interrupt Run speech interrupt eval only", log_file)
    _emit("  phrase_guards Run phrase guard eval only", log_file)
    _emit("  dictation_runtime Run dictation runtime eval only", log_file)
    _emit("  confirmation_runtime Run confirmation runtime eval only", log_file)
    _emit("  hotword_activation Run hotword activation runtime eval only", log_file)
    _emit("  command_window Run command window runtime eval only", log_file)
    _emit("  command_runtime Run command runtime eval only", log_file)
    _emit("  command_processor Run command processor eval only", log_file)
    _emit("  phrase_event Run phrase event processor eval only", log_file)
    _emit("  registry   Run entity registry eval only", log_file)
    _emit("  actions_registry Run actions registry integration eval only", log_file)
    _emit("  registry_cleanup Run registry cleanup eval only", log_file)
    _emit("  stt_quality Run interactive STT quality baseline", log_file)
    _emit("  stt_quality_report Show latest STT quality baseline", log_file)
    _emit("  duration   Run duration parser eval only", log_file)
    _emit("  timer_service Run timer service eval only", log_file)
    _emit("  timer_actions Run timer actions eval only", log_file)
    _emit("  timer_command_runtime Run timer command runtime eval only", log_file)
    _emit("  reminder_repository Run reminder repository eval only", log_file)
    _emit("  reminder_datetime Run reminder datetime parser eval only", log_file)
    _emit("  reminder_service Run reminder service eval only", log_file)
    _emit("  reminder_command_parser Run reminder command parser eval only", log_file)
    _emit("  reminder_actions Run reminder actions eval only", log_file)
    _emit("  reminder_runtime Run reminder runtime wiring eval only", log_file)
    _emit("  tts_settings Run TTS settings eval only", log_file)
    _emit("  tts_runtime  Run TTS runtime, lifecycle, and health evals", log_file)
    _emit("  audio_control  Evaluate active endpoint volume control", log_file)
    _emit("  audio_control_actions  Evaluate audio control action integration", log_file)
    _emit("  audio_control_health  Evaluate audio control health integration", log_file)
    _emit("  audio_output Evaluate audio output only", log_file)
    _emit("  audio_output_actions  Evaluate audio output actions only", log_file)
    _emit("  weather_telemetry  Evaluate operation telemetry and weather service", log_file)
    _emit("  runtime_health_monitor  Run runtime health transition monitor eval", log_file)
    _emit("  runtime_service_health  Run runtime service health integration evals", log_file)
    _emit("  runtime_architecture_audit  Run final runtime ownership and fault-injection audit", log_file)
    _emit("  developer_task_contract  Validate the safe developer task manifest contract", log_file)
    _emit("  developer_task_proposal_intake  Validate DTR-A pure model proposal intake and manifest binding", log_file)
    _emit("  developer_task_rehearsal  Validate DTR-B non-promotable static rehearsal orchestration", log_file)
    _emit("  developer_task_preflight  Validate developer task preflight safety gates", log_file)
    _emit("  package_boundaries  Validate production package layout boundaries", log_file)
    _emit("  scm01_host_worker  Validate SCM01 host worker source/fake contract", log_file)
    _emit("  action_execution_boundary  Validate HWA02-A action contract and exact B1 timer wiring", log_file)
    _emit("  timer_action_runtime  Validate HWA02-B1 timer runtime bridge", log_file)
    _emit("  volume_action_runtime  Validate HWA02-B2 volume/repeat runtime bridge", log_file)
    _emit("  core_package  Run core infrastructure package migration checks", log_file)
    _emit("  runtime_package  Run runtime coordination package migration checks", log_file)
    _emit("  learning_package  Run learning infrastructure package migration checks", log_file)
    _emit("  desktop_package  Run desktop interaction package migration checks", log_file)
    _emit("  intent_rule_policy  Evaluate exact intent rule architecture policy", log_file)
    _emit("  nlu_config_contract  Evaluate NLU environment configuration contract", log_file)
    _emit("", log_file)
    _emit("Options:", log_file)
    _emit("  --log-file <path>  Save pipeline output to selected file", log_file)
    _emit("  --no-log           Do not create pipeline log file", log_file)
    _emit("  --summary-json <new-path>  Write a JSON result to a new file", log_file)
    _emit("  --describe         Show commands' known effects without executing the flow", log_file)
    _emit("", log_file)
    _emit("Example maintenance sequence (later steps write data/model):", log_file)
    _emit("  1) python tools/pipeline.py check", log_file)
    _emit("  2) python tools/pipeline.py analyze", log_file)
    _emit("  3) python tools/pipeline.py promote", log_file)
    _emit("  4) python tools/pipeline.py label", log_file)
    _emit("  5) python tools/pipeline.py train", log_file)
    _emit("  6) python tools/pipeline.py check", log_file)
    _emit("", log_file)
    _emit("Notes:", log_file)
    _emit("  - Logs are saved by default to data/logs/pipeline/.", log_file)
    _emit("  - Step results are PASS, FAIL, SKIP, or NOT_RUN; SKIP does not count as PASS.", log_file)
    _emit("  - Exit 0 means no step failed; skipped checks produce an INCOMPLETE summary.", log_file)
    _emit("  - When consuming JSON, require actual exit 0 plus valid current PASS and all_steps_passed true.", log_file)
    _emit("  - The JSON parent directory must exist; an existing file is never overwritten.", log_file)
    _emit("  - Missing, empty or invalid JSON is not a successful result.", log_file)
    _emit("  - --no-log disables only the text log; an explicitly requested JSON is still written.", log_file)
    _emit("  - --no-log does not disable data/model writes made by child commands.", log_file)
    _emit("  - --describe creates no runner log/result; it cannot be combined with output file options.", log_file)
    _emit("  - Descriptions show known default-command effects; UNREVIEWED never means read-only.", log_file)
    _emit("  - 'raw_inbox' is NOT part of normal promote flow.", log_file)
    _emit("  - Use 'raw_inbox' only when you intentionally want to inspect noisy raw cases.", log_file)
    _emit("  - 'label' is interactive; its inner prompt output may not be fully captured in log.", log_file)
    _emit("  - 'full' does NOT run label/train/eval on purpose.", log_file)


def run_step_result(step: Step, *, cwd: Path, log_file: TextIO | None = None) -> StepResult:
    reason = _skip_reason(step)
    if reason:
        return _step_result(step, "SKIP", None, reason, log_file,
                            reason_code="requires_windows")

    _emit("", log_file)
    _emit("=" * 72, log_file)
    _emit(f"[RUN] {step.name}", log_file)
    _emit(f"[CMD] {' '.join(step.cmd)}", log_file)
    _emit("=" * 72, log_file)

    env = _build_child_env(cwd)

    # Интерактивные команды лучше не запускать через stdout=PIPE,
    # иначе input()/prompt могут работать неудобно.
    if step.interactive:
        _emit("[INFO] Interactive step: child output is shown in console directly.", log_file)
        _emit("[INFO] Interactive child output may not be fully captured in pipeline log.", log_file)

        try:
            completed = subprocess.run(step.cmd, cwd=str(cwd), env=env, check=False)
        except KeyboardInterrupt:
            return _step_result(step, "FAIL", 130, "interrupted by user", log_file,
                                reason_code="interrupted")
        except Exception as exc:
            return _step_result(step, "FAIL", 1, f"{type(exc).__name__}: {exc}", log_file,
                                reason_code="execution_error")

        rc = int(completed.returncode)
    else:
        process: subprocess.Popen[str] | None = None

        try:
            process = subprocess.Popen(
                step.cmd,
                cwd=str(cwd),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )

            if process.stdout is not None:
                for line in process.stdout:
                    _emit_raw(line, log_file)

            rc = int(process.wait())

        except KeyboardInterrupt:
            if process is not None:
                try:
                    process.kill()
                    process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            return _step_result(step, "FAIL", 130, "interrupted by user", log_file,
                                reason_code="interrupted")
        except Exception as exc:
            return _step_result(step, "FAIL", 1, f"{type(exc).__name__}: {exc}", log_file,
                                reason_code="execution_error")
        finally:
            if process is not None and process.stdout is not None:
                process.stdout.close()

    if rc != 0:
        return _step_result(step, "FAIL", rc, f"exit code {rc}", log_file,
                            reason_code="nonzero_exit")
    return _step_result(step, "PASS", 0, "", log_file)


def run_step(step: Step, *, cwd: Path, log_file: TextIO | None = None) -> int:
    """Legacy integer API; inspect run_step_result for PASS versus SKIP."""
    result = run_step_result(step, cwd=cwd, log_file=log_file)
    return result.returncode if result.returncode is not None else 0


def _flow_summary(result: FlowResult, log_file: TextIO | None) -> None:
    _emit("", log_file)
    _emit(f"[SUMMARY] Flow '{result.flow}': " + "; ".join(
        f"{status}={count}" for status, count in result.counts.items()
        if status != "TOTAL"), log_file)


def run_flow_result(flow_name: str, *, log_file: TextIO | None = None) -> FlowResult:
    flows = available_flows()
    steps = flows.get(flow_name)

    if not steps:
        _emit(f"[FAIL] Unknown flow: {flow_name}", log_file)
        _emit("", log_file)
        print_help(log_file)
        return FlowResult(flow_name, (), 2, reason_code="unknown_flow")

    _emit(f"[INFO] Project root: {PROJECT_ROOT}", log_file)
    _emit(f"[INFO] Selected flow: {flow_name}", log_file)

    results: list[StepResult] = []
    for index, step in enumerate(steps):
        result = run_step_result(step, cwd=PROJECT_ROOT, log_file=log_file)
        results.append(result)
        if result.status == "FAIL":
            _emit("", log_file)
            _emit(f"[STOP] Flow '{flow_name}' stopped on step: {step.name}", log_file)
            for pending in steps[index + 1:]:
                results.append(_step_result(pending, "NOT_RUN", None,
                                            f"flow stopped after: {step.name}", log_file,
                                            reason_code="flow_stopped"))
            outcome = FlowResult(flow_name, tuple(results),
                                 result.returncode if result.returncode is not None else 1)
            _flow_summary(outcome, log_file)
            return outcome

    outcome = FlowResult(flow_name, tuple(results), 0)
    _flow_summary(outcome, log_file)
    if outcome.status == "INCOMPLETE":
        _emit(f"[INCOMPLETE] Flow '{flow_name}' completed with skipped checks; "
              "not all checks were run.", log_file)
    else:
        _emit(f"[DONE] Flow '{flow_name}' completed successfully.", log_file)
    # Compatibility: platform skips were non-failing before this change.
    # Exit 0 means no step failed, not that every check ran. See the summary.
    return outcome


def run_flow(flow_name: str, *, log_file: TextIO | None = None) -> int:
    """Legacy integer API; inspect run_flow_result for completeness."""
    return run_flow_result(flow_name, log_file=log_file).returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("flow", nargs="?", default="help")
    parser.add_argument("--log-file", default=None)
    parser.add_argument("--no-log", action="store_true")
    parser.add_argument("--summary-json", default=None)
    parser.add_argument("--describe", action="store_true")
    parser.add_argument("-h", "--help", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    flow_name = str(args.flow).strip().lower()

    if args.help or flow_name in {"help", "--help", "-h"}:
        print_help()
        return 0

    if args.describe:
        if args.summary_json is not None or args.log_file is not None:
            _emit("[FAIL] --describe cannot be combined with --summary-json or --log-file; no steps executed.")
            return 2
        return print_flow_description(flow_name)

    summary_path = Path(args.summary_json) if args.summary_json is not None else None
    if summary_path is not None and not summary_path.is_absolute():
        summary_path = PROJECT_ROOT / summary_path
    log_path = None if args.no_log else _select_log_path(flow_name, args.log_file)

    try:
        if summary_path is not None and log_path is not None and (
                summary_path.resolve() == log_path.resolve()):
            _emit("[FAIL] Pipeline JSON summary and text log must use different files.")
            return 2

        with ExitStack() as outputs:
            # Reserve the requested new file before any child can run. A crash
            # can leave an empty/partial file, never a stale successful report.
            # Do not resolve this path before opening: x mode also refuses an
            # existing symlink, including a dangling one.
            summary_file = (outputs.enter_context(summary_path.open(
                "x", encoding="utf-8", newline="\n")) if summary_path is not None else None)
            log_file = None
            if log_path is not None:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_file = outputs.enter_context(log_path.open("w", encoding="utf-8", newline=""))
                _emit(f"[INFO] Pipeline log: {log_path}", log_file)

            result = run_flow_result(flow_name, log_file=log_file)
            if log_file is not None:
                _emit(f"[INFO] Pipeline log saved: {log_path}", log_file)
            if summary_file is not None:
                json.dump(result.to_dict(), summary_file, ensure_ascii=False, indent=2)
                summary_file.write("\n")
                summary_file.flush()
    except (OSError, ValueError) as exc:
        _emit(f"[FAIL] Pipeline output could not be prepared or saved: {type(exc).__name__}: {exc}")
        return 2

    if summary_path is not None:
        _emit(f"[INFO] Pipeline JSON summary saved: {summary_path}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
