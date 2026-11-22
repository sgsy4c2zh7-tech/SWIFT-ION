# SWIFT-ION v2.2.1 — NICT / TEC skill test regression fix

## 原因
v2.2 の `scripts/build_tec_skill.py` が、NICT観測所の固定座標で予報を抽出できなかった場合でも、その観測所名を登録済みとして確定していました。同名の後続観測所メタデータで再試行できず `NO_VALID_STATION_FORECASTS` となり、スナップショット/事後照合テストが連鎖して失敗しました。

## 修正
予報発表時刻に存在するモデル値を少なくとも1件抽出できた場合だけ、観測所名と位置を登録確定します。固定NICT座標で値が取れない場合、後続の観測所座標メタデータに再試行できます。観測されたfoF2値を予報に使う変更ではありません。

## 上書きするファイル
- `scripts/build_tec_skill.py`（既存ファイルに上書き）
- `tests/test_v221_station_fallback.py`（新規回帰テスト）

## GitHub Desktop
1. ZIPを解凍し、このZIPの `scripts` と `tests` フォルダを、SWIFT-ION リポジトリの同名フォルダに上書きコピー。
2. GitHub Desktop Summary に `Fix NICT station sampling regression in TEC skill tests` と入力。
3. Commit to main → Push origin。
4. GitHub Actions の `Run unit tests` の結果を確認。

## スコープ
NICT実測CSVの取込、経験係数、AI学習、365日履歴、予報式、GitHub Pagesのワークフローは変更していません。
以前の履歴を削除・初期化する処理もありません。

## 検証
ローカル再現環境で `test_tec_skill.py` 12件、`test_nict_bridge.py` 8件、`test_fof2_extended.py` 9件、今回の新規回帰テスト2件に成功しました。GitHub Actions上での139件+2件の全テスト完了は、Push後に確認が必要です。
