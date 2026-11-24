# SWIFT-ION GitHub Pages 公開エラー修正

対象: `sgsy4c2zh7-tech/SWIFT-ION`

## 今回の原因

2026-11-24 の Actions 実行 `45353056862` は、テスト・予報生成・`github-pages` 成果物アップロードを完了したにもかかわらず、直後の `actions/deploy-pages@v4` から `Found 0 artifact(s)` / `No artifacts named "github-pages"` が返って公開できませんでした。GitHub の成果物一覧には当該 `github-pages` 成果物が存在していました。

これは少なくとも単純な「成果物が生成されなかった」という問題ではありません。アップロード完了直後のメタデータ反映遅延や GitHub 側の一時的な API 不整合が疑われますが、確定原因は未特定です。

## 適用方法

1. ZIP を解凍します。
2. GitHub の `SWIFT-ION` リポジトリ内 `.github/workflows/pages.yml` を、ZIP 内の同じパスの **ファイル全体**で置き換えてコミットしてください。すでに新しい変更を加えた場合は、差分を確認してからマージしてください。
3. コミットにより `Build and publish SWIFT-ION` が起動します。必要なら Actions から手動実行して構いません。
4. Actions の `test-and-publish` と `deploy` の **2ジョブ**が順番に成功することを確認します。

コミットメッセージ例:
`Fix GitHub Pages deployment artifact visibility with separate job`

## 修正内容

- `test-and-publish` から GitHub Pages 環境宣言を外し、従来どおり予報・検証・履歴・成果物アップロードを実施
- `deploy` ジョブを新設し、`needs: test-and-publish` でアップロード完了後に開始
- `deploy` ジョブに `pages: write`, `id-token: write`, `actions: read` を設定
- 公開前に、Actions API が `github-pages` 成果物を返すまで最大約90秒間、5秒おきに確認（欠損している場合は明確なエラーにする）
- `deploy` のみ `github-pages` 環境を使用

## 保存している機能

元の `pages.yml`（Git blob SHA `3f3569607fd1be1e86cefcee9c98164400818b9f`）に対する最小修正です。SWIFT-TEC連動予報、SWIFT-ION foF2 モデル、GNSS、観測Kp、32地点選定処理、365日履歴、生成成果物の一覧は変更していません。

**今回のZIPでは** 以前の32地点拡張に合わせて `--max-stations 16` を `--max-stations 32` に変更しています。これで再び16地点へ戻ることを防ぎます。

## 注記

32地点への拡張も既に有効にしている場合、`pages.yml` の `--max-stations` が **32** になっていることを必ず確認してください。このZIPは32地点の設定にしてあります。すでに他の変更を `pages.yml` に加えた場合は、差分を見てからマージしてください。

## 動作確認

`pages.yml` の YAML構文を解析し、2ジョブの分離・順序・環境・アップロード処理の継続を静的検証済みです。GitHub Actions の本番デプロイは未実行です。
