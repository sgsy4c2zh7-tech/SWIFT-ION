# SWIFT-ION: GNSS TLE 72時間制限を撤廃（差し替え版）

## 変更内容
- **GNSS TLEの伝搬年齢制限を削除**：最新TLEを使用し、全予報時刻でSGP4計算を試みます。
- 衛星を72時間で除外する条件を削除し、72時間経過時の欠測メッセージも修正。
- GNSS最新TLEの生成時に付与する「72時間上限」のメタデータを撤廃。
- **TLE最新1セットだけ**という保存ポリシーは維持。データ量を増やす履歴ファイルは作りません。
- GNSS衛星群の個別選択、HDOP/VDOP、水平方向・垂直方向・3D偏差、等値線、全画面機能を維持。

## GitHubでの上書き先
このZIPのディレクトリ構造を維持して、以下の3ファイルを置き換えてください。
1. `docs/shared/gnss-iono.mjs`
2. `docs/animate.html`
3. `scripts/build_gnss_latest.py`

`pages.yml` は変更不要です。以前の修正でGNSS生成ステップが導入済みの場合、そのまま利用できます。

## Commit Summary
`Remove 72-hour GNSS TLE propagation cutoff`

## 注意
SGP4の計算を長期間実施できることと、衛星位置が高精度であることは同じではありません。TLEエポックから離れるほど精度が不確かになります。モデル表示はGNSS実測測位誤差でも運用判定でもありません。

※ 本ZIPは現在のGitHub `main` にある3ファイルのblob SHAと、直前の完成版ZIPに同梱されていたファイルのSHAが一致することを確認してからパッチしています。GitHubへの直接コミットは実施していません。
