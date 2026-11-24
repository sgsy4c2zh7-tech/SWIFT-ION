# SWIFT-ION 日本域（SWIFT-TEC / ISEE）404修正版

## 対象症状

Global Time Animation で「日本周辺（SWIFT-TEC / ISEE連動予報）」を選択すると、
「日本域の独立したSWIFT-TEC / ISEE予報が未公開です: 30分格子index HTTP 404」と出る。

2026-11-24 05:47 UTC台のGitHub Actionsログでは、日本域出力ステップが
`SWIFT-TEC ISEE selector missing` で失敗していました。従来のスクリプトは
SWIFT-TECのJS関数の登録を待つ一方、約550ms遅れて生成される
`#swiftV52TecSource` の表示用セレクタは待っていませんでした。
`continue-on-error: true` により、その失敗がPages全体の成功表示に埋もれていました。

## ZIP内の配置先

- `scripts/build_live_japan_swifttec.py`（上書き）
- `scripts/japan_kp_issue.py`（新規追加）
- `.github/workflows/pages.yml`（上書き）
- `tests/test_japan_kp_issue.py`（新規追加）

既存の `docs/animate.html`、`docs/field.html`、GNSS、foF2、全球VTEC予報は変更しません。
`docs/japan_animation` の30分予報はActionsの実行時に自動作成されます。

## 変更の内容

1. セレクタが表示されるまで待機（`wait_for_selector`）。
2. SWIFT-TEC本来の `swiftIseeRunMeanForecast()` を直接実行。
   UIボタン側がエラーを握りつぶす場合にも原因を出力。
3. 同じActions実行で検証済みの24区間NOAA予報Kpを
   `docs/swifttec_kp_issued.json` から読み込み、元のSWIFT-TECのKp系列として提供。
   欠落や不正なKpの代替に観測KpやKp=3を使用しない。
4. 3日間のKp予報期間を超える場合は最後のKpを暫定保持し、メタデータにその旨を表示。
5. `pages.yml` の日本域生成で `continue-on-error` を廃止。
   日本域データ未生成ならビルド失敗として見えるように変更。
6. 最新予報の生成・公開のみを維持。日本域予報の長期蓄積は追加しない。

## 導入方法

1. ZIPを解凍します。
2. 上記4ファイルをSWIFT-IONリポジトリの同じパスにアップロード・上書きします。
3. Commit directly to main branchでコミットします。
4. GitHub Actionsの `Build and publish SWIFT-ION` を確認します。
5. `Export SWIFT-TEC ISEE Japan regional forecast` が成功しているか確認します。
6. GitHub PagesのDeploy成功後、以下のURLを開いて `index.json` が表示されることを確認します。
   https://sgsy4c2zh7-tech.github.io/SWIFT-ION/japan_animation/index.json
7. Global Time Animationで日本域を選択してリロードしてください。

Commit summary:
`Fix Japan ISEE forecast generation and missing index`

## 注意

- 変更前は日本域の生成失敗時でも全球を公開していました。
  今回は日本域生成失敗を明確なActionsエラーにするため、
  **日本域データの生成に失敗すると、その回のPages公開は実施されません。**
  この場合はActionsログを確認してください。既に公開済みのサイトはそのままです。
- 日本域の予報ソースはSWIFT-TECオリジナルのISEE時刻別平均TEC + 予報Kp + 日本域格子AI補正です。
  ISEE観測データそのものや全球VTECの日本域切り出しで代用しません。
- このZIPには公開時の予報データ本体は含めません（生成処理の修正だけです）。
- Kpの3日を超える延長は、実際のNOAA 4日予報ではありません。
- ローカルでPython構文・YAML構文とKp入力検証7件は成功しました。
  実際のupstreamブラウザ＋Actionsを通す公開前統合テストは未実施です。
