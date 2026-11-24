# SWIFT-ION: GNSS snapshot generation fix

## 内容
`.github/workflows/pages.yml` を現行 `main` 版に対して最小変更しています。

追加したのは `Read upstream SWIFT-TEC (read-only)` の直後にある
`Build latest-only GNSS snapshot from SWIFT-TEC` ステップだけです。

このステップは:
- `scripts/build_gnss_latest.py` を実行（現行リポジトリに既存）
- `docs/gnss_latest.json` と `docs/vendor/satellite.min.js` の生成・存在を確認
- JSONのスキーマ、有効衛星数、履歴非保存を検査

既存のTEC予報・foF2・学習・365日検証・Pages公開処理は変更していません。

## 導入
1. ZIPを展開します。
2. GitHubリポジトリ `sgsy4c2zh7-tech/SWIFT-ION` の `.github/workflows/pages.yml` を、ZIP内の同名ファイルで上書きします。
3. `main` ブランチにコミットします。
   Summary: `Fix GNSS snapshot generation in Pages workflow`
4. GitHub Actionsの `Build and publish SWIFT-ION` が完走しているか確認します。
5. 公開後、次のURLを開いてJSONが表示されるかを確認します。
   https://sgsy4c2zh7-tech.github.io/SWIFT-ION/gnss_latest.json

## 注意
- GNSS衛星データは最新TLEの1セットのみを処理・出力し、過去のTLEやDOP履歴ファイルを新規保存しません。
- `gnss_latest.json` の生成はビルド中に行われ、Gitの追跡対象としてコミットする必要はありません。
- 最新TLEは72時間を超える時刻では欠測になります。
- HTTP 503が継続する場合は、GitHub ActionsのGNSS生成ステップとPagesの配信状況を確認してください。
- このZIPは公開設定の修正で、すでに導入済みのGlobal VTEC/foF2 UIは変更しません。
- GitHubへのコミットおよび公開後の動作確認はまだ実施していません。
