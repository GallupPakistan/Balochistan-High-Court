"""
BHC Cause List PDF Extractor (v2)
Parses every PDF under a downloads folder using word-position (column-aware)
extraction and appends rows into the existing combined Excel file, matching
its schema exactly:

Category | Source File | Page | Institution | Seat/Location | Cause List No |
Bench Type | Date | Court Room | Judges | Section | S.No | Case No | Case Type |
Case ID | Old/Ref No | Petitioner | Respondent | Advocate | CMAs

Usage:
    pip install pdfplumber openpyxl pandas
    python bhc_pdf_extractor.py
"""

import os
import re
import pdfplumber
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOWNLOADS_DIR = os.path.join(REPO_ROOT, "downloads")
EXISTING_FILE = os.path.join(REPO_ROOT, "data", "BHC_Final_File__-_Combined.xlsx")
OUTPUT_FILE = EXISTING_FILE  # update the same file in place

COL_SPLIT_X = 200

FOLDER_TO_SHEET = {
    "principal_seat_quetta": ("Principal Seat Quetta", "High Court (Regular)"),
    "sibi_bench": ("Sibi Bench", "SIBI BENCH"),
    "turbat_bench": ("Turbat Bench", "TURBAT BENCH"),
    "loralai_bench": ("Loralai Bench", "LORALAI BENCH"),
    "khuzdar_bench": ("Khuzdar Bench", "KHUZDAR BENCH"),
    "services_tribunal": ("Services Tribunal", "SERVICES TRIBUNAL"),
    "customs_tribunal": ("Customs Tribunal", "CUSTOMS TRIBUNAL"),
    "election_tribunal": ("Election Tribunal", "ELECTION TRIBUNAL"),
}

COLUMNS = ["Category", "Source File", "Page", "Institution", "Seat/Location",
           "Cause List No", "Bench Type", "Date", "Court Room", "Judges",
           "Section", "S.No", "Case No", "Case Type", "Case ID", "Old/Ref No",
           "Petitioner", "Respondent", "Advocate", "CMAs"]

SECTION_RE = re.compile(r"^FOR\s+[A-Z .]+$")
SNO_CASE_RE = re.compile(r"^(\d+)\s+(.+)$")
NEW_CASE_LEFT_RE = re.compile(r"^\d{1,4}\s+([A-Za-z]{1,6}[-/]|CMA\b)")


def group_rows(words, tol=4):
    rows = []
    for w in sorted(words, key=lambda w: w["top"]):
        placed = False
        for r in rows:
            if abs(r["top"] - w["top"]) <= tol:
                r["words"].append(w)
                r["top"] = (r["top"] + w["top"]) / 2
                placed = True
                break
        if not placed:
            rows.append({"top": w["top"], "words": [w]})
    rows.sort(key=lambda r: r["top"])
    for r in rows:
        r["words"].sort(key=lambda w: w["x0"])
        r["text"] = " ".join(w["text"] for w in r["words"])
    return rows


