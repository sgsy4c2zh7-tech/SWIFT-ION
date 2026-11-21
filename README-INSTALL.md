# SWIFT-ION 自動連携 v0.4 試験版

SWIFT-TEC の公開リポジトリを GitHub Actions が read-only clone し、Chromium で実際の `runForecast()` を実行して、Web表示用に 2時間間隔・格子間引きの VTEC JSON を生成します。SWIFT-TEC 本体は変更しません。CSVを作る方式ではなく直接JSONを生成します。

## 導入
ZIP内の `.github` と `scripts` を SWIFT-ION リポジトリ直下へコピーし、GitHub Desktopで Commit / Push。
Actions > Build and publish SWIFT-ION > Run workflow で初回手動実行。緑になったら https://sgsy4c2zh7-tech.github.io/SWIFT-ION/tec.html を再読み込み。

## 注意
- 実行は未検証。上流UIやNOAA APIの仕様変更・CORS・ネットワーク制約で失敗する可能性があります。Actionsの「Calculate and publish SWIFT-TEC VTEC forecast」のログで確認してください。
- 予報はSWIFT-TECのブラウザ計算結果です。ML補正段階は未検証、各層電子密度ではありません。
- NOAAの入力が欠けた場合、誤った予報を出さないよう失敗させます。
- 出力JSONはActions上で生成してPagesにデプロイされます。リポジトリにコミットされません。
- GitHubのcronは正確な30分実行を保証しません。
