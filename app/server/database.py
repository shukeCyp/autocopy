from __future__ import annotations

import aiosqlite
import json
from pathlib import Path
from datetime import datetime

DB_PATH = Path(".data/server.db")


async def get_db() -> aiosqlite.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    await _ensure_schema(db)
    return db


async def _ensure_schema(db: aiosqlite.Connection) -> None:
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            graph_json TEXT NOT NULL DEFAULT '{}',
            current_step TEXT NOT NULL DEFAULT '',
            current_node_id TEXT NOT NULL DEFAULT '',
            current_node_label TEXT NOT NULL DEFAULT '',
            result_json TEXT NOT NULL DEFAULT '{}',
            error TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS templates (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            graph_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """)
    columns = await db.execute("PRAGMA table_info(templates)")
    column_names = {row["name"] for row in await columns.fetchall()}
    if "description" not in column_names:
        await db.execute("ALTER TABLE templates ADD COLUMN description TEXT NOT NULL DEFAULT ''")
    task_columns = await db.execute("PRAGMA table_info(tasks)")
    task_column_names = {row["name"] for row in await task_columns.fetchall()}
    if "current_node_id" not in task_column_names:
        await db.execute("ALTER TABLE tasks ADD COLUMN current_node_id TEXT NOT NULL DEFAULT ''")
    if "current_node_label" not in task_column_names:
        await db.execute("ALTER TABLE tasks ADD COLUMN current_node_label TEXT NOT NULL DEFAULT ''")
    await db.commit()


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---- Task operations ----

async def create_task(name: str, graph_json: str) -> dict:
    import uuid
    task_id = datetime.now().strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]
    now = now_iso()
    db = await get_db()
    await db.execute(
        "INSERT INTO tasks (id, name, status, graph_json, created_at, updated_at) VALUES (?, ?, 'pending', ?, ?, ?)",
        (task_id, name, graph_json, now, now),
    )
    await db.commit()
    await db.close()
    return await get_task(task_id)


async def get_task(task_id: str) -> dict | None:
    db = await get_db()
    row = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    result = await row.fetchone()
    await db.close()
    if result is None:
        return None
    return _task_row_to_dict(result)


async def list_tasks() -> list[dict]:
    db = await get_db()
    rows = await db.execute("SELECT * FROM tasks ORDER BY created_at DESC")
    results = [dict(row) for row in await rows.fetchall()]
    await db.close()
    return results


async def update_task(task_id: str, **fields) -> dict | None:
    if not fields:
        return await get_task(task_id)
    fields["updated_at"] = now_iso()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [task_id]
    db = await get_db()
    await db.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", values)
    await db.commit()
    await db.close()
    return await get_task(task_id)


async def delete_task(task_id: str) -> bool:
    db = await get_db()
    cursor = await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    await db.commit()
    deleted = cursor.rowcount > 0
    await db.close()
    return deleted


def _task_row_to_dict(row) -> dict:
    d = dict(row)
    d["graph_json"] = d.get("graph_json", "{}")
    d["result_json"] = d.get("result_json", "{}")
    return d


# ---- Settings operations ----

async def get_settings() -> dict:
    db = await get_db()
    row = await db.execute("SELECT value FROM settings WHERE key = 'global'")
    result = await row.fetchone()
    await db.close()
    if result is None:
        return {}
    return json.loads(result["value"])


async def save_settings(settings: dict) -> dict:
    db = await get_db()
    value = json.dumps(settings, ensure_ascii=False)
    await db.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES ('global', ?)",
        (value,),
    )
    await db.commit()
    await db.close()
    return settings


# ---- Template operations ----

async def list_templates() -> list[dict]:
    db = await get_db()
    rows = await db.execute("SELECT id, name, description, graph_json, created_at FROM templates ORDER BY created_at DESC")
    results = [dict(row) for row in await rows.fetchall()]
    await db.close()
    return results


async def get_template(template_id: str) -> dict | None:
    db = await get_db()
    row = await db.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
    result = await row.fetchone()
    await db.close()
    if result is None:
        return None
    return dict(result)


async def save_template(name: str, graph_json: str, description: str = "") -> dict:
    import uuid
    template_id = uuid.uuid4().hex[:12]
    now = now_iso()
    db = await get_db()
    await db.execute(
        "INSERT INTO templates (id, name, description, graph_json, created_at) VALUES (?, ?, ?, ?, ?)",
        (template_id, name, description, graph_json, now),
    )
    await db.commit()
    await db.close()
    return await get_template(template_id)


async def upsert_template(template_id: str, name: str, graph_json: str, description: str = "") -> dict:
    now = now_iso()
    db = await get_db()
    await db.execute(
        """
        INSERT INTO templates (id, name, description, graph_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            description = excluded.description,
            graph_json = excluded.graph_json
        """,
        (template_id, name, description, graph_json, now),
    )
    await db.commit()
    await db.close()
    return await get_template(template_id)


async def update_template(template_id: str, name: str, graph_json: str, description: str | None = None) -> dict | None:
    db = await get_db()
    if description is None:
        cursor = await db.execute(
            "UPDATE templates SET name = ?, graph_json = ? WHERE id = ?",
            (name, graph_json, template_id),
        )
    else:
        cursor = await db.execute(
            "UPDATE templates SET name = ?, description = ?, graph_json = ? WHERE id = ?",
            (name, description, graph_json, template_id),
        )
    await db.commit()
    updated = cursor.rowcount > 0
    await db.close()
    if not updated:
        return None
    return await get_template(template_id)


async def delete_template(template_id: str) -> bool:
    db = await get_db()
    cursor = await db.execute("DELETE FROM templates WHERE id = ?", (template_id,))
    await db.commit()
    deleted = cursor.rowcount > 0
    await db.close()
    return deleted