def parse_pdf(path, bench_folder):
    category, institution = FOLDER_TO_SHEET.get(bench_folder, (bench_folder, bench_folder.upper()))
    fname = os.path.basename(path)
    out_rows = []

    try:
        with pdfplumber.open(path) as pdf:
            for pageno, page in enumerate(pdf.pages, start=1):
                words = page.extract_words()
                table_objs = page.find_tables() or []
                cma_texts = []
                for t in table_objs:
                    tdata = t.extract() or []
                    for trow in tdata:
                        if trow and trow[0] and "CMA" in str(trow[0]).upper():
                            cma_texts.append(" ".join(str(c) for c in trow[1:] if c))

                # drop words that fall inside a detected table's bbox so table text
                # (like the CMAs row) never leaks into the case column parsing
                def in_any_table(w):
                    for t in table_objs:
                        x0, top, x1, bottom = t.bbox
                        if x0 - 1 <= w["x0"] and w["x1"] <= x1 + 1 and top - 1 <= w["top"] and w["bottom"] <= bottom + 1:
                            return True
                    return False

                words = [w for w in words if not in_any_table(w)]
                rows = group_rows(words)

                header_rows, body_rows = [], []
                seen_section = False
                for r in rows:
                    if SECTION_RE.match(r["text"].strip()):
                        seen_section = True
                    (body_rows if seen_section else header_rows).append(r)

                header_text = "\n".join(r["text"] for r in header_rows)
                cln_m = re.search(r"Cause List No\.?\s*(\d+)\s*at\s*(.+)", header_text)
                cause_list_no = cln_m.group(1) if cln_m else ""
                seat_location = cln_m.group(2).strip() if cln_m else ""
                bt_m = re.search(r"For\s+(.+?)\s+dated\s+(.+)", header_text)
                bench_type = bt_m.group(1).strip() if bt_m else ""
                hearing_date = bt_m.group(2).strip() if bt_m else ""

                judge_words, room_num = [], ""
                past_dated_line = False
                for r in header_rows:
                    if bt_m and "dated" in r["text"]:
                        past_dated_line = True
                        continue
                    if not past_dated_line:
                        continue
                    left = [w["text"] for w in r["words"] if w["x0"] < 480]
                    right = [w["text"] for w in r["words"] if w["x0"] >= 480]
                    left_txt = " ".join(left).strip()
                    if left_txt and left_txt not in ("Before :", "Before", ":"):
                        left_txt = re.sub(r"^Before\s*:\s*", "", left_txt)
                        if left_txt:
                            judge_words.append(left_txt)
                    right_txt = " ".join(right)
                    rm = re.search(r"(\d+)$", right_txt)
                    if ("Room" in right_txt or "No" in right_txt) and rm:
                        room_num = rm.group(1)
                judges = " ".join(judge_words)
                judges = re.sub(r"HON'BLE\s+JUSTICE\s*", "", judges).strip()
                judges = re.sub(r"\s*&\s*", " & ", judges)
                judges = re.sub(r"\s+", " ", judges)

                current_section = ""
                case = None

                def flush(case):
                    if case is None:
                        return
                    left_txt = " ".join(case["left"]).strip()
                    right_lines = case["right"]
                    advocate = right_lines[-1].strip() if right_lines else ""
                    pr_text = " ".join(right_lines[:-1]).strip() if len(right_lines) > 1 else ""
                    if " vs " in pr_text:
                        petitioner, respondent = pr_text.split(" vs ", 1)
                    elif not pr_text and right_lines:
                        petitioner, respondent = right_lines[0], ""
                    else:
                        petitioner, respondent = pr_text, ""

                    m = SNO_CASE_RE.match(left_txt)
                    sno, rest = (m.group(1), m.group(2)) if m else ("", left_txt)
                    case_id_m = re.search(r"\b(\d{9,})\b", rest)
                    case_id = case_id_m.group(1) if case_id_m else ""
                    rest_wo_id = rest.replace(case_id, "").strip() if case_id else rest
                    parts = rest_wo_id.split(None, 1)
                    case_no = parts[0] if parts else ""
                    case_type = parts[1] if len(parts) > 1 else ""

                    out_rows.append({
                        "Category": category, "Source File": fname, "Page": pageno,
                        "Institution": institution, "Seat/Location": seat_location,
                        "Cause List No": cause_list_no, "Bench Type": bench_type,
                        "Date": hearing_date, "Court Room": room_num, "Judges": judges,
                        "Section": current_section, "S.No": sno, "Case No": case_no,
                        "Case Type": case_type, "Case ID": case_id, "Old/Ref No": "",
                        "Petitioner": petitioner.strip(), "Respondent": respondent.strip(),
                        "Advocate": advocate, "CMAs": "",
                    })

                for r in body_rows:
                    txt = r["text"].strip()
                    if SECTION_RE.match(txt):
                        flush(case)
                        case = None
                        current_section = txt
                        continue
                    left = " ".join(w["text"] for w in r["words"] if w["x0"] < COL_SPLIT_X).strip()
                    right = " ".join(w["text"] for w in r["words"] if w["x0"] >= COL_SPLIT_X).strip()
                    if left and NEW_CASE_LEFT_RE.match(left + " "):
                        flush(case)
                        case = {"left": [left], "right": [right] if right else []}
                    elif case is not None:
                        if left:
                            case["left"].append(left)
                        if right:
                            case["right"].append(right)
                flush(case)

                page_case_rows = [r for r in out_rows if r["Source File"] == fname and r["Page"] == pageno]
                n_cases = len(page_case_rows)
                n_cmas = len(cma_texts)
                for i, cma in enumerate(cma_texts):
                    idx = n_cases - (n_cmas - i)
                    if 0 <= idx < n_cases:
                        page_case_rows[idx]["CMAs"] = "CMAs " + cma
                    elif n_cases:
                        page_case_rows[-1]["CMAs"] = (page_case_rows[-1]["CMAs"] + " | CMAs " + cma).strip(" |")

    except Exception as e:
        row = {c: "" for c in COLUMNS}
        row["Category"] = category
        row["Source File"] = fname
        row["Petitioner"] = f"ERROR: {e}"
        out_rows.append(row)

    return out_rows


def main():
    all_new = {sheet: [] for sheet, _ in FOLDER_TO_SHEET.values()}

    for bench_folder in sorted(os.listdir(DOWNLOADS_DIR)):
        bench_path = os.path.join(DOWNLOADS_DIR, bench_folder)
        if not os.path.isdir(bench_path):
            continue
        sheet_info = None
        for fk, (sheet, inst) in FOLDER_TO_SHEET.items():
            if bench_folder.startswith(fk):
                sheet_info = (fk, sheet)
                break
        if not sheet_info:
            print(f"Skipping unrecognized folder: {bench_folder}")
            continue
        fk, sheet = sheet_info

        for fname in sorted(os.listdir(bench_path)):
            if not fname.lower().endswith(".pdf"):
                continue
            fpath = os.path.join(bench_path, fname)
            rows = parse_pdf(fpath, fk)
            all_new[sheet].extend(rows)
            print(f"Parsed: {bench_folder}/{fname} -> {len(rows)} row(s)")

    if os.path.exists(EXISTING_FILE):
        existing = pd.read_excel(EXISTING_FILE, sheet_name=None)
    else:
        existing = {sheet: pd.DataFrame(columns=COLUMNS) for _, (sheet, _) in FOLDER_TO_SHEET.items()}

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        for _, (sheet, _inst) in FOLDER_TO_SHEET.items():
            old_df = existing.get(sheet, pd.DataFrame(columns=COLUMNS))
            new_df = pd.DataFrame(all_new.get(sheet, []), columns=COLUMNS)
            if not new_df.empty and "Source File" in old_df.columns:
                already = set(old_df["Source File"])
                new_df = new_df[~new_df["Source File"].isin(already)]
            combined = pd.concat([old_df, new_df], ignore_index=True)
            combined.to_excel(writer, sheet_name=sheet, index=False)
            print(f"{sheet}: {len(old_df)} existing + {len(new_df)} new = {len(combined)} rows")

    print(f"\nSaved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()