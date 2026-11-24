# SWIFT-ION — 全球観測所32地点・地理的均衡サンプリング

## 目的

foF2・hmF2検証に使う **観測所の上限を最大32地点**へ拡張します。緯度3帯 × 経度6帯の18地域区画のうち、**KC2G/GIROが実際に公開している観測所がある区画**を優先し、北半球や欧州への過度な偏りを緩和します。

**重要：32地点はシステム側の上限であり、32地点の有効データが必ず取得できるという意味ではありません。** 元データに存在しない空白地域について観測所や観測値を生成しません。

## ZIPからGitHubに追加するファイル

- `scripts/station_coverage.py` — 地理的に均衡した観測所選定・地域別件数
- `scripts/apply_station_coverage_patch.py` — 現行コードを安全に変更するパッチ
- `docs/station_coverage.html` — 世界地図、取得数、緯度帯×経度帯のカバレッジ
- `tests/test_station_coverage.py` — 数値・地理分散・冪等性テスト
- `.github/workflows/enable_station_coverage.yml` — 手動適用ワークフロー

現行の `pages.yml`、`validate_ionosondes.py` 等を古いコピーで直接上書きしないよう、専用のパッチ方式にしています。

## 導入手順

1. ZIPを展開し、上記5ファイルを `sgsy4c2zh7-tech/SWIFT-ION` の同一パスにアップロードして `main` にコミットします。
2. GitHub → **Actions** → **Enable globally balanced ionosonde sampling** → **Run workflow** を選択します。
3. 成功すると次の6ファイルが自動更新・コミットされます。
   - `scripts/validate_ionosondes.py`
   - `scripts/build_prospective_skill.py`
   - `scripts/build_year_archive.py`
   - `scripts/build_tec_skill.py`
   - `.github/workflows/pages.yml`
   - `docs/year.html`
4. 次に **Actions → Build and publish SWIFT-ION → Run workflow** を実行します。GitHubの自動ワークフローが作ったコミットでは、別のActionsが自動起動しない場合があるためです。
5. ビルド完了後、公開サイト `https://sgsy4c2zh7-tech.github.io/SWIFT-ION/station_coverage.html` を開いて、取得できた地点数と世界地図を確認してください。

### コミットメッセージ（Summary）

`Expand globally balanced ionosonde sample to 32 stations`

## 変更前→変更後

| 対象 | 変更前 | 変更後 |
|---|---:|---:|
| 最新イオノゾンデ観測を抽出 | 最大16 | **最大32** |
| IRI単独の将来予報で使う観測所 | 最大12 | **最大32** |
| SWIFT-TEC連動foF2の予報対象地点 | 最大16 | **最大32** |
| 地点選定 | 最大距離方式のみ | **観測所のある18区画を優先＋距離** |
| カバレッジの可視化 | なし | **世界地図と3×6区画一覧** |
| 品質・時間条件 | 品質70以上、鮮度6時間等 | **従来どおり維持** |
| 365日間の評価履歴 | 維持 | **維持（新規に取得できる地点から蓄積）** |
| TEC予報モデル・GNSS・TLE | 変更なし | 変更なし |

## データ容量・処理時間

- 計算・保存対象の観測所数が増えるため、**履歴ファイル・IRI計算時間は増える**見込みです。
- 既存の365日アーカイブと日別圧縮JSONLをそのまま使用し、履歴の新しい種類は作りません。
- 既存の foF2 や hmF2 の的中判定閾値、予報Kp・観測Kpの区別、NOAA予報データの計算処理は変更しません。
- 利用可能な観測所が少なければ32地点未満で止まります。無理に品質基準や観測の鮮度制限を緩めません。

## 確認方法

GitHub Actionsの `Ionosonde verification against IRI climatology` に次のログが追加されます：

`Coverage (source eligible / selected / successful / occupied 30x60deg regions): ...`

`docs/ionosonde_validation.json` の `coverage` を見ると、入力観測所数・実際の抽出地点数・IRI計算成功件数・3×6区画別の件数を確認できます。地図でも同じ値を表示します。

## 限界と注意

1. 現行の取得元は **KC2G / GIRO・INGV由来の公開電離圏観測所**です。世界全域に均等に実観測が存在するわけではありません。南半球・太平洋・アフリカなどのデータが少ない場合、出典を追加しない限り空白は埋まりません。
2. 観測点以外の格子の「真の的中率」を算出する修正ではありません。foF2・hmF2の独立観測値だけで照合します。
3. 新しい地点は将来発表した予報が観測と一致した時点から的中率へ加算します。過去予報を事後再計算して水増ししません。
4. GIRO等の公開データは、各観測所の帰属表示と非営利研究利用条件などに従ってください。
5. リポジトリの構造が更新され、パッチの一致対象が見つからなければ**変更を途中まで適用せずに停止**します。そのときはGitHub Actionsのログを確認してください。

## 自動テスト

```bash
python -m unittest discover -s tests -p 'test_station_coverage.py' -v
```

8テスト：全球に18区画ある場合の選定、32地点上限、品質判定、無観測領域の非捏造、日付変更線、再現性、パッチ再実行、変更不一致時の安全停止。
