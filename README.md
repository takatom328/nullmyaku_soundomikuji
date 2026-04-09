# nullmyaku_soundomikuji

音声と身体の動きから特徴量を抽出し、クラウドAIで意味づけしておみくじ文を生成するプロジェクトです。Jetson Nano を中枢にし、M5Stack IMU、USBマイク、Raspberry Pi の印刷システム、ブラウザ可視化を組み合わせる構成を想定しています。

## Current Status

- 仕様書 v0.3 を [`docs/spec.md`](docs/spec.md) に整理済み
- Jetson 側の基本ディレクトリ構成を作成済み
- 音声、IMU、状態推定、AI、プリンタ、Web の各モジュールに初期スキャフォールドを追加済み
- Jetson から Raspberry Pi 印刷サーバへ HTTP で印刷ジョブを送る経路を追加済み
- Flask ダッシュボードの API とブラウザ表示を追加済み
- Jetson 側にローカル埋め込み（audio/imu）+ 融合埋め込み + 状態分類を追加済み
- AI 生成は `local / cloud / hybrid` を切替可能（クラウド失敗時のローカル fallback 対応）
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
4. Raspberry Pi 側の `/print-jobs` 受信仕様に合わせて印刷連携を仕上げる

## Printer Relay Configuration

Jetson 側は Raspberry Pi の印刷サービスへ HTTP でジョブを送る想定です。Ethernet と Wi-Fi のどちらでも、IP 到達できれば同じ設定で動かせます。

```bash
export PRINTER_TRANSPORT=http
export PRINTER_ENDPOINT_URL=http://raspberrypi.local:8000/print-jobs
export PRINTER_TIMEOUT_SEC=5.0
export PRINTER_SOURCE_DEVICE=jetson-nano
export PRINTER_AUTH_TOKEN=
```

デフォルトでは `stdout` を使うので、ローカル開発中はネットワークなしでも確認できます。

## Dashboard

Flask ダッシュボードを使うと、Jetson と同じネットワーク上の別端末ブラウザから特徴量を確認できます。

```bash
python3 -m pip install -r requirements.txt
export AUDIO_BACKEND=arecord
export WEB_DASHBOARD_ENABLED=1
export WEB_DASHBOARD_HOST=0.0.0.0
export WEB_DASHBOARD_PORT=5000
python3 -m jetson.main
```

別端末からは `http://<jetson-ip>:5000` にアクセスします。

## AI Mode (Local / Cloud / Hybrid)

デフォルトは `AI_MODE=local` で、Jetson のローカル推論結果からローカルテンプレ文を生成します。

```bash
export AI_MODE=local
```

クラウド生成を使う場合:

```bash
export AI_MODE=cloud
export OPENAI_API_KEY=sk-...
export AI_MODEL=gpt-4.1-mini
export OPENAI_BASE_URL=https://api.openai.com/v1
```

ハイブリッド（推奨）:

```bash
export AI_MODE=hybrid
export OPENAI_API_KEY=sk-...
export AI_FALLBACK_ENABLED=1
```

このとき、クラウド失敗時はローカル文生成へ自動でフォールバックします。

`.env` をプロジェクト直下に置けば、`python3 -m jetson.main` 起動時に自動読込されます。
（シェルで `export` 済みの値があれば、そちらが優先されます）

```text
OPENAI_API_KEY=sk-...
AI_MODE=hybrid
AI_MODEL=gpt-4.1-mini
AI_ENDPOINT=responses
OPENAI_BASE_URL=https://api.openai.com/v1
AI_FALLBACK_ENABLED=1
```

`.env` の場所を変えたい場合は `APP_DOTENV_PATH` を使えます。

```bash
export APP_DOTENV_PATH=/path/to/your.env
python3 -m jetson.main
```

## Local Model Backend

状態推定は `LOCAL_MODEL_BACKEND` で切替できます。

- `prototype`（デフォルト）: 現在の埋め込みプロトタイプ分類
- `onnx`: ローカルONNXモデルで分類（失敗時は prototype に自動フォールバック）

```bash
export LOCAL_MODEL_BACKEND=prototype
export LOCAL_MODEL_CONFIDENCE_THRESHOLD=0.64
```

ONNXを使う場合:

```bash
export LOCAL_MODEL_BACKEND=onnx
export LOCAL_MODEL_PATH=/home/jetson/project/null2myakumyaku/models/state_classifier.onnx
export LOCAL_MODEL_LABELS=energetic,delicate,focused,resonant,open,unstable
```

