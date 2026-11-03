"""M226: optional, read-only *shadow* scoring of GUI M130's function pool.

No change to the authoritative M130 shortlist, GUI selection, DTR-A privileges,
source files, checkpoints, private feedback or training. The task text stays in
an in-memory pipe to a bounded, isolated Python child; it is never logged.
"""
from __future__ import annotations

import ast
from collections.abc import Mapping
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import unicodedata
import warnings

SCHEMA = "SKYNETVS_M226_SHADOW_RANKING_V1"
MODEL_SHA256 = "8fe8e5562ade941762824c03e40ed1339eecce1b22c20ded265f4fef9611a0f7"
MODEL_BYTES = 2099338
MODEL_SCHEMA = "SKYNETVS_M163_OWN_HASHED_RETRIEVER_CANDIDATE_V1"
MODEL_TRAIN_HEAD = "a5ae5f554b88eef6584fe5d7726cdf71c06830bd"
MODEL_NAME = "M163_OwnRetriever_Experimental.pt"
HASH_BUCKETS = 16384
EMBED_DIM = 32
MAX_FEATURES = 144
WORD = re.compile(r"[a-zа-яё][a-zа-яё0-9_]{1,47}", re.I)
RUN_NAME = re.compile(r"m163_[a-f0-9]{32}\Z")
SELECTOR = re.compile(r"(?:main\.py|modules/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.py)::[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)*@[1-9][0-9]{0,6}\Z")


class ShadowRefused(ValueError):
    pass


def require(value, code):
    if not value:
        raise ShadowRefused(code)


def snapshot_digest(sources):
    """Bind GUI and child to identical source *data*, without returning it."""
    digest = hashlib.sha256()
    for path, text in sorted(sources.items()):
        digest.update(path.encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(text.encode("utf-8")).digest())
    return digest.hexdigest()


def pool_items(ranking):
    """Exactly M130's positive lexical function pool, before its Top-8 trim."""
    if ranking["file_ranks"]["retrieval_confidence"] != "LEXICAL_MATCH_EXISTS":
        return []
    rows, seen = [], set()
    for item in ranking["function_rank_top100"]:
        if item.get("bm25_name_body_score", 0) <= 0 or item.get("kind") not in ("FunctionDef", "AsyncFunctionDef"):
            continue
        key = (item["path"], item["qualname"], item["start"], item["end"])
        require(key not in seen and type(item["start"]) is int and type(item["end"]) is int,
                "M226_POOL_INVALID")
        seen.add(key)
        rows.append({"path": key[0], "qualname": key[1], "start": key[2], "end": key[3]})
    require(len(rows) <= 100, "M226_POOL_LIMIT")
    return rows


def _plain(path, directory=False):
    try:
        st = path.lstat()
    except OSError:
        return False
    return (not stat.S_ISLNK(st.st_mode) and
            not (getattr(st, "st_file_attributes", 0) & 0x400) and
            (stat.S_ISDIR(st.st_mode) if directory else stat.S_ISREG(st.st_mode)) and
            (directory or st.st_nlink == 1))


def find_model():
    """Read a single previously verified private checkpoint; never download."""
    root = Path(os.environ.get("LOCALAPPDATA") or "") / "SkynetVS" / "ModelLab" / "Runs"
    require(os.environ.get("LOCALAPPDATA") and _plain(root, directory=True),
            "MODEL_NOT_AVAILABLE")
    matches = []
    runs = list(root.iterdir())
    require(len(runs) <= 4096, "MODEL_RUN_DIRECTORY_LIMIT")
    for run in runs:
        if not RUN_NAME.fullmatch(run.name):
            continue
        require(_plain(run, directory=True), "MODEL_RUN_UNSAFE")
        private = run / "private_model"
        if not private.exists():
            continue
        require(_plain(private, directory=True), "MODEL_PRIVATE_PATH_UNSAFE")
        candidate = private / MODEL_NAME
        if not candidate.exists():
            continue
        require(_plain(candidate), "MODEL_FILE_UNSAFE")
        if candidate.stat().st_size != MODEL_BYTES:
            continue
        raw = candidate.read_bytes()
        if hashlib.sha256(raw).hexdigest() == MODEL_SHA256:
            matches.append(raw)
    require(len(matches) == 1, "MODEL_NOT_UNIQUE_OR_MISSING")
    return matches[0]




