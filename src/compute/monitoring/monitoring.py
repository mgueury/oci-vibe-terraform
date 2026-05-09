#!/usr/bin/env python3
import json
import logging
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import oracledb

ROOT_DIR = Path(os.path.expandvars("$HOME/app"))
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "60"))

DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_URL = os.environ["DB_URL"]

# Adjust if your cline command differs.
# The script sends the prompt on stdin and expects JSON on stdout.
CLINE_CMD = os.environ.get("CLINE_CMD", "cline").split()

LOG = logging.getLogger("logwatch")
LOG.setLevel(logging.DEBUG)

@dataclass
class RuleCache:
    normal: List[Dict[str, Any]]
    error: List[Dict[str, Any]]
    last_refresh: Optional[datetime]


def connect_db() -> oracledb.Connection:
    return oracledb.connect(user=DB_USER, password=DB_PASSWORD, dsn=DB_URL)


def discover_apps(root_dir: Path) -> List[Path]:
    if not root_dir.exists():
        return []
    return sorted([p for p in root_dir.iterdir() if p.is_dir()])


def discover_logs(app_dir: Path) -> List[Path]:
    return sorted([p for p in app_dir.glob("*.log") if p.is_file()])


def file_identity(path: Path) -> Tuple[int, int, float]:
    st = path.stat()
    inode = getattr(st, "st_ino", 0)
    return inode, st.st_size, st.st_mtime


def get_state(conn: oracledb.Connection, file_path: str) -> Optional[Dict[str, Any]]:
    LOG.info("<get_state>")
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT app_name, file_path, inode_num, offset_bytes, file_size, file_mtime
            FROM log_file_state
            WHERE file_path = :file_path
            """,
            {"file_path": file_path},
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "app_name": row[0],
            "file_path": row[1],
            "inode_num": row[2],
            "offset_bytes": int(row[3] or 0),
            "file_size": int(row[4] or 0),
            "file_mtime": row[5],
        }


def upsert_state(
    conn: oracledb.Connection,
    app_name: str,
    file_path: str,
    inode_num: int,
    offset_bytes: int,
    file_size: int,
    file_mtime: float,
) -> None:
    LOG.info("<upsert_state>")
    aware_dt = datetime.fromtimestamp(file_mtime, tz=timezone.utc)
    with conn.cursor() as cur:
        cur.execute(
            """
            MERGE INTO log_file_state t
            USING (
                SELECT :file_path AS file_path FROM dual
            ) s
            ON (t.file_path = s.file_path)
            WHEN MATCHED THEN UPDATE SET
                t.app_name = :app_name,
                t.inode_num = :inode_num,
                t.offset_bytes = :offset_bytes,
                t.file_size = :file_size,
                t.file_mtime = :file_mtime,
                t.updated_at = SYSTIMESTAMP
            WHEN NOT MATCHED THEN INSERT (
                app_name, file_path, inode_num, offset_bytes, file_size, file_mtime, updated_at
            ) VALUES (
                :app_name, :file_path, :inode_num, :offset_bytes, :file_size, :file_mtime, SYSTIMESTAMP
            )
            """,
            {
                "app_name": app_name,
                "file_path": file_path,
                "inode_num": inode_num,
                "offset_bytes": offset_bytes,
                "file_size": file_size,
                "file_mtime": aware_dt,
            },
        )
    conn.commit()


def load_rules_from_db(conn: oracledb.Connection, app_name: str) -> RuleCache:
    LOG.info(f"<load_rules_from_db> {app_name}")
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT rule_type, regex_text, note, updated_at
            FROM log_app_rules
            WHERE app_name = :app_name
              AND enabled = 'Y'
            ORDER BY id
            """,
            {"app_name": app_name},
        )
        rows = cur.fetchall()

    normal: List[Dict[str, Any]] = []
    error: List[Dict[str, Any]] = []
    last_refresh: Optional[datetime] = None

    for rule_type, regex_text, note, updated_at in rows:
        rule = {
            "regex": regex_text,
            "note": note,
        }
        if rule_type == "error":
            error.append(rule)
        else:
            normal.append(rule)

        if updated_at and (last_refresh is None or updated_at > last_refresh):
            last_refresh = updated_at

    return RuleCache(normal=normal, error=error, last_refresh=last_refresh)


