"""M092 local Developer Task window, booted in a separate -I -S -B process.

This is not a security sandbox. It executes the checked bundled UI and contracts,
except one M101 exact-hash-pinned AST-extracted audio method in synthetic mock tests;
its one allowed patch requires typed user approval and a separate backup. No promotion.
It writes artifacts to a per-user data directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import traceback
import zipfile
from pathlib import Path


def verify_bundle(root: Path) -> None:
    manifest_path = root / "BUNDLE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "SKYNETVS_M092_UI_BUNDLE_V1":
        raise ValueError("M092_BUNDLE_SCHEMA_INVALID")
    records = manifest.get("files")
    if not isinstance(records, dict):
        raise ValueError("M092_BUNDLE_MANIFEST_INVALID")
    actual = set()
    for path in root.rglob("*"):
        st = path.lstat()
        if (stat.S_ISLNK(st.st_mode) or getattr(st, "st_file_attributes", 0) &
                getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)):
            raise ValueError("M092_BUNDLE_LINK")
        if stat.S_ISREG(st.st_mode):
            actual.add(path.relative_to(root).as_posix())
        elif not stat.S_ISDIR(st.st_mode):
            raise ValueError("M092_BUNDLE_NOT_FILE")
    if actual != set(records) | {"BUNDLE_MANIFEST.json"}:
        raise ValueError("M092_BUNDLE_FILE_SET_MISMATCH")
    for name, record in records.items():
        if not isinstance(name, str) or name.startswith("/") or ".." in name.split("/") or "\\" in name:
            raise ValueError("M092_MANIFEST_ENTRY_PATH_INVALID")
        data = (root / name).read_bytes()
        choices = [data]
        if Path(name).suffix.lower() in {".py", ".json"}:
            lf = data.replace(b"\r\n", b"\n")
            crlf = lf.replace(b"\n", b"\r\n")
            for value in (lf, crlf):
                if value not in choices:
                    choices.append(value)
        if not any(len(value) == record.get("bytes") and
                   hashlib.sha256(value).hexdigest() == record.get("sha256")
                   for value in choices):
            raise ValueError("M092_BUNDLE_HASH_MISMATCH:" + name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).absolute().parent
    run = args.run.absolute()
    # Caller creates per-user run outside the code base; no project-relative artifacts.
    local = os.environ.get("LOCALAPPDATA", "")
    if not local or not Path(local).is_absolute():
        raise ValueError("M092_LOCALAPPDATA_REQUIRED")
    expected = Path(local) / "SkynetVS" / "DeveloperTask" / "Runs"
    if (run.parent != expected or not run.name.startswith("dtr_ui_") or
            not run.is_dir() or run.is_symlink()):
        raise ValueError("M092_RUN_DIRECTORY_NOT_APPROVED")
    verify_bundle(root)
    # Even if SkynetVS uses additional Python dependencies, this child sees only the
    # bundled read-only developer task contracts and Python standard library.
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(root / "vendor"), str(root)]
    for key in ("TCLLIBPATH", "TCL_LIBRARY", "TK_LIBRARY"):
        os.environ.pop(key, None)
    result = {
        "status": "M092_UI_STARTING", "ui_opened": False,
        "trusted_ui_and_bundled_dtra_executed": True,
        "selected_target_code_executed": False, "changed_code_executed": False,
        "patch_applied": False, "runtime_authorized": False,
        "promotion_authorized": False, "installation_authorized": False,
        "dtrb_reexecuted": False, "project_git_written": False,
        "project_tests_executed": False, "events": [], "error": None,
    }
    app = None
    code = 0
    try:
        from app.core import ArtifactStore
        from app.ui import DeveloperWindow, QuietTk
        store = ArtifactStore(run / "artifacts")
        window = QuietTk(className="SkynetVSDeveloperTask")
        app = DeveloperWindow(window, store, bundled_reference=root / "reference")
        window.update_idletasks()
        result["ui_opened"] = True
        print("WINDOW_READY=M092_EMBEDDED_DEVELOPER_TASK_UI", flush=True)
        print("BUNDLED_M074_READ_ONLY; M101_SCOPED_TYPED_APPROVAL_ONLY; NO_PROMOTION", flush=True)
        window.mainloop()
        result["status"] = "M092_UI_SESSION_CLOSED"
    except Exception as exc:
        code = 2
        result["status"] = "M092_UI_FAILED"
        result["error"] = type(exc).__name__ + ": " + str(exc)
        (run / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        print("ERROR=" + result["error"], flush=True)
    finally:
        if app is not None:
            result["events"] = app.events
            result["dtrb_receipt_viewed"] = app.dtrb_view is not None
            edits = [ev.get("event") for ev in app.events if ev.get("event") in
                     ("M101_ONE_FILE_APPLIED", "M101_ONE_FILE_ROLLED_BACK")]
            applied = "M101_ONE_FILE_APPLIED" in edits
            verified = [ev for ev in app.events if ev.get("event") == "M101_MOCK_VERIFIED"]
            result["patch_applied"] = applied  # ever applied, even if later rolled back
            result["m101_patch_currently_present_by_event"] = bool(edits and edits[-1] == "M101_ONE_FILE_APPLIED")
            result["m101_user_approval_recorded"] = applied
            result["m101_mock_test_runs"] = len(verified)
            result["changed_code_executed"] = bool(verified)  # scoped mock, not deployed execution
            result["changed_code_execution_scope"] = (
                "PINNED_AUDIO_DUCKER_AST_MOCK_ONLY" if verified else "NONE")
            result["selected_target_code_executed"] = bool(verified)
            result["selected_target_execution_scope"] = (
                "PINNED_AUDIO_DUCKER_AST_MOCK_ONLY" if verified else "NONE")
        (run / "M092_UI_Result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        paths = [run / "M092_UI_Result.json"]
        if (run / "error.txt").is_file():
            paths.append(run / "error.txt")
        if (run / "artifacts").is_dir():
            paths.extend(p for p in sorted((run / "artifacts").rglob("*")) if p.is_file() and not p.is_symlink())
        if sum(p.stat().st_size for p in paths) <= 16 * 1024 * 1024:
            dest = run / "M092_Interface_Result.zip"
            with zipfile.ZipFile(dest, "x", zipfile.ZIP_DEFLATED) as arc:
                for p in paths:
                    arc.write(p, p.relative_to(run).as_posix())
            print("RESULT_ZIP=" + str(dest), flush=True)
            print("RESULT_ZIP_SHA256=" + hashlib.sha256(dest.read_bytes()).hexdigest(), flush=True)
        else:
            print("RESULT_ZIP_NOT_CREATED=ARTIFACTS_EXCEED_16_MIB", flush=True)
        print("STATUS=" + result["status"], flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