# M226 live GUI refusal telemetry: finite codes only, never exception messages,
# traceback, paths, goal text, checkpoint contents, or worker stdout.
_SAFE_REFUSALS = frozenset({
    "MODEL_NOT_AVAILABLE", "MODEL_RUN_DIRECTORY_LIMIT", "MODEL_RUN_UNSAFE",
    "MODEL_PRIVATE_PATH_UNSAFE", "MODEL_FILE_UNSAFE", "MODEL_NOT_UNIQUE_OR_MISSING",
    "M226_REQUEST_TOO_LARGE", "M226_REQUEST_INVALID", "M226_POOL_REQUEST_INVALID",
    "M226_POOL_EMPTY", "M226_REPO_INVALID", "M226_SNAPSHOT_CHANGED",
    "M226_HEAD_CHANGED", "M226_POOL_DUPLICATE", "M226_POOL_SOURCE_NOT_SCANNED",
    "M226_SYMBOL_AST_MISMATCH", "M226_SYMBOL_IDENTITY_CONFLICT",
    "M226_MODEL_PROFILE_INVALID", "M226_MODEL_TENSOR_INVALID",
    "M226_MODEL_SCORE_NONFINITE", "M226_POOL_INVALID", "M226_POOL_LIMIT",
    "M226_WORKER_PYTHON_UNSAFE", "M226_CHILD_FAILED",
    "M226_SHADOW_RESULT_INVALID", "M226_SHADOW_SELECTION_ESCALATION_REFUSED",
})
_STAGE_NAMES = {
    "find_model": "MODEL_DISCOVERY", "rank_pool_model": "INFERENCE",
    "symbols_for_pool": "SYMBOLS", "scan_head": "GIT_SCAN",
    "_run": "GIT_READ", "_sha": "GIT_READ",
    "_worker": "WORKER", "maybe_shadow": "PARENT",
    "worker_main": "WORKER", "pool_items": "POOL",
}


def _diagnostic_code(exc):
    """Classify only trusted exception structure into a bounded, safe symbol."""
    if isinstance(exc, ShadowRefused):
        code = exc.args[0] if len(exc.args) == 1 else None
        if type(code) is str and code in _SAFE_REFUSALS:
            suffix = code[5:] if code.startswith("M226_") else code
            return "M226_REFUSED_" + suffix
        return "M226_REFUSED_UNRECOGNIZED"
    if isinstance(exc, subprocess.TimeoutExpired):
        category = "TIMEOUT"
    elif isinstance(exc, ModuleNotFoundError):
        category = "TORCH_MISSING" if exc.name == "torch" else "MODULE_MISSING"
    elif isinstance(exc, ImportError):
        category = "IMPORT_ERROR"
    elif isinstance(exc, PermissionError):
        category = "PERMISSION_ERROR"
    elif isinstance(exc, FileNotFoundError):
        category = "FILE_MISSING"
    elif isinstance(exc, OSError):
        category = "OS_ERROR"
    elif isinstance(exc, (ValueError, TypeError, KeyError, AttributeError)):
        category = "CONTRACT_ERROR"
    elif isinstance(exc, MemoryError):
        category = "MEMORY_ERROR"
    elif isinstance(exc, RuntimeError):
        category = "RUNTIME_ERROR"
    else:
        category = "OTHER_ERROR"
    stage = "GENERAL"
    tb = exc.__traceback__
    while tb is not None:
        function = tb.tb_frame.f_code.co_name
        if function in _STAGE_NAMES:
            stage = _STAGE_NAMES[function]
        tb = tb.tb_next
    return "M226_" + stage + "_" + category


