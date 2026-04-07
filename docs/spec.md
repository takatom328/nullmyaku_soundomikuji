# 音と身体から未来を生成するおみくじシステム 仕様書 v0.2

## 1. 目的

人の声と身体の動きを入力として取得し、ローカルで特徴量を抽出したうえでクラウドAIが意味づけを行い、短い未来トピックとしてのおみくじ文を生成する。最終的な出力はサーマルプリンタで紙として返す。

## 2. コンセプト

```text
感覚入力（音 + 動き）
  -> 数値化（特徴量）
  -> 意味づけ（状態推定）
  -> 物語生成（未来）
  -> 物理出力（紙）
```

プロジェクトの核は「人の状態を測定する」のではなく、「感じ取って翻訳する」ことにある。

## 3. ハードウェア機能分担

### 3.1 M5Stack

人間とのインターフェースを担う。

- スタートボタン入力
- セッションの開始・終了イベント送信
- IMUの取得
- タイマー表示
- Jetsonへのデータ送信

想定出力:

```json
{
  "timestamp": 1712467200.123,
  "ax": 0.12,
  "ay": -0.03,
  "az": 0.98,
  "acc_norm": 1.02,
  "event": "start"
}
```

通信方式は `MQTT` を第一候補とし、軽量構成では `UDP` も選択肢とする。

### 3.2 Jetson Nano

システムの中枢を担う。

- USBマイクから音声取得
- RMS、FFT、帯域エネルギー、スペクトル重心、オンセット、リズム候補の抽出
- M5StackからのIMUデータ受信
- 音声特徴量とIMU特徴量の統合
- 中間状態の推定
- クラウドAIへの送信
- Web可視化
- サーマルプリンタ制御

### 3.3 サーマルプリンタ

結果を紙として物理化する。

- おみくじ本文の印刷
- タイトル、状態、日付を含むフォーマット整形

### 3.4 ブラウザ

開発・デモ時の補助UIを担う。

- スペクトラム表示
- 音量や重心の表示
- 状態推定結果の確認
- デバッグ情報の可視化

## 4. システム構成

```text
[M5Stack] -> [Jetson Nano] -> [Cloud AI]
                   |              |
                   +-> [Web UI]   |
                   +-> [Printer] <-+
```

## 5. 入力仕様

### 5.1 音声入力

- デバイス: USBマイク
- サンプリングレート: 44100 Hz
- ブロックサイズ: 1024
- 形式: モノラル

### 5.2 IMU入力

- センサー: 3軸加速度
- サンプリングレート: 50-100 Hz
- データ: `ax`, `ay`, `az`, `acc_norm`

### 5.3 セッション制御

- 開始: M5Stackボタン
- 終了: タイマーまたはボタン
- 計測時間: 5-10秒

## 6. 特徴量設計

### 6.1 音声特徴量

基本特徴量:

- RMS
- FFT
- 16帯域エネルギー

派生特徴量:

- スペクトル重心
- 低音 / 中音 / 高音の比率
- オンセット数
- リズム周期

### 6.2 IMU特徴量

- 加速度平均
- 加速度最大値
- 動きの頻度
- 周期性

### 6.3 統合特徴量

- 音量 x 動き量
- 音リズムと身体リズムの一致度
- エネルギー総量

## 7. 状態推定

中間状態は、音声特徴量とIMU特徴量を統合して推定する。

例:

| 状態 | 条件イメージ |
| --- | --- |
| energetic | 音量が高く、加速度も高い |
| delicate | 音量が低く、高域比率が高い |
| focused | リズムが安定している |
| unstable | リズムが揺らいでいる |
| open | 低域が強く、動きも大きい |

内部表現の例:

```json
{
  "energy": 0.8,
  "brightness": 0.6,
  "rhythm_stability": 0.4,
  "movement_intensity": 0.9,
  "state": "energetic"
}
```

## 8. クラウドAI連携

基本方針は、Jetson側で特徴量抽出を行い、クラウドAIは意味づけと文生成に集中させること。

送信データの例:

```json
{
  "session": {
    "started_at": "2026-04-07T12:00:00+09:00",
    "duration_sec": 8.2
  },
  "audio_features": {
    "rms": 0.31,
    "spectral_centroid": 1820.4,
    "band_energies": [0.1, 0.2, 0.4]
  },
  "imu_features": {
    "mean_acc_norm": 1.12,
    "peak_acc_norm": 1.95,
    "movement_frequency_hz": 1.8
  },
  "derived_state": {
    "energy": 0.78,
    "brightness": 0.54,
    "rhythm_stability": 0.43,
    "movement_intensity": 0.82,
    "state": "energetic"
  },
  "transcript": "optional short transcript"
}
```

Phase 1では `Responses API` に特徴量JSONと短い文字起こしを渡して、おみくじ文を返してもらう構成を第一候補とする。Realtimeによる双方向音声はPhase 3以降で検討する。

## 9. 出力仕様

サーマルプリンタの出力例:

```text
===========
  OMIKUJI
===========

STATE:
ENERGETIC

MESSAGE:
勢いはすでに始まっている。
迷いより先に、身体が答えを知っている。

-----------
2026-04-07 12:00
-----------
```

## 10. 処理フロー

1. M5Stackでセッション開始
2. 音声・IMU取得
3. 特徴量抽出
4. 状態推定
5. クラウドAIへ送信
6. おみくじ文受信
7. 印刷

## 11. 非機能要件

- 体験上の遅延は5秒以内を目標とする
- ネットワーク断時はローカル生成にフォールバックできる余地を残す
- LEDや音声出力など将来拡張に耐えられる分離構造にする

## 12. 開発フェーズ

### Phase 1

音のみの取得、特徴量抽出、Web可視化

### Phase 2

状態推定ルールのローカル実装

### Phase 3

サーマルプリンタ出力

### Phase 4

M5Stack統合

### Phase 5

クラウドAI接続

## 13. コード構造

```text
project/
├── docs/
│   └── spec.md
├── jetson/
│   ├── main.py
│   ├── audio/
│   │   ├── input.py
│   │   ├── fft.py
│   │   ├── features.py
│   │   └── rhythm.py
│   ├── imu/
│   │   ├── receiver.py
│   │   └── features.py
│   ├── fusion/
│   │   └── state_estimator.py
│   ├── ai/
│   │   └── client.py
│   ├── printer/
│   │   └── printer.py
│   ├── web/
│   │   ├── server.py
│   │   └── static/
│   │       └── index.html
│   └── utils/
│       ├── config.py
│       └── logger.py
└── m5stack/
    └── imu_sender.ino
```

## 14. 当面の実装優先順位

1. `jetson/audio/features.py` を具体化する
2. `jetson/fusion/state_estimator.py` にルールベース推定を入れる
3. `jetson/printer/printer.py` を実機I/Oに接続する
4. `jetson/ai/client.py` をResponses API送信へ置き換える
