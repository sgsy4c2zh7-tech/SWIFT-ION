# SWIFT-ION / 全画面地図 + GNSS PDOP / TEC位置偏差 [m] + 等値線

## 対象（2026-11-23 に確認した公開SWIFT-ION構造）

- リポジトリ: `sgsy4c2zh7-tech/SWIFT-ION`
- 対象ページ: `docs/animate.html` (Global Time Animation)
- SWIFT-TEC参照元: `_upstream_swifttec/docs/data/gnss/*_latest.tle`
- 既存 `docs/animation/` のVTEC30分予報と再生機能は利用継続
- **既存の `.github/workflows/pages.yml` を削除・全面上書きしない**

## 1. ZIPのファイルをGitHubリポジトリの同じパスへ配置

| ZIP内 | 動作 |
|---|---|
| `docs/animate.html` | 全画面地図と操作HUD・GNSS/TEC表示 |
| `docs/shared/gnss-iono.mjs` | SGP4位置/PDOPと電離圏起因の位置偏差をメートル計算 |
| `docs/shared/field-contour-canvas.mjs` | 欠損を跨がない等値線/等値線ラベル/数値の描画 |
| `scripts/build_gnss_latest.py` | SWIFT-TECの最新TLEを1ファイルに変換・上書き |
| `tests/test_gnss_latest.py` | ビルド側の単体テスト |
| `tests/test_gnss_iono.mjs` | JS数値処理の単体チェック（任意実行） |
| `patch_pages_workflow.py` | 既存ワークフローに1ステップだけ差し込む補助（任意） |

**`docs/shared/forecast.js`、SWIFT-TEC本体、foF2のfield.html、年別ログには変更を加えません。**

## 2. 必須：Pagesワークフローに以下を1ステップ追加

GitHubで `.github/workflows/pages.yml` を開き、既存の
`- name: Read upstream SWIFT-TEC (read-only)` の **直後**、
`- name: Calculate SWIFT-TEC VTEC forecast and 30-minute animation` の **直前**に挿入：

```yaml
      - name: Prepare GNSS current TLE snapshot (latest only)
        run: python scripts/build_gnss_latest.py
```

これだけで既存の定期Pagesビルド（現行30分おき）時に、すでにクローンしているSWIFT-TECから最新のGNSS TLEと既存の`vendor/satellite.min.js`を取り込みます。

ローカルでリポジトリを編集しているなら、リポジトリのルートで

```bash
python patch_pages_workflow.py
```

を1度実行すれば自動で上のステップを追加できます。同じコマンドを複数回実行しても二重挿入しません。**GitHub Web UIで編集する場合は手動で上の3行を追加してください。**

## 3. GitHubのCommit message (Summary)

`Add full-screen GNSS PDOP and ionospheric error contours`

## 4. 画面の使い方

`Global Time Animation` → `⛶ 地図を全画面`：地図だけを全画面にし、時刻を右上、再生・30分送り・速度・物理量・衛星群・スライダーを地図下側の半透明パネルに配置。Escで元の通常レイアウトへ戻ります。

物理量として `VTEC` / `直前30分差` / `GNSS PDOP` / `GNSS L1電離圏起因位置偏差[m]` を選択。等値線・線ラベル・格子数値を個別に表示できます。`GPSのみ` / `GPS+QZSS` / `全5システム（実験）` が選べます。全5システムでは衛星群ごとの独立した時計オフセットを最小二乗で扱います。

## 5. データ量と技術上の注意

- GitHub Pagesビルドで生成するGNSSデータは **`docs/gnss_latest.json` 1ファイル** のみで、ビルドのたびに再生成・上書きします（Gitに時系列履歴をコミットしません）。
- `docs/vendor/satellite.min.js` はSWIFT-TECに既存のSGP4ライブラリをビルド時にコピーします。新規CDN/APIキーは不要です。
- DOP/位置偏差の30分別・日別データはファイル保存しません。閲覧中の選択フレームだけブラウザ上で計算します（メモリ内キャッシュ最大2フレーム）。
- TLE epochから±72時間を超える場合はその衛星を使いません。古いTLEだけで形状解が不足する場合は、**地図を欠測として表示**します。
- 単周波L1（1575.42MHz）相当の未補正電離圏一次遅延を推定します。VTECを350km薄殻で衛星方向のSTECへ変換し、幾何学行列から**位置バイアス（m）**とPDOPを計算します。
- これは「衛星位置とVTECから予想される電離圏成分の推定値」であり、受信機の実際の総測位誤差・補正後誤差・95%精度・GNSS可用性ではありません。とくにBeiDou/GLONASS/Galileo等の異なる周波数や衛星健全性・周波数バイアスは単純化しています。
- 欠損を跨ぐ等値線は描きません。配色と値は研究用モデルであり、観測による妥当性検証は未実施です。

## 6. テスト

```bash
python -m unittest discover -s tests -v
node tests/test_gnss_iono.mjs
```

既存の `pages.yml` のテストステップはPythonの新テストも自動で検出します。JS追加テストは上記のNodeコマンドで任意実行できます。

## 7. うまく表示されない場合

- GNSS項目を選んでも空白：Actionsの`Prepare GNSS current TLE snapshot`が成功しているか、`docs/gnss_latest.json`と`docs/vendor/satellite.min.js`がPages成果物にあるか確認。
- TLEが古い：SWIFT-TEC側の`Fetch GNSS GP data`定期処理が成功しているか確認。古いTLEでは意図的に数値を表示しません。
- `iframe`や全画面権限制限：ブラウザのFullscreen APIが有効か確認。通常画面の地図は使えます。
- 直近のGitHub Pages公開成功まで待っても表示が変わらない場合：ブラウザ強制再読み込み（Ctrl+F5）。