def _validated_child_code(result):
    value = result.get("diagnostic_code") if type(result) is dict else None
    if (type(value) is str and 0 < len(value) <= 80 and
            value.startswith("M226_") and
            all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for c in value)):
        return value
    return "M226_CHILD_UNAVAILABLE"

def feature_ids(text, max_features=MAX_FEATURES):
    """Byte-for-byte M163 frozen hashed word/character n-gram feature logic."""
    text = unicodedata.normalize("NFKC", text.casefold())
    ids, seen = [], set()
    for word in WORD.findall(text)[:180]:
        word = word[:42]
        parts = ["w:" + word]
        bounded = "^" + word + "$"
        for k in (3, 4):
            parts.extend("c:" + bounded[i:i + k] for i in range(len(bounded) - k + 1))
        for part in parts:
            ident = 1 + int.from_bytes(
                hashlib.blake2s(part.encode("utf-8"), digest_size=4).digest(), "big") % (HASH_BUCKETS - 1)
            if ident not in seen:
                seen.add(ident)
                ids.append(ident)
                if len(ids) >= max_features:
                    return ids
    return ids or [0]


def symbols_for_pool(sources, pool):
    """Match exact AST definitions; code strings are ephemeral and not persisted."""
    wanted = {(x["path"], x["qualname"], x["start"], x["end"]) for x in pool}
    require(len(wanted) == len(pool) and len(pool) <= 100, "M226_POOL_DUPLICATE")
    result = {}
    for path in sorted({x["path"] for x in pool}):
        require(path in sources, "M226_POOL_SOURCE_NOT_SCANNED")
        source = sources[path]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source, filename="<m226_git_blob_data>")
        lines = source.splitlines(keepends=True)
        def walk(node, parent=()):
            for child in ast.iter_child_nodes(node):
                named = isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                chain = (*parent, child.name) if named else parent
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    key = (path, ".".join(chain), child.lineno, child.end_lineno)
                    if key in wanted:
                        require(key not in result and child.end_lineno is not None and
                                child.end_lineno <= len(lines), "M226_SYMBOL_IDENTITY_CONFLICT")
                        raw = "".join(lines[child.lineno - 1:child.end_lineno])
                        doc = ast.get_docstring(child, clean=True) or ""
                        identifiers = []
                        for n in ast.walk(child):
                            if isinstance(n, ast.Name): identifiers.append(n.id)
                            elif isinstance(n, ast.Attribute): identifiers.append(n.attr)
                        code = (path.replace("/", " ") + " " + " ".join(chain) + " " +
                                " ".join(chain) + " " + doc[:350] + " " +
                                " ".join(identifiers[:130]) + " " + raw[:400])[:1300]
                        result[key] = code
                walk(child, chain)
        walk(tree)
    require(set(result) == wanted, "M226_SYMBOL_AST_MISMATCH")
    return result


