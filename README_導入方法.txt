SWIFT-ION: observed Kp patch error repair + globally balanced 32 stations

原因
  現在の build_tec_skill.py のインデント（空白17個・12個）と
  apply_observed_kp_patch.py に記述されている期待値（空白18個・13個）が違い、
  Missing expected source anchor: tec groups で停止していました。

手順
  1. ZIPを解凍する。
  2. 「.github/workflows/repair_observed_kp_and_stations.yml」を
     SWIFT-IONリポジトリの同じパスへ追加してコミットする。
     （他のファイルは、このZIPからGitHubへアップロードする必要はありません）
  3. GitHub → Actions →
     "Repair observed Kp and enable 32 globally balanced stations" → Run workflow
  4. "Verify both migrations and run complete test suite" と
     "Commit repaired migration and integrated source changes" の成功を確認する。
  5. その後 "Build and publish SWIFT-ION" の成功を確認する。
     mainへのpushで自動実行されることがあります。

実行する内容
  - 既存の observed Kp 適用スクリプトの空白数を現在のコードに合わせて修正。
  - 観測Kp別foF2評価を実装。予報Kpを予報計算に使う方針は変更しない。
  - 観測所の選定・予報発行の上限を32地点に統一。世界の緯度経度区画ごとに分散選択。
  - 構文・既存の全単体テスト・重要な接続条件を検証。
  - 成功した場合のみ、改修済みソースをmainへコミット・push。

注意
  - 365日間の評価履歴は書き換えません。過去の予報値を後付け再生成しません。
  - 観測Kpは3時間区間終了後に評価データへ追加します。
  - 最大32地点は上限です。実際の観測可能地点は元の観測APIと品質条件によります。
  - このZIP自体ではGitHubに変更は加わりません。実行はユーザー側で行ってください。
  - 実環境のActionsでの成功は未確認です。

Commit summary (for uploading the workflow):
Add one-click repair for observed Kp migration and 32-station coverage

補足: 予報・観測Kp集計行に加え、レポートのmetadata行の空白差も修正します。
