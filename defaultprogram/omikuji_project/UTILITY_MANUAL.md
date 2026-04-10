# Star Utility Manual

対象ファイル: `omikuji_project/star_util.py`

## 1. 目的

`star_util.py` は、Raspberry Pi + Star TSP100IIU 環境で、通常プリンターのように運用するためのCLIユーティリティです。  
CUPS操作、印刷、設定反映、プロファイル管理、診断を一つにまとめています。

## 2. 基本コマンド

```bash
cd /home/tt18/omikuji_project
/home/tt18/omikuji_env/bin/python star_util.py --help
```

共通:
- `--printer star` で対象キューを指定（デフォルトは `star`）

主なサブコマンド:
- `status`: プリンター状態確認
- `queues`: キュー一覧
- `jobs`: ジョブ一覧
- `list-options`: CUPSオプション一覧
- `set-options`: CUPSオプション設定
- `print-file`: ファイル印刷
- `print-text`: テキスト印刷（`test_print.py` 経由）
- `test`: テストページ印刷

## 3. 診断とドライバー管理

```bash
# 環境診断
/home/tt18/omikuji_env/bin/python star_util.py --printer star doctor

# ドライバー再ビルド/再導入（ソース配置済み前提）
/home/tt18/omikuji_env/bin/python star_util.py install-driver --use-sudo
```

## 4. TSP100IIU専用プリセット

公式Tipsの `.dat` を raw 送信して、BackFeed/Compression設定を反映します。

```bash
# 一覧
/home/tt18/omikuji_env/bin/python star_util.py tsp100iiu-list

# 適用例
/home/tt18/omikuji_env/bin/python star_util.py --printer star tsp100iiu-apply --preset compression-75
```

適用後はプリンター電源再投入推奨。

## 5. プロファイル運用

```bash
# 現在設定保存
/home/tt18/omikuji_env/bin/python star_util.py --printer star profile-save --name prod_default

# 保存一覧
/home/tt18/omikuji_env/bin/python star_util.py profile-list

# 適用
/home/tt18/omikuji_env/bin/python star_util.py --printer star profile-apply --name prod_default
```

保存先:
- `omikuji_project/profiles/*.json`

## 6. Windows設定の参照

Windowsドライバー配布物の `escpos.xml` / `default config.xml` を要約できます。

```bash
/home/tt18/omikuji_env/bin/python star_util.py win-xml-summary '/home/tt18/Downloads/tsp100_v770/Windows/ConfigurationSettingFiles/TSP100ECO/escpos.xml'
```

## 7. よく使う実運用手順

```bash
cd /home/tt18/omikuji_project
/home/tt18/omikuji_env/bin/python star_util.py --printer star doctor
/home/tt18/omikuji_env/bin/python star_util.py --printer star profile-apply --name prod_default
/home/tt18/omikuji_env/bin/python star_util.py --printer star test --mode image --layout horizontal --orientation portrait
```

