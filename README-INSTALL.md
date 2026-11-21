# SWIFT-ION — 全機能リンク付きホーム画面

## インストール

1. ZIPを解凍してください。
2. `docs/index.html` を、ローカルSWIFT-IONリポジトリ内の同じ場所へ上書きコピーしてください。
3. GitHub DesktopからCommit → Push originしてください。
4. GitHub Pagesの公開処理が成功したら https://sgsy4c2zh7-tech.github.io/SWIFT-ION/ を開いてください。

推奨コミットメッセージ: `Add full feature navigation to SWIFT-ION homepage`

## このパッチの内容

- `docs/index.html` のみを変更。予報ロジック・Workflow・365日履歴は変更しません。
- 11機能を4カテゴリにまとめ、各機能をカードで直接開けるようにしました。
- デスクトップ、スマートフォン対応。キーボード操作と画面読み上げ用の見出し・ナビゲーションを用意しています。
- 既存の `animate.html`, `impact.html`, `globe.html`, `ops.html`, `ionosphere.html`, `tec.html`, `year.html`, `skill.html`, `ionosonde.html`, `quality.html`, `map.html` を参照します。
