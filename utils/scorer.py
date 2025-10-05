import pandas as pd
import json

def load_scoring_rules(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_class_rank(path: str) -> dict:
    df = pd.read_csv(path)
    return dict(zip(df["クラス名"], df["ランク"]))

def compare_class(current: str, next_: str, class_rank: dict) -> str:
    cur_rank = class_rank.get(str(current).strip(), 0)
    next_rank = class_rank.get(str(next_).strip(), 0)

    if cur_rank >= next_rank:
        return "同格以上"
    elif cur_rank < next_rank:
        return "格下"
    return "不明"

def score_horse_row(row: pd.Series, rules: dict, next_class: str, class_rank: dict) -> int:
    score = 0

    # 補正タイム
    try:
        time = float(row.get("補正タイム", 0))
        score += time * rules["補正タイム"]["scale"]
    except:
        pass

    # -3F差と4
    try:
        diff = float(row.get("-3F差", ""))
        four = row.get("4", "")
        four = int(four) if str(four).isdigit() else None
        for cond in rules["-3F差と4"]:
            if cond["range"][0] <= diff <= cond["range"][1]:
                if "4" not in cond or four in cond["4"] or (None in cond["4"] and four is None):
                    score += cond["score"]
                    break
    except:
        pass

    # 上3F順位
    try:
        rank = int(row.get("上3F順位", 0))
        score += rules["上3F順位"].get(str(rank), 0)
    except:
        pass

    # 着差とクラス比較
    try:
        diff = float(row.get("着差", ""))
        current_class = row.get("クラス", "")
        comparison = compare_class(current_class, next_class, class_rank)

        if comparison == "同格以上":
            if diff <= 0.3:
                score += rules["着差とクラス"]["同クラス"]["<=0.3"]
            elif 0.4 <= diff <= 0.5:
                score += rules["着差とクラス"]["同クラス"]["0.4-0.5"]
        elif comparison == "格下":
            if diff <= -0.3:
                score += rules["着差とクラス"]["格下"]["<=-0.3"]
            elif -0.2 <= diff <= 0:
                score += rules["着差とクラス"]["格下"]["-0.2-0"]
    except:
        pass

    return float(score)

def score_horse_info(horse_info: pd.DataFrame, rules: dict, next_class: str, class_rank: dict) -> pd.DataFrame:
    scored = horse_info.copy()
    scored["スコア"] = scored.apply(lambda row: score_horse_row(row, rules, next_class, class_rank), axis=1)
    return scored