# SWIFT-ION v2.1.2 – foF2 欠測緩和・品質区分パッチ

## 対象

`SWIFT-ION` v2.1 + v2.1.1（NICT 96h 横軸表示）を導入済みのリポジトリに適用してください。
SWIFT-TEC 原本は変更しません。`pages.yml` / GitHub Actions のステップ順や既存の365日履歴ブランチは変更しません。

## インストール（GitHub Desktop）

1. ZIP を解凍します。
2. `.github` は含まれません。解凍した `scripts/`, `docs/`, `tests/` を SWIFT-ION リポジトリ直下に上書きしてください。**既存フォルダを削除しないこと**。
3. `git diff` に `scripts/build_ion_forecast.py`, `scripts/build_tec_skill.py`, `scripts/build_fof2_stage_skill.py`, `scripts/train_fof2_calibration.py`, `docs/nict_compare.html`, `docs/year.html`, `docs/shared/fof2-window-diagnostics.mjs` および新しい tests があることを確認します。
4. GitHub Desktop で Commit → Push。新たに走る `Build and publish SWIFT-ION` が成功することを確認してください。
5. `https://sgsy4c2zh7-tech.github.io/SWIFT-ION/nict_compare.html` を更新し、「通常」「低信頼・拡張」の参考件数を確認します。`year.html` ではスコア母数の区分を確認できます。

## なぜ途切れたか

もともと TEC-linked foF2 は、SWIFT-TEC 全 VTEC / IRI(100–2000 km)部分TEC = R について `0.5 <= R <= 2.0` の場合だけ計算されていました。また高度2000km付近のIRI電子密度がピークの10%を超える場合も棄却しました。したがって VTEC自体が存在しても夜間や低緯度で大量の空欄となりました。

## v2.1.2 の処理

- **STANDARD**（元の許容条件を満たす）: 元と全く同じ値 `R` を採用します。学習済み経験/AI補正を従来どおり適用できます。
- **EXTENDED**（入力VTECとIRIが存在するが厳密な比率/上端条件外）: 値を欠損にせず、物理的精度を保証しない**低信頼の参考感度推定**として出します。経験/AI補正は禁止です。
- **MISSING**（元のVTECが欠測、F2ピークが得られない等）: 今回も欠測です。IRIで埋めたり、0で埋めたりしません。

`EXTENDED` に適用する「滑らかな制限付き比率」：

```
R = VTEC_SWIFT / TEC_IRI_100_2000
if R < 0.5:
    R_used = 0.35 + 0.15 * exp(-(0.5-R)/0.15)
elif R <= 2.0:
    R_used = R
else:
    R_used = 2.0 + 0.5 * (1-exp(-(R-2.0)/0.5))
foF2_physics = foF2_IRI * sqrt(R_used)
```

**これは検証済みの新しい物理則ではなく、表示とモデル感度比較のための保守的な外挿処理**です。上端プロファイルが十分収束しない場合も、EXTENDEDのまま参考値と明示されます。滑らかさや空欄減少自体は予報精度の改善を証明しません。

`docs/ion_forecast.json` に追加のフィールド：`fof2_quality`, `fof2_strict_mhz`, `fof2_strict_failure`, `fof2_raw_vtec_ratio`。旧フィールド名・JSON schema は変更していません。`metadata.fof2_quality_counts` で内訳が分かります。

## 365日精度検証と学習の扱い

- これまでと同じ `swift-ion-history`、発表日時/観測日時の照合を使います。
- 経験/AI補正の学習は **STANDARD** の過去観測照合ペアのみ。**EXTENDED は学習対象外**。
- 365日「正式な主表示の的中率」は STANDARD のみを従来どおり比較します。
- EXTENDED の参考的中率は **別集計** として `docs/tec_skill.json` / `docs/fof2_stage_skill.json`、日別・月別CSVに記録します。`year.html` に通常/拡張の件数を表示します。
- 過去の予報を再計算して新たな事前予報と偽ることはしません。

## 安全性／注意

- モデルには同じ積分範囲ではない VTEC と IRI 部分 TEC の比較に起因する不確かさがあります。EXTENDED は観測済み値でも、本来の電離圏の鉛直復元でもありません。
- `fof2_physics_mhz` / `fof2_tec_mhz` に EXTENDED が入っても、AIは適用されず、`fof2_quality` で区別できます。
- 96時間（前日側24時間+3日間）表示は保持。元の241フレームは学習履歴のため変更しません。
- 本番データのVTEC値・IRI値の範囲によっては欠測が残ります。正常かどうかは再デプロイ後の予報JSONを確認してください。

## ローカル検査

- Python `unittest` 20件成功（v2.1の3段階テスト10件 + 追加10件）
- Node.js の JS 診断テスト2件成功
- HTML インラインJavaScript とモジュールの構文検査成功
- 合成入力での2フレーム予報生成と品質フラグ／学習除外／通常スコア分離を検証
- GitHub Actions本番の実行・公開は未検証
