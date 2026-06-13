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
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS freezer_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                freezer TEXT NOT NULL UNIQUE,
                shelf_count INTEGER NOT NULL,
                slots_per_shelf INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
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
        freezer_configs = db.execute(
            "SELECT freezer, shelf_count, slots_per_shelf FROM freezer_configs ORDER BY freezer"
        ).fetchall()
        occupied_slots = db.execute(
            """
            SELECT freezer, shelf, slot, sample_code, project_name, owner
            FROM samples
            WHERE status = 'stored'
            """
        ).fetchall()

    occupied_map = {}
    for row in occupied_slots:
        key = (row["freezer"], str(row["shelf"]), str(row["slot"]))
        occupied_map[key] = {
            "sample_code": row["sample_code"],
            "project_name": row["project_name"],
            "owner": row["owner"],
        }

    all_slots = []
    for config in freezer_configs:
        freezer = config["freezer"]
        shelf_count = config["shelf_count"]
        slots_per_shelf = config["slots_per_shelf"]
        for shelf_num in range(1, shelf_count + 1):
            shelf = str(shelf_num)
            for slot_num in range(1, slots_per_shelf + 1):
                slot = str(slot_num)
                key = (freezer, shelf, slot)
                occupied = occupied_map.get(key)
                if occupied:
                    all_slots.append(
                        {
                            "freezer": freezer,
                            "shelf": shelf,
                            "slot": slot,
                            "status": "occupied",
                            "sample_code": occupied["sample_code"],
                            "project_name": occupied["project_name"],
                            "owner": occupied["owner"],
                        }
                    )
                else:
                    all_slots.append(
                        {
                            "freezer": freezer,
                            "shelf": shelf,
                            "slot": slot,
                            "status": "available",
                            "sample_code": None,
                            "project_name": None,
                            "owner": None,
                        }
                    )

    return JsonResponse(all_slots, safe=False)


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


@csrf_exempt
def freezer_config(request):
    if request.method == "GET":
        with conn() as db:
            rows = db.execute(
                """
                SELECT id, freezer, shelf_count, slots_per_shelf, created_at, updated_at
                FROM freezer_configs
                ORDER BY freezer
                """
            ).fetchall()
            return JsonResponse(rows_to_json(rows), safe=False)
    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def init_freezer(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    payload = body(request)
    freezer = payload.get("freezer")
    shelf_count = payload.get("shelf_count")
    slots_per_shelf = payload.get("slots_per_shelf")

    if not freezer or not shelf_count or not slots_per_shelf:
        return JsonResponse(
            {"error": "freezer, shelf_count, and slots_per_shelf are required"},
            status=400,
        )
    if not isinstance(shelf_count, int) or shelf_count <= 0:
        return JsonResponse(
            {"error": "shelf_count must be a positive integer"},
            status=400,
        )
    if not isinstance(slots_per_shelf, int) or slots_per_shelf <= 0:
        return JsonResponse(
            {"error": "slots_per_shelf must be a positive integer"},
            status=400,
        )

    with conn() as db:
        existing = db.execute(
            "SELECT id FROM freezer_configs WHERE freezer = ?", (freezer,)
        ).fetchone()
        if existing:
            db.execute(
                """
                UPDATE freezer_configs
                SET shelf_count = ?, slots_per_shelf = ?, updated_at = CURRENT_TIMESTAMP
                WHERE freezer = ?
                """,
                (shelf_count, slots_per_shelf, freezer),
            )
        else:
            db.execute(
                """
                INSERT INTO freezer_configs
                (freezer, shelf_count, slots_per_shelf)
                VALUES (?, ?, ?)
                """,
                (freezer, shelf_count, slots_per_shelf),
            )
        row = db.execute(
            "SELECT * FROM freezer_configs WHERE freezer = ?", (freezer,)
        ).fetchone()
        return JsonResponse(dict(row), status=201 if not existing else 200)
