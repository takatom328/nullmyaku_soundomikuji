# nullmyaku_soundomikuji

音声と身体の動きから特徴量を抽出し、クラウドAIで意味づけしておみくじ文を生成するプロジェクトです。Jetson Nano を中枢にし、M5Stack IMU、USBマイク、サーマルプリンタ、ブラウザ可視化を組み合わせる構成を想定しています。

## Current Status

- 仕様書 v0.2 を [`docs/spec.md`](docs/spec.md) に整理済み
- Jetson 側の基本ディレクトリ構成を作成済み
- 音声、IMU、状態推定、AI、プリンタ、Web の各モジュールに初期スキャフォールドを追加済み
- `python3 -m jetson.main` でプレースホルダ実行を確認済み

## Directory Structure

```text
docs/       Project specification
jetson/     Core application on Jetson Nano
m5stack/    M5Stack-side firmware scaffold
```

## Next Steps

1. Jetson の音声特徴量抽出を実装する
2. M5Stack から Jetson への IMU 通信を接続する
3. Responses API に特徴量 JSON を送る AI クライアントを実装する
4. サーマルプリンタ実機へ出力を接続する
