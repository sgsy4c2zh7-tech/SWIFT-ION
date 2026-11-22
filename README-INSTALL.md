# SWIFT-ION v1.9.2 — Map-editable multi-waypoint routes + detailed axes + native Excel charts

## 追加した機能

1. **地図をタップして経由点を追加**。途中の方向転換を含む**2〜12地点のルート**（5地点も可）を作れます。
2. **ドラッグでピン移動**。地図のスクロールやピンチズームはいつもどおり使えます。
3. **経路線をタップして途中へ挿入**。編集モードの「◇ 経路に挿入」を選び、点線の経路をタップします。
4. **↑ ↓ で地点の並び替え、× で地点削除**。座標の手入力とも相互同期します。
5. **経路編集に追従して再計算**：foF2距離グラフ、30分グラフ、飛行経路動画、電子密度断面。
6. **Excel出力に Waypoints シート**：緯度・経度、区間距離、累計距離。
7. 前回v1.9.1の横軸改良も同梱：距離50/100/200/500km、経過時間10/15/30/60分、NICT比較3/6/12/24時間、ホバー値表示。
8. 飛行経路Excelに編集可能な折れ線グラフ2点、NICT 4地点比較Excelに編集可能な折れ線グラフ4点。

**注意：** 地図のドラッグ操作は、デフォルトでは地図自体を移動します。経由点を作る場合は「＋ 地図タップで追加」、線の途中への追加は「◇ 経路に挿入」を押してください。ピンはどのモードでもドラッグできます。

## インストール

1. このZIPを解凍。
2. 中の `docs/` フォルダを、ローカル `SWIFT-ION/docs/` に上書きコピー。
3. GitHub Desktopで Commit → Push。
4. `route_excel.html`（Excel分析）と `route.html`（30分動画）の地図を操作する。
5. `nict_compare.html` も横軸の細分化とExcelグラフ追加を確認。
6. 以前の画面が出たら `Ctrl+F5` で再読込。

コミット例：`Add multi-waypoint map route editing and Excel charts`

## フォルダ構成

- `docs/route_excel.html`：地図で経路編集、100km/30分グラフ、Excel出力
- `docs/route.html`：動画で地図経路編集（現在のv1.6ベースのページと互換）
- `docs/nict_compare.html`：4地点比較の横軸改善
- `docs/shared/route-map-editor.mjs`：Leaflet用経由点編集モジュール（新規）
- `docs/shared/axis-plots.mjs`：目盛り/ホバー表示（新規）
- `docs/shared/xlsx-charts.mjs`：画像ではないExcelネイティブ折れ線グラフ（新規）
- `tests/*.mjs`：Nodeによる検証

**pages.yml・NOAA取得・ISEE取得・モデル予報計算・365日保存の処理は変更しません。**

## 予報の科学的制限

- 経路は**入力地点間を大圏で接続**した公開・架空の研究用ルートです。実際の航空管制経路ではありません。
- 対地速度は一定と仮定します。風・旋回半径・空域制限は考慮していません。
- 100km/30分で数値を抽出しますが、元のfoF2予報の空間・時間精度が高くなるわけではありません。
- foF2はHF通信の最適周波数やMUFと同じではありません。実運用の可用性判定には使用できません。
- 予報の外側・空間補間不能・TEC連動の対象外は欠測としてグラフ／Excelでは空欄とします。
- GitHub Pagesで使うのは**公開・架空の経路**のみとしてください。部隊の非公開情報は掲載しないでください。

## ローカル検査

```
node tests/test_route_map_editor.mjs
node tests/test_route_map_leaflet.mjs
node tests/test_chart_export.mjs
node tests/test_nict_charts.mjs
```

※ 本番ブラウザのLeafletタッチ操作と、GitHub Actions後の全画面表示は未検証。地図ライブラリの配信がない場合は表示されません。
