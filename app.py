import streamlit as st
from utils.parser import parse_csv_blocks
from utils.scorer import load_scoring_rules, load_class_rank, score_horse_row
import pandas as pd
from reportlab.lib.pagesizes import landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import os
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak
import io
import re

# 共通で使うフォント名（表/タイトルの指定に使う）
PDF_FONT_NAME = "HeiseiKakuGo-W5"

def setup_jp_font():
    """WindowsではMSGothic、クラウドでは内蔵CJKフォントを使う。"""
    global PDF_FONT_NAME
    win_font = r"C:\Windows\Fonts\msgothic.ttc"
    if os.path.exists(win_font):
        # TTCなので subfontIndex を付けるのが安全（0でまずOK）
        pdfmetrics.registerFont(TTFont("MSGothic", win_font, subfontIndex=0))
        PDF_FONT_NAME = "MSGothic"
    else:
        # サーバー側はファイルがないので内蔵CIDフォントを使う
        pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
        PDF_FONT_NAME = "HeiseiKakuGo-W5"

setup_jp_font()

def safe_float(val):
    try:
        return float(val)
    except:
        return 0.0

def score_block(block, rules, class_rank):
    race_info = block["race_info"].iloc[0]
    next_class = race_info.get("クラス名", "")
    horse_df = block["horse_info"]
    scored_rows = []

    for _, row in horse_df.iterrows():
        horse_name = row.get("馬名", "不明")
        total_score = 0
        row_scores = {"馬名": horse_name}

        for n in range(1, 6):
            prefix = f"{n}走前" if n > 1 else "1走前"
            suffix = "" if n == 1 else f"_{n}"

            sub_row = pd.Series({
                "補正タイム": row.get(f"補正タイム{suffix}", None),
                "-3F差": row.get(f"-3F差{suffix}", None),
                "4": row.get(f"4{suffix}", None),
                "上3F順位": row.get(f"上3F順位{suffix}", None),
                "着差": row.get(f"着差{suffix}", None),
                "クラス": row.get(f"クラス{suffix}", None),
                "芝・ダ": row.get(f"芝・ダ{suffix}", None)
            })

            s = score_horse_row(sub_row, rules, next_class, class_rank)
            total_score += s

            row_scores[f"{prefix}の合計スコア"] = s
            row_scores[f"{prefix}のタイムスコア"] = safe_float(sub_row.get("補正タイム")) * rules["補正タイム"]["scale"]
            row_scores[f"{prefix}の-3F差スコア"] = 0
            row_scores[f"{prefix}の上3Fスコア"] = rules["上3F順位"].get(str(sub_row.get("上3F順位", "")).strip(), 0)
            row_scores[f"{prefix}の着差スコア"] = 0

            try:
                four = sub_row.get("4", "")
                four = int(four) if str(four).isdigit() else None
                if safe_float(sub_row.get("-3F差")) == 0 and (four is None or "障" in sub_row.get("芝・ダ")):
                    diff = 99.9
                else:
                    diff = safe_float(sub_row.get("-3F差"))
                for cond in rules["-3F差と4"]:
                    if diff == 99.9:
                        row_scores[f"{prefix}の-3F差スコア"] = 0
                    elif cond["range"][0] <= diff <= cond["range"][1]:
                        if "4" not in cond or four in cond["4"] or (None in cond["4"] and four is None):
                            row_scores[f"{prefix}の-3F差スコア"] = cond["score"]
                            break
            except:
                pass

            try:
                diff = safe_float(sub_row.get("着差"))
                current_class = sub_row.get("クラス", "")
                if class_rank.get(str(current_class).strip(), 0) == 0:
                    comparison = "値なし"
                elif class_rank.get(str(current_class).strip(), 0) >= class_rank.get(str(next_class).strip(), 0):
                    comparison = "同格以上"
                elif class_rank.get(str(current_class).strip(), 0) < class_rank.get(str(next_class).strip(), 0):
                    comparison = "格下"

                if comparison == "同格以上":
                    if diff <= 0.3:
                        row_scores[f"{prefix}の着差スコア"] = rules["着差とクラス"]["同クラス"]["<=0.3"]
                    elif 0.4 <= diff <= 0.5:
                        row_scores[f"{prefix}の着差スコア"] = rules["着差とクラス"]["同クラス"]["0.4-0.5"]
                elif comparison == "格下":
                    if diff <= -0.3:
                        row_scores[f"{prefix}の着差スコア"] = rules["着差とクラス"]["格下"]["<=-0.3"]
                    elif -0.2 <= diff <= 0:
                        row_scores[f"{prefix}の着差スコア"] = rules["着差とクラス"]["格下"]["-0.2-0"]
                else:
                    row_scores[f"{prefix}の着差スコア"] = 0
            except:
                pass

        row_scores["過去5走の合計スコア"] = total_score
        scored_rows.append(row_scores)

    scored_df = pd.DataFrame(scored_rows)
    cols = ["馬名", "過去5走の合計スコア"] + [c for c in scored_df.columns if c not in ["馬名", "過去5走の合計スコア"]]
    return scored_df[cols]

