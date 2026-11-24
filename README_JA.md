# SWIFT-ION｜GitHub workflow permission 復旧

## 原因
以前の Actions では `.github/workflows/pages.yml` を `git add` して、GitHub App トークンで push しようとしました。GitHub では workflows 権限のないトークンによるワークフローファイルの更新が拒否されます。テストとコード修正は成功していてもコミットが反映されません。

## 手順
1. このZIPの `.github/workflows/repair_observed_kp_and_stations.yml` を、GitHub リポジトリの同名ファイルへ **Web UI で上書きしてコミット** してください。GitHub アカウントによる編集であり、Actions のトークンではありません。
2. GitHub Actions > `Repair observed Kp and enable 32 globally balanced stations` > `Run workflow` を一度実行。`Commit source files only` が成功することを確認してください。
3. **重要**: GitHub Web UI で `.github/workflows/pages.yml` を開き、`--max-stations 16` を `--max-stations 32` に変更してコミットしてください。これをしないとビルド時の観測地点上限は16のままです。
4. `Build and publish SWIFT-ION` が成功することを確認してください。

## 何を変更したか
- 復旧用 Actions のコミット対象から `.github/workflows/pages.yml` を除外。
- 誤って workflow ファイルを staged していたら中断する保護を追加。
- それ以外の観測Kp・全球32地点・全テストの処理は前回と同じ。
- 365日観測履歴・SWIFT-TEC予報計算の変更なし。

## 注意
GitHub Pages の公開と実際の32地点観測取得は、公開後の Actions ログで確認してください。32は上限であり、供給元に観測値がなければ32地点未満になります。
