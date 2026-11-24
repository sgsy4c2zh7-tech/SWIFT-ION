# SWIFT-ION：foF2「観測Kp別」的中率・実装パッチ

このパッケージは **SWIFT-ION** の foF2 365-day Skill に対する追加機能です。

## 何が変わる？

- **主分類：観測Kp**。NOAA SWPCの推定観測Kpを、予報対象時刻を含む3時間区間に正確に対応づけます。3時間区間の終了前には評価へ追加しません。
- **参考分類：予報Kp**。現在の予報Kp別の表は折りたたみ式で残します。
- **foF2を計算する際のKpは変更しません。** 発表時点で利用できた3日間の予報Kpで予測した値を後から改変しないため、予測の実力を公平に評価できます。
- **分類：** Kp<4 平穏、4≤Kp<5 活動的、Kp≥5 磁気嵐相当、観測Kp未取得は「不明」。不明を0や予報Kpに置き換えません。
- **NOAA推定Kp≠GFZ確定Kp**。日本語ラベルにも注意書きを追加します。
- 365日保存の `tec_matches` の各レコードに観測Kp値と出典を追記するだけ。SWIFT-TECにある観測Kpアーカイブを使い、巨大な新規TEC格子ファイルは作りません。
- メイン指標の比較対象は従来どおり「同一SWIFT-TEC実行で予報Kpの出典が確認できた事前発表済み予報」「STANDARD品質」「観測foF2照合済み」に限定します。分類を変えても元の一致ペアの母数を増やしません。

## GitHub上で適用（ブラウザのみ）

1. ZIPを解凍し、以下の3ファイルを **SWIFT-ION mainブランチ** に同じパスで追加：
   - `scripts/observed_kp_support.py`
   - `scripts/apply_observed_kp_patch.py`
   - `.github/workflows/enable_observed_kp_skill.yml`
   - （任意・推奨）`tests/test_observed_kp_support.py`
2. GitHub → **Actions** → **Enable observed-Kp foF2 skill classification** → **Run workflow** を1回実行。
3. 成功すると、ワークフローが以下2ファイルの変更をmainへコミットします：
   - `scripts/build_tec_skill.py`
   - `docs/year.html`
4. GitHub → Actions → **Build and publish SWIFT-ION** → **Run workflow** を実行。Actions内で観測Kpを過去の予報照合履歴と対応づけ、GitHub Pagesに表示します。
5. `year.html` の「磁気活動別のfoF2予報精度（観測Kpで分類）」を確認。下に予報Kpの参考表が表示されます。

> GitHub Actionsにリポジトリの書き込み権限がない場合は、手順3が失敗します。その場合はgit cloneしたリポジトリで `python scripts/apply_observed_kp_patch.py` を実行し、変更された2ファイルをmainへコミットします。

> **注意:** GITHUB_TOKENで作成したコミットは通常のpushトリガーを発火しないため、手順4は手動で行ってください。

## ローカル適用（Gitあり）

ZIP内のファイルをリポジトリの同じパスへ配置したあと：

```bash
python scripts/apply_observed_kp_patch.py
python -m unittest discover -s tests -p 'test_observed_kp_support.py' -v
git add scripts/observed_kp_support.py scripts/apply_observed_kp_patch.py scripts/build_tec_skill.py docs/year.html tests/test_observed_kp_support.py
git commit -m "Classify foF2 skill by observed Kp; keep forecast Kp as reference"
git push
```

## 仕組み・監査

- 観測Kp：`_upstream_swifttec/docs/data/ai/isee_japan/kp_actual_archive.json` （SWIFT-TECが保存したNOAA SWPCの推定観測Kp）
- 予報Kp：従来の `docs/swifttec_kp_issued.json` とfoF2発表済み履歴（変更しない）
- 観測値の結合キー： `floor(valid_at UTC / 3時間)` で求めた3時間区間開始時刻。近傍Kpへの丸めや未来Kpでの補完は行わない。
- 観測Kpが欠測： `UNKNOWN` として表示。すでに保存されている過去の実測Kpは一時的な取得失敗で消さない。
- API／表示の項目： `kp3day_by_observed_activity`（新規・主分類）、`kp3day_by_activity`（従来の予報Kp別・参考分類）。
- 日別・月別CSVに `observed_kp_quiet_n`, `observed_kp_active_n`, `observed_kp_storm_n`, `observed_kp_unknown_n` が追加。
- 発表済みfoF2、AI係数の学習、TLE、DOP、TECデータの計算は一切変更しません。

### 大事な区別

- **的中率** = 「発表済みfoF2予報 vs 後日のfoF2観測」を比較。Kpはその比較を磁気活動で分類するためだけに使用。
- **予報Kpによる参考分類** = 実際の磁気嵐ではなく予報で想定した磁気活動別の成績。
- **Kp予報の誤差そのもの** は今回の表に含みません。必要なら別途、同じ対象時刻の予報Kpと観測Kpの差を算出します。
- データ不足なら「評価待ち」。変更だけで評価0件が必ず解消するわけではありません。

## Commit Summary

`Classify foF2 skill by observed Kp; keep forecast Kp as reference`
