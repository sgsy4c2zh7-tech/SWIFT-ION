# SWIFT-ION v1.7 — foF2 Map Background + Cesium 2D/2.5D & Side Camera

## インストール（GitHub Desktop）
1. ZIPを解凍する。
2. ZIP内の `docs/` と `tests/` をローカル SWIFT-ION リポジトリのルートへコピー（同名ファイルは上書き）。
3. GitHub Desktopで `Add georeferenced foF2 maps and Cesium camera modes` とコミットし、Push。
4. GitHub Actionsの Pages 公開完了後、`/field.html` と `/explorer.html` を開く。

## 変更ファイル（他は触らない）
- `docs/field.html` — Leaflet地図の上に予報PNGを緯度経度で投影。ダーク/OSM/衛星切替、地図クリックの値、透明度、IRIサイト表示。
- `docs/shared/map-geo.mjs` — EPSG:3857（Web Mercator）に合わせた緯度方向のサンプル計算。
- `docs/explorer.html` — Cesium 3D/2D/2.5D、横から/真上からの視点、角度・方位・距離スライダー。
- `docs/shared/gaia3d-app.mjs` — Cesiumの投影法・カメラ操作。
- `tests/test-map-geo.mjs`, `tests/test_v17_ui.py` — テスト。

## 維持される機能
- 30分 VTEC動画、foF2/hmF2/Neの30分動画
- 3D多層、Voxel、Isosurface、経路断面、ISEE表示
- 365日履歴、既存 `pages.yml`、SWIFT-TECおよびNOAA取得
- IRI基準とTEC連動実験シナリオの区別。新しい物理モデル・予報精度の向上は含まない。

## 表示上の注意
- 地図タイルは実行時のネットワーク接続が必要です。背景が白/黒になるときはタイル配信・広告ブロック・ブラウザネットワークを確認してください。
- 2Dでは高度を平面投影するため、層を横から確認するときは3Dへ戻って Side View を押してください。
- 多層の色分布は疎なIRIモデルの空間補間であり、3D電子密度の実測ではありません。
- 完成したZIPのテストはローカルの構文／数値検査。CDNに依存する本番3D描画はPush後の確認が必要です。