def upsert_rule(
    conn: oracledb.Connection,
    app_name: str,
    rule_type: str,
    regex_text: str,
    note: Optional[str] = None,
    source: str = "llm",
    confidence: Optional[float] = None,
) -> None:
    LOG.info("<upsert_rule>")    
    with conn.cursor() as cur:
        cur.execute(
            """
            MERGE INTO log_app_rules t
            USING (
                SELECT :app_name AS app_name,
                       :rule_type AS rule_type,
                       :regex_text AS regex_text
                FROM dual
            ) s
            ON (
                t.app_name = s.app_name
                AND t.rule_type = s.rule_type
                AND t.regex_text = s.regex_text
            )
            WHEN MATCHED THEN UPDATE SET
                t.note = :note,
                t.source = :source,
                t.confidence = :confidence,
                t.enabled = 'Y',
                t.updated_at = SYSTIMESTAMP
            WHEN NOT MATCHED THEN INSERT (
                app_name, rule_type, regex_text, note, enabled, source, confidence, created_at, updated_at
            ) VALUES (
                :app_name, :rule_type, :regex_text, :note, 'Y', :source, :confidence, SYSTIMESTAMP, SYSTIMESTAMP
            )
            """,
            {
                "app_name": app_name,
                "rule_type": rule_type,
                "regex_text": regex_text,
                "note": note,
                "source": source,
                "confidence": confidence,
            },
        )
    conn.commit()


def classify_by_regex(line: str, rules: RuleCache) -> Tuple[str, Optional[str]]:
    LOG.info("<classify_by_regex>")        
    for rule in rules.error:
        pattern = rule.get("regex", "")
        if pattern and re.search(pattern, line):
            return "error", pattern

    for rule in rules.normal:
        pattern = rule.get("regex", "")
        if pattern and re.search(pattern, line):
            return "normal", pattern

    return "unknown", None


def insert_warning(
    conn: oracledb.Connection,
    app_name: str,
    file_path: str,
    line_no: int,
    line: str,
    severity: str,
    source: str,
    matched_rule: Optional[str],
    llm_reason: Optional[str],
) -> None:
    LOG.info(f"<insert_warning> {app_name} line_no={line_no} line={line}")       
    line_hash = sha256(f"{app_name}|{file_path}|{line}".encode("utf-8")).hexdigest()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO log_warnings (
                app_name, file_path, line_no, line_hash, severity, source,
                matched_rule, log_line, llm_reason
            )
            VALUES (
                :app_name, :file_path, :line_no, :line_hash, :severity, :source,
                :matched_rule, :log_line, :llm_reason
            )
            """,
            {
                "app_name": app_name,
                "file_path": file_path,
                "line_no": line_no,
                "line_hash": line_hash,
                "severity": severity,
                "source": source,
                "matched_rule": matched_rule,
                "log_line": line,
                "llm_reason": llm_reason,
            },
        )
    conn.commit()


def call_cline(prompt: str) -> Dict[str, Any]:
    LOG.info(f"<call_cline> {prompt}")          
    proc = subprocess.run(
        CLINE_CMD,
        input=prompt,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "cline failed")

    out = proc.stdout.strip()
    try:
        LOG.info(f"<call_cline> out={out}")          
        return json.loads(out)
    except json.JSONDecodeError:
        return {
            "severity": "warning",
            "reason": out,
            "suggested_regex": None,
            "pattern_type": None,
            "confidence": 0.0,
        }


def llm_classify(app_name: str, file_path: str, line: str) -> Dict[str, Any]:
    LOG.info("<llm_classify>")        
    prompt = f"""
You classify a log line for application: {app_name}
File: {file_path}

Return ONLY valid JSON with keys:
severity: one of ["normal", "warning", "error"]
reason: short explanation
suggested_regex: optional regex that could catch this pattern later, or null
confidence: number from 0 to 1

Example of output:
[
  { "severity": "normal", "reason": "normal line", "suggested_regex": "Success .*", "confidence": "1" }
]

Rules:
- If the line is clearly normal, severity = "normal"
- If it is suspicious but not clearly an error, severity = "warning"
- If it is an error, severity = "error"
- If you can learn a useful regex, include it in suggested_regex and set pattern_type accordingly.
- Prefer compact regexes that are specific enough not to overmatch.