def rank_pool_model(*, goal, sources, pool, checkpoint_bytes):
    """Run fixed M163 CPU inference on *M130's* candidates only."""
    import torch  # only in child, after model bytes and Git snapshot validation
    from .context_search import expand_query

    torch.set_num_threads(min(2, max(1, torch.get_num_threads())))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        checkpoint = torch.load(io.BytesIO(checkpoint_bytes), map_location="cpu", weights_only=True)
    require(type(checkpoint) is dict and checkpoint.get("schema") == MODEL_SCHEMA and
            checkpoint.get("trained_on_head") == MODEL_TRAIN_HEAD and
            checkpoint.get("hash_buckets") == HASH_BUCKETS and
            checkpoint.get("embedding_dim") == EMBED_DIM and
            checkpoint.get("training_labels") == 37 and
            checkpoint.get("not_deployed") is True and
            isinstance(checkpoint.get("state_dict"), Mapping) and
            set(checkpoint["state_dict"]) == {"weights.weight"}, "M226_MODEL_PROFILE_INVALID")
    weight = checkpoint["state_dict"]["weights.weight"]
    require(isinstance(weight, torch.Tensor) and tuple(weight.shape) ==
            (HASH_BUCKETS, EMBED_DIM) and bool(torch.isfinite(weight).all().item()),
            "M226_MODEL_TENSOR_INVALID")
    q_text, _ = expand_query(goal)
    codes = symbols_for_pool(sources, pool)
    def embedding(ids):
        positions = torch.tensor(ids, dtype=torch.long)
        with torch.no_grad():
            z = weight[positions].sum(dim=0) / math.sqrt(len(ids))
            return torch.nn.functional.normalize(z, p=2, dim=0, eps=1e-8)
    with torch.no_grad():
        q_vector = embedding(feature_ids(q_text))
        scored = []
        for row in pool:
            key = (row["path"], row["qualname"], row["start"], row["end"])
            code_vector = embedding(feature_ids(codes[key]))
            score = float(torch.dot(code_vector, q_vector).item())
            require(math.isfinite(score), "M226_MODEL_SCORE_NONFINITE")
            scored.append((score, row))
    scored.sort(key=lambda x: (-x[0], x[1]["path"], x[1]["qualname"], x[1]["start"]))
    return [f"{r['path']}::{r['qualname']}@{r['start']}" for _, r in scored[:8]]


def _worker(request):
    from .context_search import scan_head
    from .git_source import GitSourceReader, find_git
    require(type(request) is dict and request.get("schema") == SCHEMA and
            type(request.get("goal")) is str and 0 < len(request["goal"]) <= 1200 and
            type(request.get("commit")) is str and
            re.fullmatch(r"[0-9a-f]{40}", request["commit"]) and
            type(request.get("digest")) is str and
            re.fullmatch(r"[0-9a-f]{64}", request["digest"]), "M226_REQUEST_INVALID")
    pool = request.get("pool")
    require(type(pool) is list and len(pool) <= 100 and all(
        type(x) is dict and set(x) == {"path", "qualname", "start", "end"} and
        type(x["path"]) is str and type(x["qualname"]) is str and
        type(x["start"]) is int and type(x["end"]) is int and
        0 < x["start"] <= x["end"] <= 9999999 and
        SELECTOR.fullmatch(f"{x['path']}::{x['qualname']}@{x['start']}")
        for x in pool), "M226_POOL_REQUEST_INVALID")
    require(len(pool) > 0, "M226_POOL_EMPTY")
    repo = Path(os.path.abspath(sys.argv[1]))
    require(_plain(repo, directory=True), "M226_REPO_INVALID")
    reader = GitSourceReader(repo, find_git())
    commit, sources, scan = scan_head(reader)
    require(commit == request["commit"] and scan.get("partial") is False and
            snapshot_digest(sources) == request["digest"], "M226_SNAPSHOT_CHANGED")
    checkpoint = find_model()
    ranking = rank_pool_model(goal=request["goal"], sources=sources,
                              pool=pool, checkpoint_bytes=checkpoint)
    require(reader._sha("rev-parse", "--verify", "HEAD^{commit}") == commit,
            "M226_HEAD_CHANGED")
    return {"schema": SCHEMA, "status": "ADVISORY", "commit": commit,
            "model_sha256": MODEL_SHA256, "pool_size": len(pool), "top": ranking,
            "trained_on_user_labels": False, "model_deployed": False,
            "selection_authorized": False, "no_patch_or_apply": True}


