# SWIFT-ION v1.4 — ISEE Japan + GAIA-style 3D Explorer

既存の SWIFT-ION 自動更新・30分アニメーション・365日の精度履歴を維持して、3D Explorer に日本ISEE高解像度VTECと経路断面を追加するアップデートです。

## 導入手順（GitHub Desktop）

1. この ZIP を展開する。
2. 同梱の `.github/`・`docs/`・`scripts/`・`tests/` の4フォルダを **SWIFT-ION リポジトリのルートへ**コピーし、同名のものだけ上書きする。
3. 特に `.github/workflows/pages.yml` は丸ごと上書きする。これは **以前の v1.3 の簡略化版ではなく、v1.2統合版のフル workflow を復元／維持した上で新しいIRI/ISEE生成ステップを1件追加したもの**。
4. GitHub Desktopで `Add ISEE Japan and GAIA-style 3D route sections` をCommit、Push originする。
5. GitHub Actions → `Build and publish SWIFT-ION` の成功を確認する。新ステップは `Build GAIA-style IRI and ISEE Japan explorer`。
6. GitHub Pages: `https://sgsy4c2zh7-tech.github.io/SWIFT-ION/explorer.html`

## ファイル（このパッチで追加／上書き）

- `.github/workflows/pages.yml` : 現行の全自動パイプラインと365日保存を維持した**フルコード**。古いスタイルに戻したり、他のジョブ・履歴書き込みを消さない。
- `scripts/build_3d_explorer.py` : 既存の **IRI実計算** `docs/ionosphere.json` を読み込み、必要ならISEEの記録時刻に追加のIRI計算を実施。
- `docs/explorer.html` : 日本／全球切替、GAIA型立体点群、縦断面、水平高度スライス、地点別 Ne(h)、飛行経路断面、ISEE VTEC表示。Cesiumトークン／外部JS不要のCanvas描画。
- `docs/index.html` : 既存の全機能カードを維持して、新しい3D Explorerへのカードとショートカットを追加。
- `tests/test_3d_explorer.py` : 出典時刻、モデル種別、ISEE欠測、保存パス検証等の単体テスト。

## 時間・物理量の取り扱い（重要）

- **Global IRI**：既存 `docs/ionosphere.json` の実計算Ne(h)をそのまま使います。80計算地点×5時刻の空間補間は高解像度の実測ではありません。
- **Japan ISEE**：SWIFT-TECで既にGitに保存されている `_upstream_swifttec/docs/data/isee_tec/index.json` から観測 **VTEC [TECU]** を読みます。`docs/data/ai/isee_japan/...` のAI補正成績や学習係数とは別物です。
- 最新アーカイブの `:00` / `:30` の最大3時刻を選び、**その時刻のIRI電子密度を日本の36地点で別途計算**します。ISEEに5分刻みしかない／欠測の場合は時刻を捏造しません。
- ISEEの配信が何日も遅れる場合があります。画面に**観測UTCとソース年齢（時間）**を表示します。これはリアルタイムの日本3D電子密度ではありません。
- 縦断面は実IRI計算地点に対する **空間IDW補間**です。地点から大きく離れる場合（日本域モデルで最寄りIRI地点から850km超）は補間しません。
- 全球のVTEC比較は同じフレームの **SWIFT-TECモデルVTEC**、日本は同じ記録UTCの **ISEE観測系VTEC**。いずれもNe(h)そのものではありません。
- GPS L1遅延（表示される場合）は垂直一次電離圏群遅延の計算例であり、航空機の航法可用性や実際の飛行経路のリスク予報ではありません。
- GAIAの計算コード・出力を実際に使っているわけではありません。ここでいう「GAIA型」は高度断面など**表示の形式**を指し、科学的なモデルはIRI-2020です。
- 以前のv1.3で作られた `docs/ionosphere_3d.json`（合成フォールバックデータ）は**新画面では読み込みません**。データがない場合は欠損を表示します。
- SWIFT-TECのISEE「AI補正予報」の生成・接続は今回**未実装**です。追加したのは **ISEE AGRID2 VTECアーカイブ**の読み取りとIRI同時刻計算です。

## 操作方法

- **日本全国の地点**：札幌・仙台・東京・名古屋・大阪・広島・福岡・鹿児島・那覇の選択、または任意の緯度・経度を入力。
- **経路**：東京–那覇、札幌–福岡、東京–大阪、仙台–名古屋、福岡–鹿児島、東京–シドニー（全球モデルを選択）、または任意2〜12点を緯度・経度で入力。
- **ビュー**：3D地球／垂直断面／高度スライス／経路断面。地球をドラッグして回転可能。
- **時間**：ISEEアーカイブの30分スロットを切替・再生。全球IRIはその実計算時刻のみ切替。

## 科学的・技術的制約

- 本件は一般公開データによる研究表示です。機微な位置・実運用情報をGitHub Pagesへアップロードしないでください。
- 新規のIRI計算は最大3時刻×36地点を追加するため、Actions実行時間は従来より増えます。時間が厳しい場合、`--regional-sites 24`、`--max-isee-frames 2` に下げられます。
- ISEEデータが取得できない場合、新画面の **全球IRI** は表示できますが、日本のISEE機能は未利用可能になります。参照を捏造する処理はありません。

## 検証範囲

- Python単体テスト、workflow YAML読込、JavaScript構文検査、および**模擬JSONを使ったローカルChromiumの各画面操作**で動作確認。
- **GitHub Actions本番のIRI実計算・最新ISEEファイル・GitHub Pagesへのデプロイは未実行**。公開後にActionsログをご確認ください。
