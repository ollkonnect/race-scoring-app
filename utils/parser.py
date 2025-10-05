import csv
import pandas as pd
from typing import List, Dict
import io

def make_unique_columns(columns: list[str]) -> list[str]:
    seen = {}
    unique = []
    for col in columns:
        col = col.strip()
        if col not in seen:
            seen[col] = 1
            unique.append(col)
        else:
            seen[col] += 1
            unique.append(f"{col}_{seen[col]}")
    return unique

def parse_csv_blocks(file) -> List[Dict[str, pd.DataFrame]]:
    # ファイル内容を文字列として読み込む（Shift_JIS対応）
    content = file.read().decode("cp932")
    reader = csv.reader(io.StringIO(content))

    rows = list(reader)
    blocks = []
    i = 0
    while i < len(rows):
        # レース情報（2行）
        if i + 1 >= len(rows):
            break
        race_info_raw = rows[i:i+2]
        i += 2

        # 出走馬ヘッダー（1行）
        if i >= len(rows):
            break
        horse_header = rows[i]
        i += 1

        # 出走馬データ（次のレース情報まで）
        horse_rows = []
        while i < len(rows):
            row = rows[i]
            if len(row) == 10 and any(keyword in row for keyword in ["年", "場所", "R", "クラス名"]):
                break  # 次のレース情報の開始
            horse_rows.append(row)
            i += 1

        if not horse_rows:
            continue

        # DataFrame化（重複カラム名をユニーク化）
        race_info = pd.DataFrame(race_info_raw[1:], columns=race_info_raw[0])
        horse_info = pd.DataFrame(horse_rows, columns=make_unique_columns(horse_header))

        blocks.append({
            "race_info": race_info.reset_index(drop=True),
            "horse_info": horse_info.reset_index(drop=True)
        })

    return blocks