def worker_main(*, protocol_fd=None):
    """Write one ASCII JSON frame to the private pipe, not to library stdout."""
    try:
        raw = sys.stdin.buffer.read(32769)
        require(len(raw) <= 32768, "M226_REQUEST_TOO_LARGE")
        data = json.loads(raw.decode("utf-8", "strict"))
        reply = _worker(data)
    except BaseException as exc:
        # Finite reason code only. Never output exception text or task data.
        reply = {"schema": SCHEMA, "status": "UNAVAILABLE",
                 "diagnostic_code": _diagnostic_code(exc)}
    frame = json.dumps(reply, ensure_ascii=True, separators=(",", ":")) + "\n"
    if protocol_fd is None:
        # Backward-compatible direct/test calls. GUI always uses protocol_fd.
        sys.stdout.write(frame)
    else:
        # Bootstrap saved a duplicate of the child's stdout PIPE, then moved
        # the ordinary stdout fd onto stderr BEFORE imports/inference.
        # Any Python/torch/colorama exit-time ANSI now goes to stderr, not JSON.
        if type(protocol_fd) is not int or protocol_fd < 3:
            return 2
        try:
            remaining = memoryview(frame.encode("ascii"))
            while remaining:
                written = os.write(protocol_fd, remaining)
                if written <= 0:
                    return 2
                remaining = remaining[written:]
        finally:
            os.close(protocol_fd)
    return 0


