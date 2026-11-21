# SWIFT-ION v0.8 — 科学的品質管理とGloTEC事後照合

## 目的
- 前回v0.7のIRI計算（72地点/3時刻）を **80地点/5時刻** に増やす（計算時間を監視）。
- IRI 100–2000 km 部分TECとSWIFT-TEC VTECの **モデル差分** を報告する。異なる高度範囲なので精度として扱わない。
- 予報発表時刻より未来の対象時刻が過ぎてから、公開SWIFT-TECリポジトリのNOAA GloTEC事後格子（30分ごと）と**同時刻・同座標に完全一致する場合のみ**MAE/RMSE/Biasを算出する。GloTECはモデルベースの推定プロダクトで、独立真値ではない。
- IRI計算地点からの補間距離と、TEC感度係数の適用可能率を監視する。
- GitHub Actionsの出力JSONを7日間の実行アーティファクトとして保持する（push/手動実行および約6時間間隔の定期実行を保存）。

## インストール（SWIFT-ION側のみ）
1. ZIPを展開する。
2. `.github`, `docs`, `scripts`, `tests` の4フォルダをSWIFT-IONリポジトリルートに上書きコピーする（SWIFT-TECは変更しない）。
3. GitHub Desktop: Summary `Add IRI quality monitoring and NOAA GloTEC retrospective checks` → Commit to main → Push origin。
4. Actions `Build and publish SWIFT-ION` を確認する。
5. 正常公開後: `https://sgsy4c2zh7-tech.github.io/SWIFT-ION/quality.html`

## データと評価の区別
- `docs/quality.json`：公開静的JSON（API風に取得可能）。`quality.html`が表示。
- `docs/ionosphere.json`：IRIの気候モデル推定と仮定付きTEC感度実験であり、検証済み電子密度予報ではない。
- `docs/swift_tec_vtec.json`：既存SWIFT-TECブラウザ計算結果。機械学習補正が最終出力に含まれているかは依然未確認。
- GloTEC事後照合は、発表時刻より先の `valid_at` で、かつ同じ時刻の事後アーカイブが確認でき、同座標30格子以上一致する場合のみ計算。対象時刻が未来やアーカイブにない場合は `pending`/`unavailable` と表示し、エラーや「的中率0%」としては扱わない。
- 7日保存はActionsのartifactにおける個別実行データの保持。定期実行の保存はUTCの実行時刻で6時間ごとを目安に制限。現パッチでは過去artifactを再読込して再検証する機能は未実装。次段階の追加開発対象。
- 将来GIRO等の検証用データを追加し、foF2/hmF2の予報精度を検証する。

## ローカルテスト
```
python -m unittest discover -s tests -v
python scripts/build_quality_report.py --ionosphere docs/ionosphere.json --forecast docs/swift_tec_vtec.json --archive _upstream_swifttec/docs/data/tec --out docs/quality.json
```

GitHub Actionsの実行時間は新しい80地点×5時刻のIRIで増える。40分上限に近づく場合はまず72地点×3時刻に戻すこと。
