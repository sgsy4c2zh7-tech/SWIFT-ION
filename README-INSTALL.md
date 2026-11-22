# SWIFT-ION v2.1.1 — SWIFT-TEC 96h foF2表示と欠測診断

## 変更箇所（2ファイルのみ）

- `docs/nict_compare.html`: 「前日側24時間＋続く3日間（合計96時間）」をグラフ初期表示に設定。IRI単独を画面に重ねず、従来どおりTEC連動foF2を主表示。表示期間内の有効点数・欠測点数・1 MHz縦目盛り・UTC 6時間補助線を維持。Excelの`foF2_Charts`は選択した表示期間に対応し、`Forecast_30min`等の生データは従来どおり241点を保存。
- `docs/shared/fof2-window-diagnostics.mjs`: 予報時刻から最大96時間を選択する機能と、欠測した時刻について「最近傍のIRI計算点に記録された棄却理由」の参考内訳を表示する機能。

ZIP中の`tests/test_fof2_window_diagnostics.mjs`は任意のローカル検査で、GitHub Actionsの既存Pythonテストには影響しません。

## 導入手順

1. ZIPを展開する。
2. `docs/nict_compare.html` および `docs/shared/fof2-window-diagnostics.mjs` を、GitHub Desktopで管理する`SWIFT-ION`の同じ相対パスへコピーする。既存の`nict_compare.html`は上書きする。
3. GitHub DesktopでCommit → Pushする。例： `Show 24h reference and 72h TEC foF2 forecast with missing-data diagnostics`
4. GitHub Pagesの`https://sgsy4c2zh7-tech.github.io/SWIFT-ION/nict_compare.html`を確認する。
5. 「表示期間」では「前日側24h＋3日間（SWIFT-TEC形式）」がデフォルト。全241フレームを見たい場合は「全モデル時刻（参考）」に切り替えられる。

## どこまでが確実か

- 現在のSWIFT-TECは`runForecast()`でNOAAの3日間Kpテキストを取り込み、`rStorm(kpF)`に渡してVTEC予報を計算する。SWIFT-IONはそのVTECにIRI鉛直電子密度を組み合わせてfoF2を推定する。経験/AI段階では別途NOAA予報Kpを説明変数に使える。
- 一方、SWIFT-TECの現行コードは5日間（241フレーム）を生成し、3日間Kpの範囲外では最初/最後の日のKpを延長使用する。NOAA取得・Kp解析が不成立ならKp=3を代用する経路もある。**特定の公開実行で有効なKpが使われたかは、この画面と静的コードだけでは断定できない。** GitHub Actionsの元のSWIFT-TEC計算ログや入力記録で確認する必要がある。
- 初期表示はデータの最初のフレーム時刻から96時間（最初の24時間を前日側の参考領域、続く72時間を3日間側とみなす）。**時刻の区分は表示上の便宜で、予報発表日・NOAA Kpの3日間公表範囲と完全一致することを保証しない。** 前日側を実測として扱わない。
- foF2の欠測は`F=VTEC_SWIFT/TEC_IRI(100–2000km)`が`[0.5,2.0]`外、IRIの高度上端（topside）の条件不成立、VTEC欠損などの品質判定に起因し得る。欠測はそのまま欠測にする。
- 欠測理由の内訳は各観測所の「最も近いモデル格子点」の記録を参考として集計。観測所位置では複数格子点を補間しているため、**特定の欠測の正確な理由を示すものではない**。
- 3段階の物理/経験/AI計算、SWIFT-TEC本体、SWIFT-IONのモデル生成、GitHub Actions、365日履歴はこのパッチでは変更しない。

## 検査

- `node tests/test_fof2_window_diagnostics.mjs` — 241フレーム中の最大96時間選択（193点）、境界、欠測診断の集計を確認。
- `node --check` でJavaScriptモジュールとHTML内スクリプトの構文検査済み。
- GitHub Pages上の本番ブラウザ描画および特定実行のNOAA Kp取得履歴は未確認。
