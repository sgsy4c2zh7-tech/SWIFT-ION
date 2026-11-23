# SWIFT-ION v2 完成版（2026-11-23）

## 反映ファイル
GitHub [sgsy4c2zh7-tech/SWIFT-ION](https://github.com/sgsy4c2zh7-tech/SWIFT-ION) の `main` に以下を同じパスで上書き/追加します。

1. `docs/animate.html` — Global VTEC画面の GNSS衛星群チェックボックス、HDOP/VDOP、水平方向・垂直方向・3D電離圏起因位置偏差、欠測通知、地図のみ全画面表示。
2. `docs/shared/gnss-iono.mjs` — 任意GNSS選択対応、ENU偏差分解、DOP計算。
3. `docs/shared/field-contour-canvas.mjs` — 地図上の等値線/値ラベル。既存v1同じファイルです。
4. `docs/field.html` — foF2、hmF2、電子密度、VTEC画面も **地図領域だけ全画面**。時刻は右上、操作類は地図内下部。
5. `docs/shared/field-contours.mjs` — foF2等値線の既存モジュール（旧ZIPを使っていない場合も導入できます）。
6. `scripts/build_gnss_latest.py` — SWIFT-TECの既存最新TLEを1ファイルに集約（既存版と同じ）。

## 絶対に必要な404対策
Pagesが公開する `docs/gnss_latest.json` は **手動登録するファイルではなくビルド生成物**です。`docs/animate.html` だけ更新しても404のままです。

`.github/workflows/pages.yml` の `Read upstream SWIFT-TEC (read-only)` の **直後**、`Calculate SWIFT-TEC VTEC forecast and 30-minute animation` の直前に、ZIP内 `WORKFLOW_追加するステップ.yml.txt` の4行を追加してください。

ローカルで作業する場合は、ZIP内の `patch_pages_workflow.py` をリポジトリのルートへコピーして `python patch_pages_workflow.py` を実行すれば、既存のworkflowを保持したまま自動挿入できます（既存ステップがあれば検証付きに更新）。

新しいファイル: `docs/gnss_latest.json` は **Actions実行時にSWIFT-TECから取得**され、毎回1ファイルだけ生成します。過去のTLE・過去のDOP格子・過去の推定誤差格子は保存しません。`docs/vendor/satellite.min.js` も同時に1つだけ生成します。

**Pagesでの確認:** GitHub Actions の `Build and publish SWIFT-ION` が緑色になった後、`https://sgsy4c2zh7-tech.github.io/SWIFT-ION/gnss_latest.json` にアクセスし、`schema: swift-ion-latest-gnss-v1` が表示されるか確認してください。404が残る場合はWorkflowの変更がmainへコミットされているか、Actionsの実行ログを確認してください。

## 注意：科学的意味
- 表示する水平・垂直・3Dのm値は**単周波L1換算で、未補正の電離圏遅延に起因する推定位置偏差**です。実際の受信機の測位精度、補正済み位置誤差、保証精度ではありません。
- GPS/他群の衛星時刻バイアスは群別に推定しますが、GLONASS等の固有周波数、各群の信号遅延、受信機バイアス等を含む厳密な測位解ではありません。
- TLEのエポックから72時間を超える時刻や衛星配置が不足する地点は**欠測**。最新TLEだけでは5日間すべての予報のDOPを信頼して再現できません。
- 単独QZSSなど可視衛星が4機未満ではPDOP・位置偏差を出せない場合があります。
- ヒートマップ／数値は欠測を補間して作りません。ブラウザ内キャッシュは最大2フレーム。

## GitHub Commit Summary
`Fix GNSS snapshot, add constellation selection and H/V error maps, improve map fullscreen`