def maybe_shadow(repository, goal, commit, sources, ranking):
    """One bounded optional subprocess; never blocks or replaces M130 success."""
    fallback = {"schema": SCHEMA, "status": "UNAVAILABLE", "selection_authorized": False,
                "model_deployed": False, "no_patch_or_apply": True}
    contract_stage = "POOL"
    try:
        pool = pool_items(ranking)
        if not pool:
            return {**fallback, "diagnostic_code": "M226_POOL_EMPTY"}
        contract_stage = "REQUEST_DIGEST"
        request = {"schema": SCHEMA, "goal": goal, "commit": commit,
                   "digest": snapshot_digest(sources), "pool": pool}
        contract_stage = "REQUEST_JSON"
        encoded = json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        require(len(encoded) <= 32768, "M226_REQUEST_TOO_LARGE")
        repo = os.path.abspath(str(repository))
        # Task text passes only via an anonymous pipe, never via argv or disk.
        bootstrap = ("import os,sys;_m226_proto=os.dup(1);os.dup2(2,1);"
                     "sys.path.insert(0,sys.argv[1]);"
                     "from modules.developer_task_ui.app.task_symbol_shadow "
                     "import worker_main;sys.exit(worker_main(protocol_fd=_m226_proto))")
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("PYTHON", "GIT_", "SSH_"))}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        # GUI uses -S; Python 3.12 may expose base sys.executable without torch.
        # On Windows select only this repository's non-reparse .venv Python.
        if os.name == "nt":
            project_venv = Path(repo) / ".venv"
            project_scripts = project_venv / "Scripts"
            worker_python = project_scripts / "python.exe"
            require(_plain(project_venv, directory=True) and
                    _plain(project_scripts, directory=True) and
                    _plain(worker_python), "M226_WORKER_PYTHON_UNSAFE")
        else:
            worker_python = Path(sys.executable)
        contract_stage = "CHILD_START"
        process = subprocess.run([str(worker_python), "-I", "-B", "-X", "utf8", "-c", bootstrap, repo],
                                 input=encoded, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 timeout=90, check=False, cwd=repo, env=env,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        contract_stage = "CHILD_PROCESS_CHECK"
        require(process.returncode == 0 and len(process.stdout) <= 4096 and
                len(process.stderr) <= 4096, "M226_CHILD_FAILED")
        contract_stage = "CHILD_JSON"
        result = json.loads(process.stdout.decode("utf-8", "strict"))
        contract_stage = "CHILD_STATUS"
        if result.get("status") != "ADVISORY":
            return {**fallback, "diagnostic_code": _validated_child_code(result)}
        contract_stage = "CHILD_CONTRACT"
        require(result.get("schema") == SCHEMA and result.get("commit") == commit and
                result.get("model_sha256") == MODEL_SHA256 and result.get("pool_size") == len(pool) and
                result.get("trained_on_user_labels") is False and
                result.get("model_deployed") is False and
                result.get("selection_authorized") is False and
                result.get("no_patch_or_apply") is True, "M226_SHADOW_RESULT_INVALID")
        contract_stage = "CHILD_TOP"
        top = result.get("top")
        contract_stage = "ALLOWED_POOL"
        allowed = {f"{item['path']}::{item['qualname']}@{item['start']}" for item in pool}
        require(type(top) is list and len(top) == min(len(pool), 8) and
                len(top) == len(set(top)) and all(x in allowed for x in top),
                "M226_SHADOW_SELECTION_ESCALATION_REFUSED")
        # Strictly advisory. In particular this result must not populate the GUI combobox.
        return result
    except (Exception, KeyboardInterrupt) as exc:
        code = _diagnostic_code(exc)
        if code == "M226_PARENT_CONTRACT_ERROR":
            # Only finite, static diagnostic classes. Never expose stdout, paths,
            # task text, exception message, traceback or model contents.
            if contract_stage == "CHILD_JSON" and isinstance(exc, json.JSONDecodeError):
                raw = process.stdout if isinstance(process.stdout, bytes) else b""
                if not raw.strip():
                    code = "M226_PARENT_JSON_EMPTY"
                elif raw.lstrip().startswith(b"{") and raw.count(b"\n") > 1:
                    code = "M226_PARENT_JSON_EXTRA_OUTPUT"
                elif raw.lstrip().startswith(b"{"):
                    # Strict parser remains unchanged. Classify a malformed
                    # object without showing any stdout bytes, error message,
                    # target symbol, private path, or user goal.
                    msg = exc.msg
                    if msg == "Extra data":
                        try:
                            parsed, tail_pos = json.JSONDecoder().raw_decode(
                                raw.decode("utf-8", "strict").lstrip())
                        except (ValueError, UnicodeError):
                            code = "M226_PARENT_JSON_EXTRA_UNPARSEABLE"
                        else:
                            tail = raw.decode("utf-8", "strict").lstrip()[tail_pos:].lstrip()
                            if type(parsed) is dict and parsed.get("schema") == SCHEMA:
                                if tail.startswith("{"):
                                    code = "M226_PARENT_JSON_MULTIPLE_FRAMES"
                                elif tail.startswith("\x1b"):
                                    code = "M226_PARENT_JSON_TRAILING_ANSI"
                                elif tail:
                                    code = "M226_PARENT_JSON_TRAILING_NOISE"
                                else:
                                    code = "M226_PARENT_JSON_EXTRA_UNEXPLAINED"
                            else:
                                code = "M226_PARENT_JSON_EXTRA_AFTER_OTHER"
                    elif msg == "Unterminated string starting at":
                        code = "M226_PARENT_JSON_UNTERMINATED_STRING"
                    elif exc.pos >= len(exc.doc) - 1:
                        code = "M226_PARENT_JSON_INCOMPLETE_AT_END"
                    elif msg == "Expecting ':' delimiter":
                        code = "M226_PARENT_JSON_EXPECT_COLON"
                    elif msg == "Expecting ',' delimiter":
                        code = "M226_PARENT_JSON_EXPECT_COMMA"
                    elif msg == "Expecting property name enclosed in double quotes":
                        code = "M226_PARENT_JSON_EXPECT_PROPERTY"
                    elif msg == "Illegal trailing comma before end of object":
                        code = "M226_PARENT_JSON_TRAILING_COMMA"
                    elif msg == "Invalid \\escape":
                        code = "M226_PARENT_JSON_INVALID_ESCAPE"
                    elif msg == "Invalid control character at":
                        code = "M226_PARENT_JSON_CONTROL_CHARACTER"
                    elif msg == "Invalid \\uXXXX escape":
                        code = "M226_PARENT_JSON_INVALID_UNICODE_ESCAPE"
                    else:
                        code = "M226_PARENT_JSON_OTHER_SYNTAX"
                else:
                    code = "M226_PARENT_JSON_NONOBJECT_OUTPUT"
            elif contract_stage == "CHILD_JSON" and isinstance(exc, UnicodeDecodeError):
                code = "M226_PARENT_JSON_UTF8_INVALID"
            else:
                code = "M226_PARENT_CONTRACT_" + contract_stage
        return {**fallback, "diagnostic_code": code}