# ===== 追加：表示用 MultiIndex 化ユーティリティ =====
def to_multiindex_for_display(df: pd.DataFrame) -> pd.DataFrame:
    """
    フラット列の DataFrame を 2 段ヘッダーに整形して返す。
    上段: 「1走前/2走前/…」  下段: 「タイムスコア/上3Fスコア/…」
    例外: 「馬名」「過去5走の合計スコア」は上段空欄の単独列。
    """
    def split_header(c: str):
        if c in ("馬名", "過去5走の合計スコア"):
            return ("", c)
        m = re.match(r"^(\d+走前)の(.+)$", c)
        if m:
            return (m.group(1), m.group(2))
        # 想定外はそのまま下段に
        return ("", c)

    tuples = [split_header(c) for c in df.columns]
    mi = pd.MultiIndex.from_tuples(tuples)
    out = df.copy()
    out.columns = mi
    # 「馬名」を一番左に固定しやすいように並び替え（任意）
    first_cols = [("", "馬名"), ("", "過去5走の合計スコア")]
    other_cols = [c for c in out.columns if c not in first_cols]
    out = out[first_cols + other_cols]
    return out

def generate_combined_pdf(blocks, rules, class_rank):
    """
    PDFを2段見出し（上段=◯走前の合計スコア、下段=各指標）で出力。
    追加:
      - グループ境界線を太く表示
      - 各グループ内の「合計スコア」列のみ背景色を付与
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=(1700, 500),  # 必要に応じて調整
        rightMargin=12, leftMargin=12, topMargin=14, bottomMargin=14
    )

    elements = []
    styles = getSampleStyleSheet()
    try:
        styles['Title'].fontName = 'PDF_FONT_NAME'
    except Exception:
        pass

    # 並び順の優先度（存在しないものは自動スキップ）
    metric_order = ["合計スコア", "タイムスコア", "-3F差スコア", "上3Fスコア", "着差スコア"]
    run_pat = re.compile(r"^(\d+走前)の(.+)$")

    # 色・線の設定（好みに合わせて変更可）
    SUMMARY_BG = colors.HexColor("#FFF2CC")  # 合計スコア列の背景（薄い黄色）
    GROUP_BORDER_WIDTH = 1.5                 # グループ境界の線太さ
    GROUP_BORDER_COLOR = colors.black

    for i, block in enumerate(blocks):
        race_info = block["race_info"].iloc[0]
        title = f"{race_info.get('場所','')}{race_info.get('R','')}R: {race_info.get('略レース名','')}"
        df = score_block(block, rules, class_rank)  # フラット列のまま

        # --- 列のグルーピング（1走前/2走前… -> 指標） ---
        static_cols = ["馬名", "過去5走の合計スコア"]
        by_run = {}   # run -> [col_name,...]
        for col in df.columns:
            m = run_pat.match(col)
            if m:
                run, metric = m.group(1), m.group(2)
                by_run.setdefault(run, []).append(col)

        def run_key(run_label: str) -> int:
            return int(run_label.replace("走前", ""))

        ordered_groups = []
        for run in sorted(by_run.keys(), key=run_key):
            cols = by_run[run]
            ordered = []
            for k in metric_order:
                ordered += [c for c in cols if c.endswith(k)]
            ordered += [c for c in cols if c not in ordered]
            ordered_groups.append((run, ordered))

        # --- 2段ヘッダー行を構築しつつ、スタイル用の座標も収集 ---
        header_top = ["馬名", "過去5走の合計スコア"]
        header_sub = ["", ""]
        spans = [
            ('SPAN', (0, 0), (0, 1)),  # 馬名 縦結合
            ('SPAN', (1, 0), (1, 1)),  # 過去5走合計 縦結合
        ]

        # グループ境界線と「合計スコア」列のインデックスを記録
        # ※テーブル内座標は (col, row)。ヘッダーは row=0,1、データは row>=2
        group_ranges = []   # (start_col, end_col)
        summary_cols = []   # 各グループ内の「合計スコア」列の col index

        start_col_index = len(header_top)
        ordered_cols = static_cols[:]

        for run, children in ordered_groups:
            width = len(children)
            if width == 0:
                continue
            # 上段（結合）/ 下段（子列名）
            header_top += [f"{run}の合計スコア"] + [""] * (width - 1)
            header_sub += [c.split("の", 1)[1] for c in children]
            spans.append(('SPAN', (start_col_index, 0), (start_col_index + width - 1, 0)))

            # グループの列範囲を記録
            g_start, g_end = start_col_index, start_col_index + width - 1
            group_ranges.append((g_start, g_end))

            # 子列を追加（後でデータ行抽出に使用）
            ordered_cols += children

            # 「◯走前の合計スコア」列のインデックスを特定
            # children 内から末尾が「合計スコア」の列を探し、そのテーブル上のcol番号に変換
            for offset, name in enumerate(children):
                if name.endswith("合計スコア"):
                    summary_cols.append(start_col_index + offset)
                    break  # 1グループにつき1列想定
            start_col_index += width

        # --- データを組み立て ---
        body = df[ordered_cols].round(1).astype(str).values.tolist()
        table_data = [header_top, header_sub] + body

        # --- Table とスタイル ---
        table = Table(table_data, repeatRows=2)

        style_cmds = [
            ('FONTNAME', (0, 0), (-1, -1), 'PDF_FONT_NAME'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            # ヘッダー背景（2行）
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('BACKGROUND', (0, 1), (-1, 1), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            # ベースの罫線
            ('GRID', (0, 0), (-1, -1), 0.25, colors.black),
        ] + spans

        data_row_start = 2
        data_row_end = len(table_data) - 1

        # ① 各グループの境界線を太く（左端/右端にLINEBEFORE/LINEAFTER）
        for (g_start, g_end) in group_ranges:
            # 左境界（グループ開始列の直前）
            style_cmds.append(('LINEBEFORE', (g_start, 0), (g_start, -1), GROUP_BORDER_WIDTH, GROUP_BORDER_COLOR))
            # 右境界（グループ最終列の直後側）
            style_cmds.append(('LINEAFTER', (g_end, 0), (g_end, -1), GROUP_BORDER_WIDTH, GROUP_BORDER_COLOR))

        # ② 各グループ内の「合計スコア」列だけ背景色を付与（データ行全体）
        for col_idx in summary_cols:
            style_cmds.append(('BACKGROUND', (col_idx, data_row_start), (col_idx, data_row_end), SUMMARY_BG))
            style_cmds.append(('TEXTCOLOR', (col_idx, data_row_start), (col_idx, data_row_end), colors.black))
            style_cmds.append(('FONTNAME', (col_idx, data_row_start), (col_idx, data_row_end), 'PDF_FONT_NAME'))
            style_cmds.append(('FONTSIZE', (col_idx, data_row_start), (col_idx, data_row_end), 8))
            # 視認性UPのため、合計スコア列の左右も少し強調（任意）
            style_cmds.append(('LINEBEFORE', (col_idx, data_row_start), (col_idx, data_row_end), 0.75, colors.darkgoldenrod))
            style_cmds.append(('LINEAFTER', (col_idx, data_row_start), (col_idx, data_row_end), 0.75, colors.darkgoldenrod))

        table.setStyle(TableStyle(style_cmds))

        elements.append(Paragraph(title, styles['Title']))
        elements.append(Spacer(1, 10))
        elements.append(table)

        if i < len(blocks) - 1:
            elements.append(PageBreak())

    doc.build(elements)
    buffer.seek(0)
    return buffer

# ページ設定
st.set_page_config(page_title="競走成績スコアリング", layout="wide")
st.title("競走成績スコアリングシステム 🐎")
st.markdown("CSVファイルをアップロードして、各馬の過去成績を数値化します。")

uploaded_file = st.file_uploader("CSVファイルを選択", type=["csv", "xlsx"])

if uploaded_file:
    st.success("ファイルがアップロードされました。")

    try:
        rules = load_scoring_rules("config/scoring_rules.json")
        class_rank = load_class_rank("data/class_master.csv")
        blocks = parse_csv_blocks(uploaded_file)

        if not blocks:
            st.warning("レース情報が見つかりませんでした。CSVの構造をご確認ください。")
        else:
            for block in blocks:
                race_info = block["race_info"].iloc[0]
                place = race_info.get("場所", "")
                race_num = race_info.get("R", "")
                race_name = race_info.get("略レース名", f"レース")
                st.subheader(f"🏇 {place}{race_num}R: {race_name}")

                # スコア（フラット列）
                df = score_block(block, rules, class_rank)

                # 表示用に 2 段ヘッダー化
                view_df = to_multiindex_for_display(df)

                # 表示は MultiIndex、PDF はフラット列を使用
                st.dataframe(view_df, use_container_width=True)

            combined_pdf = generate_combined_pdf(blocks, rules, class_rank)
            st.download_button(
                label="📄 全レースまとめてPDF出力",
                data=combined_pdf,
                file_name="全レーススコアまとめ.pdf",
                mime="application/pdf"
            )

    except Exception as e:
        st.error(f"エラーが発生しました: {e}")
