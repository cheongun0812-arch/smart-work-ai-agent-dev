from __future__ import annotations

import os
import re
from typing import Any


def _decode_text_bytes(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "cp949", "euc-kr", "utf-8"):
        try:
            decoded = raw.decode(encoding)
            if decoded:
                return decoded
        except Exception:
            continue
    return ""


def _extract_number(value: Any):
    if value is None:
        return None
    text = str(value).strip()
    if not text or text == "-----":
        return None
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def parse_waton_ibex(raw: bytes, filename: str = "") -> dict:
    """Parse the confirmed WATON IBEX tab-delimited text export (.xls extension).

    Safety rules:
    - Recognize only the confirmed 'IBEX Impedance Data' layout.
    - Auto-candidate only complete 24-cell segments.
    - Require each voltage to be within 0.1..20 V.
    - Never infer missing measurements or silently convert invalid rows.
    """
    decoded = _decode_text_bytes(raw)
    if not decoded:
        return {"recognized": False, "ok": False, "message": "파일을 텍스트로 읽지 못했습니다."}

    normalized = decoded.lower()
    if "ibex impedance data" not in normalized or "\tbank 1" not in normalized:
        return {"recognized": False, "ok": False, "message": "현재 확인된 WATON IBEX 원본 형식이 아닙니다."}

    lines = decoded.splitlines()
    export_time = ""
    for line in lines[:10]:
        m = re.search(r"\bTime\s+(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})", line, re.I)
        if m:
            export_time = m.group(1)
            break

    metric_header_idx = None
    for idx, line in enumerate(lines[:80]):
        parts = [p.strip().lower() for p in line.split("\t") if p.strip()]
        if "impe" in parts and "volt" in parts:
            metric_header_idx = idx
            break

    if metric_header_idx is None:
        return {
            "recognized": True,
            "ok": False,
            "message": "WATON 형식은 확인했지만 Impe/Volt/Temp 헤더를 찾지 못했습니다.",
        }

    metric_parts = lines[metric_header_idx].split("\t")
    bank_count = max(0, (len(metric_parts) - 1) // 3)
    if bank_count <= 0:
        return {"recognized": True, "ok": False, "message": "Bank 열 구조를 확인하지 못했습니다."}

    bank_names: dict[int, str] = {}
    for line in lines[:metric_header_idx]:
        parts = line.split("\t")
        if parts and parts[0].strip().upper() == "NAME":
            for bank_no in range(1, bank_count + 1):
                col = 1 + (bank_no - 1) * 3
                name = parts[col].strip() if col < len(parts) else ""
                bank_names[bank_no] = name or f"BANK_{bank_no:02d}"
            break
    for bank_no in range(1, bank_count + 1):
        bank_names.setdefault(bank_no, f"BANK_{bank_no:02d}")

    bank_rows: dict[int, dict[int, dict]] = {i: {} for i in range(1, bank_count + 1)}

    for line in lines[metric_header_idx + 1 :]:
        parts = line.split("\t")
        if not parts:
            continue
        m = re.fullmatch(r"\s*Cell\s+(\d+)\s*", parts[0], re.I)
        if not m:
            continue
        source_cell = int(m.group(1))

        for bank_no in range(1, bank_count + 1):
            base = 1 + (bank_no - 1) * 3
            if base >= len(parts):
                continue
            raw_impe = parts[base].strip() if base < len(parts) else ""
            raw_volt = parts[base + 1].strip() if base + 1 < len(parts) else ""
            raw_temp = parts[base + 2].strip() if base + 2 < len(parts) else ""
            if all(v in {"", "-----"} for v in (raw_impe, raw_volt, raw_temp)):
                continue
            bank_rows[bank_no][source_cell] = {
                "source_cell": source_cell,
                "impedance": _extract_number(raw_impe),
                "voltage": _extract_number(raw_volt),
                "temperature": _extract_number(raw_temp),
                "raw_impe": raw_impe,
                "raw_volt": raw_volt,
                "raw_temp": raw_temp,
            }

    candidates: list[dict] = []
    diagnostics: list[dict] = []

    for bank_no, rows in bank_rows.items():
        if not rows:
            continue
        regular_cells = sorted(c for c in rows if 1 <= c <= 600)
        if not regular_cells:
            continue
        max_cell = max(regular_cells)
        max_segment = min((max_cell - 1) // 24 + 1, 25)

        for segment_no in range(1, max_segment + 1):
            start = (segment_no - 1) * 24 + 1
            end = start + 23
            segment_rows = [rows.get(c) for c in range(start, end + 1)]
            present = sum(item is not None for item in segment_rows)
            valid_volt = sum(
                item is not None
                and item.get("voltage") is not None
                and 0.1 <= float(item["voltage"]) <= 20.0
                for item in segment_rows
            )
            if present == 0:
                continue
            diagnostics.append(
                {
                    "bank": bank_no,
                    "bank_name": bank_names[bank_no],
                    "source_start": start,
                    "source_end": end,
                    "present_count": present,
                    "valid_voltage_count": valid_volt,
                }
            )
            if present != 24 or valid_volt != 24:
                continue

            records = []
            for target_cell, source_cell in enumerate(range(start, end + 1), start=1):
                item = rows[source_cell]
                records.append(
                    {
                        "cell": target_cell,
                        "source_cell": source_cell,
                        "voltage": float(item["voltage"]),
                        "impedance": item.get("impedance"),
                        "temperature": item.get("temperature"),
                        "source_bank": bank_no,
                        "source_bank_name": bank_names[bank_no],
                    }
                )

            source_range = f"Cell {start}~{end}"
            label = (
                f"Bank {bank_no} · {source_range} · 24개"
                if start == 1
                else f"Bank {bank_no} · {source_range} → 현재 조 Cell 1~24 · 24개"
            )
            candidates.append(
                {
                    "label": label,
                    "bank": bank_no,
                    "bank_name": bank_names[bank_no],
                    "source_start": start,
                    "source_end": end,
                    "records": records,
                    "impedance_detected": any(r["impedance"] is not None for r in records),
                    "temperature_detected": any(r["temperature"] is not None for r in records),
                }
            )

    observed_banks = sorted(bank for bank, rows in bank_rows.items() if rows)
    incomplete = [
        d for d in diagnostics
        if not (d["present_count"] == 24 and d["valid_voltage_count"] == 24)
    ]

    if not candidates:
        return {
            "recognized": True,
            "ok": False,
            "format": "WATON_TEXT_XLS",
            "export_time": export_time,
            "observed_banks": observed_banks,
            "diagnostics": diagnostics,
            "message": "WATON 원본 형식은 확인했지만 자동 적용 가능한 완전한 24셀 묶음이 없습니다.",
        }

    return {
        "recognized": True,
        "ok": True,
        "format": "WATON_TEXT_XLS",
        "filename": os.path.basename(filename),
        "export_time": export_time,
        "observed_banks": observed_banks,
        "candidates": candidates,
        "diagnostics": diagnostics,
        "incomplete_segments": incomplete,
        "message": f"WATON IBEX 원본 형식을 확인했고 24셀 적용 가능 묶음 {len(candidates)}개를 찾았습니다.",
    }
