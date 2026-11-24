# SWIFT-ION: 全球/日本域 SWIFT-TEC 予報切替・透明度

このパッチは、SWIFT-TECが実際に計算した日本周辺（ISEEベース）30分間隔VTEC予報をSWIFT-IONに取り込むもので、ISEE過去観測そのものや全球予報の日本域切り抜きは使用しません。

## GitHubへアップロードするファイル

- docs/animate.html                         （上書き）
- docs/shared/gnss-iono.mjs                 （上書き）
- docs/shared/field-contour-canvas.mjs      （上書き）
- docs/shared/japan-grid.mjs                （新規）
- scripts/build_live_japan_swifttec.py     （新規）
- .github/workflows/pages.yml             （上書き）

ZIP内のフォルダ階層をそのまま配置してください。docs/field.htmlなど他のファイルは変更しません。

Commit Summary:
  Add ISEE-based Japan TEC forecast and heatmap opacity controls

## 動作

Global: SWIFT-ION従来の全球SWIFT-TEC/NOAA予報
Japan: SWIFT-TEC自身が生成する ISEE時刻別平均VTEC + 予報Kp + 日本域格子AI補正の独立した予報
日本域は別の30分格子データ docs/japan_animation/index.json と frames_*.json を、Pagesデプロイの都度生成して公開。
衛星TLEおよびDOP結果の履歴追加なし。既存のGLOBALアニメーションファイルを重複保存しません。
透明度はヒートマップだけに適用し、等値線・地図背景・ラベルはそのまま視認可能です。

## 注意

- SWIFT-TEC日本域の予報計算に失敗した場合、GitHub Pagesの他の表示は維持されますが、日本域には「日本域の独立予報が未公開」と表示されます。全球予報を日本域のISEEモデルと偽って表示することはありません。
- 最初に [Actions] → [Build and publish SWIFT-ION] の `Export SWIFT-TEC ISEE Japan regional forecast` の結果を確認してください。
- docs/japan_animation/index.json がデプロイ後に閲覧できれば、日本域の格子データ配信ができています。
- GitHub Pagesの再公開（Deploy）の成功は別途必要です。
- 日本域モデルのVTECは過去観測でなくSWIFT-TECの予報値ですが、その初期データにはISEEの過去観測に由来する平均が用いられます。未検証の研究予報です。
- 誤差とGNSSのm単位値は受信機で実際に観測された測位誤差ではありません。

## 重要なデータ容量の方針

新しい日本域用の30分データは、Pages公開のその時点の予報用スナップショットだけです。
追加の長期履歴・GNSS時系列保存はありません。

## トラブルシューティング

日本域でデータ未公開の場合：ActionsのJapan exportステップで、時刻別平均データ、Kp予報、格子AI補正の取得が成功しているか確認してください。Globalに戻れば既存のNOAA版表示を利用できます。
