# race-scoring-app

Python の自主学習の一環として **個人開発** した、CSV から過去成績を読み込み **ルールに基づいて数値化**し、Web と **PDF で出力**するミニアプリです。  
集計・スコアリング・帳票出力という汎用パターンを押さえているため、今回の題材に限らず **ビジネス／プライベート両方に転用可能** な構成を意識しています。

> デモ（Streamlit Cloud）：[https://race-scoring-app.streamlit.app/](https://race-scoring-app.streamlit.app/)  
> ※ 公開設定や URL は運用に応じて変更される場合があります。

---

## ✨ 何ができるか

- **CSV 読み込み**：レース・出走馬の情報を取り込む  
- **スコアリング**：設定ファイル（JSON）とクラス表（CSV）を用いて、過去走の各指標を点数化  
- **可視化**：表形式で 2 段ヘッダー（◯走前の合計／内訳）表示  
- **PDF 出力**：ReportLab で帳票を生成（グループ境界の強調・合計スコア列のハイライト）

---

## 🧩 仕組み（転用ポイント）

- **入力**：`/config` のルール、`/data` のマスター、任意の CSV  
- **処理**：`utils/` に集約（パーサー・スコアラーを分離）  
  → ルールや指標を差し替えるだけで他ドメインにも転用しやすい構造  
- **出力**：Streamlit でインタラクティブ表示、ReportLab で **PDF** を生成  
  → 「見る／配る」を両立

> 例：セールス実績の採点、アンケートのスコア化、トレーニング記録の可視化などに横展開できます。

---

## ▶️ ローカル実行

- **要件**：Python 3.10–3.11 で動作確認  
- **依存**：`requirements.txt` を使用

```bash
# 1) （任意）仮想環境
python -m venv .venv
# Windows
. .venv/Scripts/activate

# 2) 依存インストール
pip install -r requirements.txt

# 3) 起動
streamlit run app.py
````

---

## 📦 ディレクトリ

```
.
├─ app.py                 # Streamlit UI / PDF 出力
├─ utils/
│   ├─ parser.py          # CSV 解析
│   └─ scorer.py          # ルールに基づくスコアリング
├─ config/
│   └─ scoring_rules.json # 指標と配点の定義
├─ data/
│   └─ class_master.csv   # クラス順位マスター
├─ requirements.txt
└─ packages.txt (任意)    # 追加 Linux パッケージ（例：fonts-noto-cjk）
```

---

## 🔧 技術スタック

* Python / pandas / Streamlit / ReportLab
* （オプション）streamlit-aggrid

---

## 📝 ライセンス / 利用

* コードの再利用可否はリポジトリのライセンス設定に従います。
* データ（CSV 等）は権利に注意してご利用ください。

---

## フィードバックについて

このリポジトリは **No license（無許諾）** 方針です。
コードの再利用・配布・改変は原則として許可していませんが、**フィードバックは歓迎**します。

* ご質問・不具合報告・改善提案は **Issues** にてお知らせください。
* **Pull Request** は原則クローズ前提ですが、軽微な修正や文言調整は検討します。まずは **Issue で事前相談** をお願いします。
* 大きな変更提案は、設計意図との整合や保守性の観点からお断りする場合があります。ご了承ください。

---

## 🙌 作者

* **ollkonnect**（`@ollkonnect`）

