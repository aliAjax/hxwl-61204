import json
import sqlite3
from pathlib import Path

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

DB_PATH = Path(__file__).resolve().parent.parent / "freezer_samples.db"


def conn():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with conn() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_code TEXT NOT NULL UNIQUE,
                project_name TEXT NOT NULL,
                freezer TEXT NOT NULL,
                shelf TEXT NOT NULL,
                slot TEXT NOT NULL,
                owner TEXT NOT NULL,
                stored_at TEXT DEFAULT CURRENT_TIMESTAMP,
                checked_out_at TEXT,
                status TEXT NOT NULL DEFAULT 'stored'
            )
            """
        )


def body(request) -> dict:
    return json.loads(request.body.decode("utf-8") or "{}")


def rows_to_json(rows) -> list[dict]:
    return [dict(row) for row in rows]


init_db()


def health(request):
    return JsonResponse({"status": "ok", "port": 61204})


@csrf_exempt
def samples(request):
    if request.method == "POST":
        payload = body(request)
        with conn() as db:
            cursor = db.execute(
                """
                INSERT INTO samples
                (sample_code, project_name, freezer, shelf, slot, owner)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["sample_code"],
                    payload["project_name"],
                    payload["freezer"],
                    payload["shelf"],
                    payload["slot"],
                    payload["owner"],
                ),
            )
            row = db.execute("SELECT * FROM samples WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return JsonResponse(dict(row), status=201)
    if request.method == "GET":
        with conn() as db:
            rows = db.execute("SELECT * FROM samples ORDER BY id DESC").fetchall()
            return JsonResponse(rows_to_json(rows), safe=False)
    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def move_sample(request, sample_id: int):
    if request.method != "PATCH":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    payload = body(request)
    with conn() as db:
        cursor = db.execute(
            """
            UPDATE samples
            SET freezer = ?, shelf = ?, slot = ?
            WHERE id = ? AND status = 'stored'
            """,
            (payload["freezer"], payload["shelf"], payload["slot"], sample_id),
        )
        if cursor.rowcount == 0:
            return JsonResponse({"error": "Stored sample not found"}, status=404)
        row = db.execute("SELECT * FROM samples WHERE id = ?", (sample_id,)).fetchone()
        return JsonResponse(dict(row))


@csrf_exempt
def checkout_sample(request, sample_id: int):
    if request.method != "PATCH":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    with conn() as db:
        cursor = db.execute(
            """
            UPDATE samples
            SET status = 'checked_out', checked_out_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = 'stored'
            """,
            (sample_id,),
        )
        if cursor.rowcount == 0:
            return JsonResponse({"error": "Stored sample not found"}, status=404)
        return JsonResponse({"checked_out": sample_id})


def slots(request):
    with conn() as db:
        rows = db.execute(
            """
            SELECT freezer, shelf, slot, sample_code, project_name, owner
            FROM samples
            WHERE status = 'stored'
            ORDER BY freezer, shelf, slot
            """
        ).fetchall()
        return JsonResponse(rows_to_json(rows), safe=False)


def owner_samples(request, owner: str):
    with conn() as db:
        rows = db.execute(
            """
            SELECT * FROM samples
            WHERE owner = ? AND status = 'stored'
            ORDER BY stored_at DESC
            """,
            (owner,),
        ).fetchall()
        return JsonResponse(rows_to_json(rows), safe=False)
