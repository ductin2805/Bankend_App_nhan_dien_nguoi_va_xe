"""Migrate JSON persistence (history.json, runs/face_db.json) into PostgreSQL.

Usage: run from project root where DATABASE_URL is set (or set env var in script).
"""

import os
import json
import time
from typing import Any

from app.services.postgres_service import postgres_storage


def load_json(path: str) -> Any:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Failed to load {path}:", e)
        return None


def migrate_history(file_path: str = "history.json") -> int:
    data = load_json(file_path)
    if not data:
        print("No history file found or empty.")
        return 0

    inserted = 0
    for entry in data:
        try:
            eid = str(entry.get("id") or entry.get("timestamp") or f"h{int(time.time()*1000)}")
            machine_id = entry.get("machine_id") or "default"
            ts = float(entry.get("timestamp") or time.time())
            typ = entry.get("type")
            method = entry.get("method")
            path = entry.get("path")
            summary = entry.get("summary")
            full_result = entry.get("full_result")
            rep = entry.get("representative_image_path", "")

            # upsert (do nothing if exists)
            if postgres_storage.enabled:
                postgres_storage.execute(
                    """
                    INSERT INTO history_entries (id, machine_id, timestamp, type, method, path, summary, full_result, representative_image_path, raw_entry)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        eid,
                        machine_id,
                        float(ts),
                        typ,
                        method,
                        path,
                        postgres_storage.to_json(summary or {}),
                        postgres_storage.to_json(full_result) if full_result is not None else None,
                        rep,
                        postgres_storage.to_json(entry),
                    ),
                )
                inserted += 1
        except Exception as e:
            print("Error inserting history entry:", e)
    print(f"Migrated {inserted} history entries (attempted inserts).")
    return inserted


def migrate_face_db(path: str = os.path.join("runs", "face_db.json")) -> int:
    data = load_json(path)
    if not data:
        print("No face_db file found or empty.")
        return 0

    persons = data.get("persons") if isinstance(data, dict) else None
    if not isinstance(persons, list):
        print("No persons list in face db.")
        return 0

    inserted = 0
    for p in persons:
        try:
            pid = str(p.get("person_id") or p.get("id") or f"p{int(time.time()*1000)}")
            owner = p.get("owner_machine_id") or p.get("machine_id") or "default"
            name = p.get("name") or ""
            person_code = p.get("person_code") or ""
            info = p.get("info") or {}
            descriptors = p.get("descriptors") or p.get("descriptor") or []
            reg_path = p.get("registration_image_path") or ""
            created_at = float(p.get("created_at") or time.time())

            if postgres_storage.enabled:
                postgres_storage.execute(
                    """
                    INSERT INTO face_persons (person_id, owner_machine_id, name, person_code, info, descriptors, registration_image_path, created_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (person_id) DO UPDATE SET
                      owner_machine_id = EXCLUDED.owner_machine_id,
                      name = EXCLUDED.name,
                      person_code = EXCLUDED.person_code,
                      info = EXCLUDED.info,
                      descriptors = EXCLUDED.descriptors,
                      registration_image_path = EXCLUDED.registration_image_path,
                      created_at = EXCLUDED.created_at
                    """,
                    (
                        pid,
                        owner,
                        name,
                        person_code,
                        postgres_storage.to_json(info),
                        postgres_storage.to_json(descriptors),
                        reg_path,
                        float(created_at),
                    ),
                )
                inserted += 1
        except Exception as e:
            print("Error inserting person:", e)

    print(f"Migrated {inserted} face persons (attempted upserts).")
    return inserted


def main():
    if not postgres_storage.enabled:
        print("Postgres storage not enabled. Set DATABASE_URL and ensure psycopg2 is installed.")
        return

    h_count = migrate_history("history.json")
    f_count = migrate_face_db()

    print("Done. Summary:")
    print("  history entries attempted:", h_count)
    print("  face persons attempted:", f_count)

    # Optionally remove old files - we won't delete automatically; user said can drop old data.
    print("Migration complete. Old JSON files are left in place; delete them manually if you wish.")


if __name__ == "__main__":
    main()
