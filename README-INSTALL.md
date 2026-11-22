# SWIFT-ION v2.1 — TEC-linked foF2: Physics + Empirical + AI

## 目的

SWIFT-TEC連動foF2の計算を、次の3段階へ拡張します。NICT 4地点比較では**選択済みTEC連動foF2を主表示**し、365日履歴には3段階それぞれの的中率を追加します。SWIFT-TECの上流リポジトリは変更しません。

1. **物理基準**：IRIの鉛直電子密度プロファイルから部分TECとNmF2を計算し、SWIFT-TEC VTECと照合。`F=VTEC_SWIFT / TEC_IRI(100–2000 km)` が0.5～2.0の範囲など品質条件を満たす場合、`foF2_physics=foF2_IRI × sqrt(F)`。同等の等価スラブ厚近似ですが、全柱TECとIRI部分TECは厳密に同じ柱積分ではないため、**検証済みの復元式ではありません**。欠測時は`null`、IRIで埋め戻しません。
2. **経験係数補正**：過去の事前発表foF2と、後から観測したイオノゾンデを用いて、TEC比の多項式、地方時、季節、予報時点のKp、利用可能な直近観測F10.7を説明変数としてリッジ回帰。学習日数14日以上・48ペア以上、時系列末尾の独立検証区間で物理基準MAEより0.02 MHz以上改善するときのみ有効化。
3. **AI補正（非線形機械学習）**：相互作用項・高調波を追加した非線形特徴量の正則化回帰で経験補正の残差を学習。35観測日・160ペア等の条件を満たし、**学習に使っていない後期間の検証**でMAEがさらに0.03MHz以上改善するときのみ有効化。ニューラルネットではなく、軽量な機械学習。必ずしも精度向上を保証しません。

学習数不足または検証未達の段階は有効化しません。`fof2_tec_mhz` はその時点で有効な最上位段階の値、`fof2_physics_mhz`, `fof2_empirical_mhz`, `fof2_ai_mhz` は段階ごとの**発表時点の**値として別記します。高度別Neは従来の条件付きTEC一様倍率補正のままです。AI/経験補正によるNe(h)やhmF2の物理的修正はしていません。

## 導入

1. ZIPを解凍。
2. 中の `.github/`, `scripts/`, `docs/`, `tests/` をGitHub Desktopで管理している`SWIFT-ION`リポジトリ直下へ**フォルダを統合して上書き**。
3. `README-INSTALL.md` は導入メモとして自由に保存。
4. Commit: `Add leakage-safe three-stage TEC-linked foF2 calibration and skill`
5. Push後、GitHub Actions内の以下を確認：
   - `Prepare rolling-year archive branch`
   - `Read NOAA Kp forecast and observed F10.7 for optional foF2 predictors`
   - `Train leakage-safe empirical and nonlinear ML foF2 calibration`
   - `Build 30-minute ionosphere forecast cinema`
   - `Record paired TEC-linked foF2 skill (365 days)`
   - `Evaluate physics empirical and AI foF2 stages prospectively (365 days)`
   - `Commit 365-day history to dedicated branch`
   - `Deploy GitHub Pages`
6. 公開画面：
   - `https://sgsy4c2zh7-tech.github.io/SWIFT-ION/nict_compare.html`（TEC連動foF2の4地点比較、NICT観測はユーザー取込CSV）
   - `https://sgsy4c2zh7-tech.github.io/SWIFT-ION/year.html`（従来IRI比較、TEC比較、3段階的中率）

## 自動生成するJSON/CSV

- `docs/ion_forecast.json`: 30分ごと・地点ごとに各段階の発表値と選択された段階
- `docs/fof2_drivers.json`: NOAA予報Kp、発表時点までのF10.7実測値（未取得はnull）
- `docs/fof2_calibration.json`: 検証条件、経験係数、AI係数、学習状況（不足時は `PHYSICS_ONLY`）
- `docs/tec_skill.json`: 既存の同時刻・同地点のIRI vs TEC連動foF2の公平な比較
- `docs/fof2_stage_skill.json`: 物理・経験・AIの的中率（誤差±1MHz以内）、N、MAE、RMSE、Bias、同一観測ペアでの改善量
- `docs/fof2_stage_daily.csv`, `docs/fof2_stage_monthly.csv`: 時刻・予測リードタイムごとの段階別集計

**重要**：3段階の的中率は、導入後の予報発表値を`swift-ion-history`ブランチの`tec_outlooks`に保存し、後から取得したGIRO/KC2Gイオノゾンデ観測を`tec_matches`に照合したもの。古い予報を遡及計算して的中率を捏造しません。発表前に見えていない実測値を学習や予報入力に使用しません。推定値がない段階は欠測扱いです。観測点が非常に少ない可能性があります。

## workflowへの影響

GitHub ActionsのNOAA取得、ISEE、元のSWIFT-TEC、IRI/TEC動画、元のIRI365日履歴のステップはそのままです。**既存の年次履歴ブランチ準備を前倒し**して、古い観測照合済みデータだけで学習した後、当日の30分予報を発行します。新しい段階別検証は後段の365日履歴Push前に行います。

`contents: write`と`swift-ion-history`ブランチへのPush権限が必要です。実行可能性とデータ量に応じてAI段階の起動までは日数を要します。

## モデルと利用上の注意

- TECは電子密度の柱積分で、TEC単体からNmF2/foF2の一意な解は得られません。IRI鉛直形状を仮定した**研究用**補正です。
- `foF2`は臨界周波数であり、MUFや実際の航空機HF通信可否ではありません。
- KpはNOAA「predicted」区間だけを、F10.7は既知の最近の観測値を持続として使います。未来のF10.7観測を予報で利用しません。
- 観測値の利用条件（GIRO/INGV/KC2G、CC BY-NC-SA 4.0や各局のクレジット）を守ってください。非商用研究向け。
- GitHub Actions本番、外部NOAA APIの応答、ブラウザでのPages描画は環境内では確認できていません。Pythonユニットテスト・YAML・JS構文・ローカル模擬ブラウザ検証のみです。

## ローカル検査

`python -m unittest discover -s tests -v`

従来の検証ファイルには手を加えません。今回追加した `tests/test_fof2_ml.py` も同じ検証コマンドで実行されます。
