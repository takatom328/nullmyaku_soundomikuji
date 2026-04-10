# Raspberry Pi 再現手順書（TSP100IIU + おみくじ）

この手順は、別の Raspberry Pi へ同じ印刷環境を再現するためのものです。

## 1. 前提

- OS: Raspberry Pi OS (64bit 推奨)
- プリンター: Star TSP100IIU（USB接続）
- 配布ファイル:
  - `star-cups-driver-rpi_1.0.0_arm64.deb`

## 2. 事前インストール

```bash
sudo apt-get update
sudo apt-get install -y cups python3 python3-pil python3-qrcode fonts-noto-cjk
```

必要ならCUPS有効化:

```bash
sudo systemctl enable cups
sudo systemctl start cups
```

## 3. パッケージ導入

```bash
sudo dpkg -i ./star-cups-driver-rpi_1.0.0_arm64.deb
```

依存解決が必要な場合:

```bash
sudo apt-get -f install -y
```

## 4. プリンターキュー作成

USB URI確認:

```bash
lpinfo -v
```

例（`usb://Star/TSP143%20(STR_T-001)` の場合）:

```bash
sudo lpadmin -x star || true
sudo lpadmin -p star -E -v 'usb://Star/TSP143%20(STR_T-001)' -m 'star/tsp143.ppd'
sudo lpoptions -d star
```

## 5. 動作確認

```bash
star-util-rpi --printer star doctor
star-util-rpi --printer star test --mode image --layout horizontal --orientation portrait
omikuji-rpi --print --printer star
```

## 6. 初期設定（任意）

TSP100IIU プリセット適用:

```bash
star-util-rpi tsp100iiu-list
star-util-rpi --printer star tsp100iiu-apply --preset backfeed-default
```

設定適用後は電源再投入推奨。

## 7. よく使う運用コマンド

```bash
# 状態確認
star-util-rpi --printer star status

# キュー設定一覧
star-util-rpi --printer star list-options

# おみくじ印刷
omikuji-rpi --print --printer star
```

## 8. トラブル時の確認

```bash
lsusb
lsusb -t
lpstat -t
lpoptions -p star -l
```

ポイント:
- `lpoptions -p star -l` が失敗する場合は、PPD/ドライバ導入を再確認
- 文字化け（□）が出る場合は `fonts-noto-cjk` の導入確認