Log line:
{line}
""".strip()

    return call_cline(prompt)


def maybe_learn_rule(
    conn: oracledb.Connection,
    app_name: str,
    rules: RuleCache,
    llm_result: Dict[str, Any],
) -> bool:
    LOG.info("<maybe_learn_rule>")      
    regex_text = llm_result.get("suggested_regex")
    pattern_type = llm_result.get("pattern_type")
    confidence = float(llm_result.get("confidence") or 0.0)

    if not regex_text or pattern_type not in {"normal", "error"}:
        return False

    if confidence < 0.80:
        return False

    bucket = rules.error if pattern_type == "error" else rules.normal
    if any(r.get("regex") == regex_text for r in bucket):
        return False

    upsert_rule(
        conn=conn,
        app_name=app_name,
        rule_type=pattern_type,
        regex_text=regex_text,
        note=llm_result.get("reason", "learned from LLM"),
        source="llm",
        confidence=confidence,
    )
    bucket.append({"regex": regex_text, "note": llm_result.get("reason", "learned from LLM")})
    return True


def process_file(
    conn: oracledb.Connection,
    app_dir: Path,
    log_path: Path,
    rules: RuleCache,
) -> None:
    LOG.info(f"<process_file> {app_dir}")      
    app_name = app_dir.name
    state = get_state(conn, str(log_path))
    inode, file_size, file_mtime = file_identity(log_path)

    offset = 0
    if state and state["inode_num"] == inode and file_size >= state["file_size"]:
        offset = int(state["offset_bytes"])
    elif state and state["inode_num"] != inode:
        offset = 0
    elif state and file_size < state["file_size"]:
        offset = 0

    line_no = 0
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        f.seek(offset)
        while True:
            pos_before = f.tell()
            line = f.readline()
            if not line:
                break

            line_no += 1
            line = line.rstrip("\n")
            if line=="": 
                break

            severity, matched_rule = classify_by_regex(line, rules)

            if severity == "normal":
                offset = f.tell()
                continue

            if severity == "error":
                insert_warning(
                    conn=conn,
                    app_name=app_name,
                    file_path=str(log_path),
                    line_no=line_no,
                    line=line,
                    severity="error",
                    source="regex",
                    matched_rule=matched_rule,
                    llm_reason=None,
                )
                offset = f.tell()
                continue

            try:
                llm_result = llm_classify(app_name, str(log_path), line)
            except Exception as exc:
                LOG.exception("LLM failed for %s: %s", log_path, exc)
                llm_result = {
                    "severity": "warning",
                    "reason": f"LLM failed: {exc}",
                    "suggested_regex": None,
                    "pattern_type": None,
                    "confidence": 0.0,
                }

            severity = str(llm_result.get("severity", "warning")).lower()
            reason = llm_result.get("reason")

            if severity in {"warning", "error"}:
                insert_warning(
                    conn=conn,
                    app_name=app_name,
                    file_path=str(log_path),
                    line_no=line_no,
                    line=line,
                    severity=severity,
                    source="llm",
                    matched_rule=None,
                    llm_reason=reason,
                )

            maybe_learn_rule(conn, app_name, rules, llm_result)
            offset = f.tell()

    upsert_state(
        conn=conn,
        app_name=app_name,
        file_path=str(log_path),
        inode_num=inode,
        offset_bytes=offset,
        file_size=file_size,
        file_mtime=file_mtime,
    )


def main() -> int:
    LOG.info(f"<main>")        
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    conn = connect_db()
    schema_path = Path(__file__).with_name("schema.sql")

    rules_cache: Dict[str, RuleCache] = {}

    LOG.info("Watching %s", ROOT_DIR)

    while True:
        try:
            apps = discover_apps(ROOT_DIR)

            for app_dir in apps:
                app_name = app_dir.name
                loaded_rules = load_rules_from_db(conn, app_name)

                cache = rules_cache.get(app_name)
                if cache is None or cache.last_refresh != loaded_rules.last_refresh:
                    rules_cache[app_name] = loaded_rules
                    LOG.info(
                        "Loaded rules for %s: %d normal, %d error",
                        app_name,
                        len(loaded_rules.normal),
                        len(loaded_rules.error),
                    )

                rules = rules_cache[app_name]

                for log_path in discover_logs(app_dir):
                    process_file(conn, app_dir, log_path, rules)

        except Exception:
            LOG.exception("Unexpected loop failure")

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    sys.exit(main())