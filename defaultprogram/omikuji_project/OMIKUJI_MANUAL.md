# Omikuji Manual

対象ファイル:
- `omikuji_project/omikuji.py`
- `omikuji_project/test_print.py`

## 1. 全体構成

- `omikuji.py`: おみくじ文面を生成し、必要なら印刷実行
- `test_print.py`: 印字エンジン（CUPS送信 + 画像レンダリング）

フロー:
1. `omikuji.py` が文面を作る
2. 特殊トークン（タイトル/運勢/鳥居/QR）を埋める
3. `test_print.py` がトークンを画像描画
4. `lp`/`lpr` で `star` キューへ送信

## 2. 実行方法

```bash
cd /home/tt18/omikuji_project

# 画面表示のみ
/home/tt18/omikuji_env/bin/python omikuji.py

# 固定結果で確認
/home/tt18/omikuji_env/bin/python omikuji.py --seed 7

# 印刷
/home/tt18/omikuji_env/bin/python omikuji.py --print --printer star
```

## 3. 現在のデザイン仕様

- 神社名: `ぬるみゃく神社`
- タイトル: 幅に合わせて自動拡大・中央寄せ
- 運勢: 拡大・中央寄せ
- 鳥居: 文字アートではなく図形描画（崩れ対策）
- QRコード: 最下部に `https://www.yahoo.co.jp/` を出力
- フォント: `NotoSansCJK-Regular.ttc` 優先

## 4. 特殊トークン仕様

`omikuji.py` が生成し、`test_print.py` が解釈して描画します。

- `[[TITLE:文字列]]`
  - 大きめフォントで中央描画
- `[[FORTUNE:文字列]]`
  - 運勢行をさらに強調して中央描画
- `[[TORII]]`
  - 鳥居図形を描画
- `[[QRCODE:URL]]`
  - URLのQRコードを下部中央に描画

## 5. 文面を変える場所

主に `omikuji.py` を編集します。

- 運勢の確率: `FORTUNE_WEIGHTS`
- 各項目文言: `WISH`, `BUSINESS`, `STUDY`, `LOVE`
- 補助文言: `LUCKY_ITEMS`, `ADVICE`
- 神社名: `SHRINE_NAME`
- QRリンク: `DEFAULT_QR_URL`

## 6. レイアウトを変える場所

主に `test_print.py` を編集します。

- タイトルサイズロジック: `load_title_font`
- 運勢サイズロジック: `load_fortune_font`
- 鳥居描画: `draw_torii`
- QR描画: `draw_qrcode`
- 余白/行間: `margin`, `line_spacing`

## 7. 文字化け（□）対策

対策済み:
- `fonts-noto-cjk` 導入
- `test_print.py` のフォント優先順位をNoto CJK優先へ変更
- `omikuji.py` 印刷時に `--font-path /usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc` を明示

もし再発した場合:
1. `fc-list :lang=ja family file` でフォント確認
2. `DEFAULT_PRINT_FONT` を有効な日本語フォントへ変更

## 8. 将来拡張の例

- `omikuji.py` に `--qr-url` 引数を追加（リンク差し替え）
- `omikuji.py` に `--shrine-name` 引数を追加（神社名差し替え）
- `test_print.py` にロゴ画像トークンを追加（`[[IMAGE:path]]`）

