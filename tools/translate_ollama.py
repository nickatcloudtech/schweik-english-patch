#!/usr/bin/env python3
"""Translate schweik_dialogue.csv via local Ollama, preserving Hašek deadpan style."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "translation" / "schweik_dialogue.csv"
DEFAULT_OUTPUT = ROOT / "translation" / "schweik_dialogue.csv"
DEFAULT_MODEL = "qwen3.5-32k:latest"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"

BATCH_SIZE = 6
LOW_PRIORITY_LOCATIONS = {"ВРЕМЕННЫЕ", "темы диалогов", "Общие", "Любой перс"}

LOCATION_GLOSS = {
    "Трактир У чаши": "The Chalice pub",
    "Квартира Лукаша": "Lieutenant Lukáš's flat",
    "Кухня Швейка": "Švejk's kitchen",
    "Гостиная Каца": "Chaplain Katz's parlour",
    "Парк": "the park",
    "Госпиталь палата": "military hospital ward",
    "Кабинет следователя": "the interrogator's office",
    "Психушка коридор": "madhouse corridor",
    "Палата": "the ward",
    "Площадь": "the town square",
    "Часовня": "the garrison chapel",
    "Камера": "the jail cell",
    "Вход в психушку": "madhouse entrance",
    "Процедурная": "the treatment room",
    "Комната Швейка": "Švejk's room",
    "Вокзал": "the railway station",
    "Комиссариат": "the police commissariat",
    "Комната ПМ": "Mrs Müller's room",
    "Кабинет главврача": "the head doctor's office",
}

VOICE_GUIDE = """You are translating dialogue for a point-and-click adventure game adapted from Jaroslav Hašek's satirical novel "The Good Soldier Švejk" (Prague, 1914, on the eve of the Great War, under the Austro-Hungarian empire).

Translate each Russian line into English. Your single most important job is to PRESERVE THE HUMOR AND SATIRE. Hašek's comedy works through:
- Deadpan earnestness: Švejk says absurd things with total sincerity. Never wink at the joke.
- Mock-official politeness: bureaucratic and military registers used for trivial matters.
- Rambling pub anecdotes: "I knew a fellow once in Vršovice who..." — keep the meandering, gossipy cadence.
- Cheerful fatalism and absurd logic delivered as plain common sense.
- Understatement, not exaggeration. The humor is dry.

Style rules:
- Period voice, ~1914. NO modern slang or anachronisms ("okay", "guy", "cool" are forbidden). Prefer "fellow", "chap", "a man I knew", "beg to report".
- Švejk's signature phrase "Осмелюсь доложить" → "Humbly report, sir" (or "Humbly report" mid-sentence).
- Names use the standard English-edition conventions: Švejk, Mrs Müller (Пани Мюллерова), Palivec, Chaplain Katz, Lieutenant Lukáš, Bretschneider, Hradčany, Vršovice, The Chalice (У чаши).
- Keep translations roughly the same length as the original (game UI constraint). Match the original's punctuation feel: keep ellipses, exclamations, question marks.
- Short UI-ish lines (e.g. examine-object barks like "A candle. It burns.") stay terse and flat — the flatness IS the joke.
- Natural spoken English; contractions are fine and encouraged in dialogue.

Examples of the target register:
RU: "Свечка и свечка. На этой неделе уже три таких ушло."
EN: "A candle's a candle. Three of them gone this week already."
RU: "Вообще днем свечки не жгут. Надо придумать, как оправдать такое расточительство."
EN: "Nobody burns candles in the daytime. I'll have to think up some way to justify that kind of extravagance."

