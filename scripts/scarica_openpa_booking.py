from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests

BASE_URL = (
    "https://spazicomuni.comune.trento.it/"
    "openpa/data/booking_sala_pubblica/"
)

START_DATE = date(2025, 1, 1)
END_DATE = date.today() + timedelta(days=1)

ROOMS = {
    985812: "Sala Multiuso 2",
    985810: "Sala Video Nichelatti",
}

OUTPUT_DIR = Path("dati_openpa_booking")


def download_calendar(
    session: requests.Session,
    room_id: int,
) -> Any:
    response = session.get(
        BASE_URL,
        params={
            "sala": room_id,
            "start": START_DATE.isoformat(),
            "end": END_DATE.isoformat(),
        },
        headers={
            "Accept": "application/json",
            "User-Agent": (
                "PovoCivicCampus/1.0 "
                "(analisi utilizzo spazi pubblici)"
            ),
        },
        timeout=90,
    )

    response.raise_for_status()

    try:
        return response.json()
    except requests.JSONDecodeError as exc:
        preview = response.text[:500]
        raise RuntimeError(
            f"La risposta per la sala {room_id} non è JSON:\n{preview}"
        ) from exc


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    combined: dict[str, Any] = {
        "periodo": {
            "dal": START_DATE.isoformat(),
            "al_escluso": END_DATE.isoformat(),
        },
        "sale": {},
    }

    for room_id, room_name in ROOMS.items():
        print(f"Scarico {room_name} ({room_id})...")

        payload = download_calendar(session, room_id)

        room_record = {
            "id": room_id,
            "nome": room_name,
            "dati": payload,
        }

        combined["sale"][str(room_id)] = room_record

        output_file = OUTPUT_DIR / f"sala_{room_id}_calendario.json"
        output_file.write_text(
            json.dumps(room_record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        event_count = len(payload) if isinstance(payload, list) else "?"
        print(f"  Eventi restituiti: {event_count}")

    combined_file = OUTPUT_DIR / "occupazioni_sale_povo_raw.json"
    combined_file.write_text(
        json.dumps(combined, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Dati salvati in {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
