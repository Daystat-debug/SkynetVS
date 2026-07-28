from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TextIO


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_LOG_DIR = PROJECT_ROOT / "data" / "logs" / "pipeline"


@dataclass(frozen=True)
class Step:
    name: str
    cmd: list[str]
    interactive: bool = False


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


def _make_log_path(flow_name: str, explicit_path: str | None = None) -> Path:
    if explicit_path:
        path = Path(explicit_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_flow = _safe_log_name_part(flow_name)
        path = PIPELINE_LOG_DIR / f"{ts}_{safe_flow}.log"

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
    _emit("  audit      Check command registry consistency", log_file)
    _emit("  check      Run command audit + NLU eval", log_file)
    _emit("  confirmation Run confirmation phrase eval only", log_file)
    _emit("  analyze    Run analysis reports only", log_file)
    _emit("  promote    Export promotion results only", log_file)
    _emit("  raw_inbox  Export raw learning cases to inbox (rescue/manual path)", log_file)
    _emit("  label      Run label_inbox.py only", log_file)
    _emit("  train      Run train/train_nlu.py only", log_file)
    _emit("  eval       Run tools/eval_nlu.py only", log_file)
    _emit("  nlu_diag   Run NLU diagnostics with top-k candidates", log_file)
    _emit("  nlu_risk   Run NLU risk report", log_file)
    _emit("  nlu_risk_guard Run NLU risk guard", log_file)
    _emit("  full       Analyze + promote", log_file)
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
    _emit("  intent_rule_policy  Evaluate exact intent rule architecture policy", log_file)
    _emit("  nlu_config_contract  Evaluate NLU environment configuration contract", log_file)
    _emit("", log_file)
    _emit("Options:", log_file)
    _emit("  --log-file <path>  Save pipeline output to selected file", log_file)
    _emit("  --no-log           Do not create pipeline log file", log_file)
    _emit("", log_file)
    _emit("Recommended order:", log_file)
    _emit("  1) python tools/pipeline.py check", log_file)
    _emit("  2) python tools/pipeline.py analyze", log_file)
    _emit("  3) python tools/pipeline.py promote", log_file)
    _emit("  4) python tools/pipeline.py label", log_file)
    _emit("  5) python tools/pipeline.py train", log_file)
    _emit("  6) python tools/pipeline.py check", log_file)
    _emit("", log_file)
    _emit("Notes:", log_file)
    _emit("  - Logs are saved by default to data/logs/pipeline/.", log_file)
    _emit("  - 'raw_inbox' is NOT part of normal promote flow.", log_file)
    _emit("  - Use 'raw_inbox' only when you intentionally want to inspect noisy raw cases.", log_file)
    _emit("  - 'label' is interactive; its inner prompt output may not be fully captured in log.", log_file)
    _emit("  - 'full' does NOT run label/train/eval on purpose.", log_file)


def run_step(step: Step, *, cwd: Path, log_file: TextIO | None = None) -> int:
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
            _emit("\n[STOP] Interrupted by user.", log_file)
            return 130
        except Exception as e:
            _emit(f"[FAIL] {step.name}: {type(e).__name__}: {e}", log_file)
            return 1

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
                process.kill()
            _emit("\n[STOP] Interrupted by user.", log_file)
            return 130
        except Exception as e:
            _emit(f"[FAIL] {step.name}: {type(e).__name__}: {e}", log_file)
            return 1

    if rc != 0:
        _emit(f"[FAIL] {step.name}: exit code {rc}", log_file)
    else:
        _emit(f"[OK] {step.name}", log_file)

    return rc


def run_flow(flow_name: str, *, log_file: TextIO | None = None) -> int:
    flows = available_flows()
    steps = flows.get(flow_name)

    if not steps:
        _emit(f"[FAIL] Unknown flow: {flow_name}", log_file)
        _emit("", log_file)
        print_help(log_file)
        return 2

    _emit(f"[INFO] Project root: {PROJECT_ROOT}", log_file)
    _emit(f"[INFO] Selected flow: {flow_name}", log_file)

    for step in steps:
        rc = run_step(step, cwd=PROJECT_ROOT, log_file=log_file)
        if rc != 0:
            _emit("", log_file)
            _emit(f"[STOP] Flow '{flow_name}' stopped on step: {step.name}", log_file)
            return rc

    _emit("", log_file)
    _emit(f"[DONE] Flow '{flow_name}' completed successfully.", log_file)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("flow", nargs="?", default="help")
    parser.add_argument("--log-file", default=None)
    parser.add_argument("--no-log", action="store_true")
    parser.add_argument("-h", "--help", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    flow_name = str(args.flow).strip().lower()

    if args.help or flow_name in {"help", "--help", "-h"}:
        print_help()
        return 0

    if args.no_log:
        return run_flow(flow_name, log_file=None)

    log_path = _make_log_path(flow_name, args.log_file)

    with log_path.open("w", encoding="utf-8", newline="") as log_file:
        _emit(f"[INFO] Pipeline log: {log_path}", log_file)
        rc = run_flow(flow_name, log_file=log_file)
        _emit(f"[INFO] Pipeline log saved: {log_path}", log_file)

    return rc


if __name__ == "__main__":
    raise SystemExit(main())