You will receive a JSON array of lines: [{"i": rowNumber, "c": "speaker", "t": "Russian text"}]. The scene location is given separately.
Respond with ONLY a JSON object, no markdown fences, no commentary:
{"t":[{"i":rowNumber,"en":"English translation"}, ...]}
Every input line must appear exactly once in the output."""


def clean_field(value: str) -> str:
    return (value or "").replace("\0", "").strip()


def load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = [{k: clean_field(v) for k, v in row.items()} for row in reader]
    if "russian" not in fields or "english" not in fields:
        raise ValueError("CSV must include 'russian' and 'english' columns")
    return fields, rows


def save_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def extract_json(text: str) -> dict:
    clean = re.sub(r"```json|```", "", text, flags=re.IGNORECASE).strip()
    start = clean.find("{")
    end = clean.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object in model response")
    return json.loads(clean[start : end + 1])


def ollama_chat(
    *,
    base_url: str,
    model: str,
    user_message: str,
    temperature: float,
    timeout: int,
) -> str:
    payload = {
        "model": model,
        "think": False,
        "messages": [
            {"role": "system", "content": VOICE_GUIDE},
            {"role": "user", "content": user_message},
        ],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": temperature,
            "num_predict": 1200,
        },
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    message = data.get("message") or {}
    content = (message.get("content") or "").strip()
    if content:
        return content
    thinking = (message.get("thinking") or "").strip()
    if thinking:
        raise ValueError(
            "Model returned empty content (thinking-only response). "
            "Use a Qwen3 model with think disabled, or pass --model with think support."
        )
    return ""


def build_batches(rows: list[dict[str, str]], batch_size: int) -> list[tuple[str, list[tuple[int, dict[str, str]]]]]:
    pending: list[tuple[int, dict[str, str]]] = []
    for index, row in enumerate(rows):
        if row.get("russian") and not row.get("english"):
            pending.append((index, row))

    by_location: dict[str, list[tuple[int, dict[str, str]]]] = defaultdict(list)
    for item in pending:
        by_location[item[1].get("location", "")].append(item)

    def location_sort_key(location: str) -> tuple[int, str]:
        return (1 if location in LOW_PRIORITY_LOCATIONS else 0, location)

    batches: list[tuple[str, list[tuple[int, dict[str, str]]]]] = []
    for location in sorted(by_location, key=location_sort_key):
        items = by_location[location]
        for offset in range(0, len(items), batch_size):
            batches.append((location, items[offset : offset + batch_size]))
    return batches


def translate_batch(
    *,
    batch: list[tuple[int, dict[str, str]]],
    location: str,
    base_url: str,
    model: str,
    temperature: float,
    timeout: int,
    retries: int,
) -> dict[int, str]:
    gloss = LOCATION_GLOSS.get(location, location or "unspecified")
    payload = [
        {"i": index, "c": row.get("character", ""), "t": row["russian"]}
        for index, row in batch
    ]
    user_message = (
        f"Scene location: {gloss}\n\nLines to translate:\n{json.dumps(payload, ensure_ascii=False)}"
    )

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            text = ollama_chat(
                base_url=base_url,
                model=model,
                user_message=user_message,
                temperature=temperature,
                timeout=timeout,
            )
            parsed = extract_json(text)
            result: dict[int, str] = {}
            for item in parsed.get("t", []):
                if isinstance(item.get("i"), int) and isinstance(item.get("en"), str):
                    result[item["i"]] = item["en"].strip()
            if len(result) != len(batch):
                raise ValueError(
                    f"Expected {len(batch)} translations, got {len(result)}"
                )
            return result
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(attempt * attempt)
    raise RuntimeError(f"Batch failed after {retries} attempts: {last_error}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--temperature", type=float, default=0.35)
    parser.add_argument("--timeout", type=int, default=600, help="Seconds per batch request")
    parser.add_argument("--retries", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0, help="Translate at most N pending lines (0 = all)")
    parser.add_argument("--dry-run", action="store_true", help="Show pending batches without calling Ollama")
    args = parser.parse_args()

    fields, rows = load_csv(args.input)
    batches = build_batches(rows, max(1, args.batch_size))
    pending_total = sum(len(batch) for _, batch in batches)

    if pending_total == 0:
        print("Nothing to translate — every row already has english text.")
        return 0

    if args.limit > 0:
        trimmed: list[tuple[str, list[tuple[int, dict[str, str]]]]] = []
        remaining = args.limit
        for location, batch in batches:
            if remaining <= 0:
                break
            trimmed.append((location, batch[:remaining]))
            remaining -= len(batch[:remaining])
        batches = trimmed
        pending_total = sum(len(batch) for _, batch in batches)

    print(f"Model: {args.model}")
    print(f"Pending lines this run: {pending_total}")
    print(f"Batches: {len(batches)} (size ≤ {args.batch_size})")

    if args.dry_run:
        for location, batch in batches[:5]:
            gloss = LOCATION_GLOSS.get(location, location or "unspecified")
            print(f"  - {gloss}: {len(batch)} lines")
        if len(batches) > 5:
            print(f"  ... and {len(batches) - 5} more batches")
        return 0

    translated = 0
    failed_batches = 0
    started = time.time()

    for batch_number, (location, batch) in enumerate(batches, start=1):
        gloss = LOCATION_GLOSS.get(location, location or "unspecified")
        print(
            f"[{batch_number}/{len(batches)}] Translating {len(batch)} lines in {gloss}…",
            flush=True,
        )
        try:
            mapping = translate_batch(
                batch=batch,
                location=location,
                base_url=args.ollama_url,
                model=args.model,
                temperature=args.temperature,
                retries=args.retries,
                timeout=args.timeout,
            )
        except RuntimeError as exc:
            failed_batches += 1
            print(f"[{batch_number}/{len(batches)}] FAILED {gloss}: {exc}", file=sys.stderr)
            continue

        for index, _row in batch:
            rows[index]["english"] = mapping[index]
            translated += 1

        save_csv(args.output, fields, rows)
        elapsed = max(time.time() - started, 0.001)
        rate = translated / elapsed * 60
        print(
            f"[{batch_number}/{len(batches)}] {gloss}: "
            f"{len(batch)} lines ({translated}/{pending_total}, ~{rate:.1f} lines/min)"
        )

    print(f"Done. Translated {translated} lines.")
    if failed_batches:
        print(f"{failed_batches} batch(es) failed — re-run to retry only missing lines.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())