Dashboard の `model:` チップと `Embed Source` に、`prototype` / `onnx` が表示されます。

## Build Dataset from Sessions

セッション保存ファイル（`sessions/*.json`）から、ローカルモデル学習用データを作れます。

```bash
python3 tools/build_local_model_dataset.py \
  --input-dir sessions \
  --output-dir training
```

出力:

- `training/session_dataset.jsonl`
- `training/labels_template.csv`

`labels_template.csv` の `manual_label` を埋めて、次の学習ステップへ使います。

## Session Control (Start / Stop)

M5Stack の `event=start/stop` を使って、Jetson 側でセッション単位に集約します。
セッション完了時にのみ AI 生成と印刷ジョブ送信を行います。

- `BtnA` -> `start`
- `BtnB` -> `stop`
- `SESSION_AUTO_STOP_SEC` 到達でも自動終了

```bash
export SESSION_ENABLED=1
export SESSION_REQUIRE_START_EVENT=1
export SESSION_AUTO_STOP_SEC=10
export SESSION_MIN_DURATION_SEC=1.0
export SESSION_COOLDOWN_SEC=0.8
export SESSION_ARCHIVE_ENABLED=1
export SESSION_ARCHIVE_DIR=sessions
export SESSION_ARCHIVE_PRETTY=0
```

`SESSION_REQUIRE_START_EVENT=0` にすると、常時セッション（自動開始）モードになります。
セッション完了時は `SESSION_ARCHIVE_DIR` に JSON ログが保存されます。

## IMU (M5Stack -> Jetson)

Jetson 側は UDP 受信を使います。M5Stack から JSON を `IMU_UDP_PORT` へ送ってください。

```bash
export IMU_TRANSPORT=udp
export IMU_UDP_HOST=0.0.0.0
export IMU_UDP_PORT=9001
```

M5Stack スケッチ例は [imu_sender.ino](/Users/tomohiro/Library/Mobile%20Documents/com~apple~CloudDocs/creation/null2myakumyaku/m5stack/imu_sender.ino) を使えます。

M5Stack Core2 では microSD の `/imu_config.txt` から送信先設定を読み込めます。

```text
WIFI_SSID=your-ssid
WIFI_PASS=your-password
JETSON_IP=192.168.1.120
JETSON_PORT=9001
SEND_INTERVAL_MS=20
```

読み込みに成功すると Core2 の画面に `ConfigSD: LOADED` と表示されます。
Core2 画面右側には IMU の3D風ビュー（X/Y/Z軸と加速度ベクトル）が表示されます。

Jetson 側で受信確認だけしたい場合は、別端末からテストパケットを送れます。

```bash
python3 - <<'PY'
import json, socket, time
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for i in range(30):
    p = {"timestamp": time.time(), "ax": 0.1, "ay": 0.2, "az": 0.98, "acc_norm": 1.01, "event": "none"}
    s.sendto(json.dumps(p).encode("utf-8"), ("127.0.0.1", 9001))
    time.sleep(0.02)
PY
```

## Jetson Venv Setup

Jetson Nano では `venv` の使用をおすすめします。音声入力はデフォルトで `arecord` バックエンドを優先します。

```bash
cd ~/project/null2myakumyaku
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

USB マイクが接続済みなら、このまま起動できます。

```bash
cd ~/project/null2myakumyaku
source .venv/bin/activate
export AUDIO_BACKEND=arecord
unset AUDIO_INPUT_DEVICE
export WEB_DASHBOARD_ENABLED=1
export WEB_DASHBOARD_HOST=0.0.0.0
export WEB_DASHBOARD_PORT=5000
python3 -m jetson.main
```

必要なら入力デバイスを固定できます。

```bash
export AUDIO_INPUT_DEVICE="USB"
```

`arecord` バックエンドを使う場合は ALSA デバイス名が使えます。

```bash
arecord -l
export AUDIO_ARECORD_DEVICE=hw:2,0
```

`AUDIO_INPUT_DEVICE` は `sounddevice` 用です。`arecord` バックエンドでは使いません。

`sounddevice` を明示的に使いたい場合のみ追加インストールします。

```bash
python3 -m pip install "numpy<1.20" "sounddevice<0.5"
export AUDIO_BACKEND=sounddevice
```
