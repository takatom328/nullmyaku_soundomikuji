# Raspberry Pi Print API Contract

Jetson Nano は印刷本文と最小限のメタデータを Raspberry Pi 側の印刷サービスへ送る。ネットワークは Ethernet / Wi-Fi のどちらでもよく、到達性があれば同じ API を利用できる。

## Endpoint

```text
POST /print-jobs
Content-Type: application/json
Authorization: Bearer <optional token>
```

エンドポイント例:

```text
http://raspberrypi.local:8000/print-jobs
```

## Request Body

```json
{
  "job_id": "6d8f4b5e-9ef3-413f-aac0-27d29d15c2d7",
  "job_type": "omikuji",
  "created_at": "2026-04-07T05:00:00+00:00",
  "source_device": "jetson-nano",
  "state": "energetic",
  "message": "勢いはすでに始まっている。",
  "ticket_text": "===========\n  OMIKUJI\n===========\n...",
  "format": "plain_text"
}
```

## Expected Response

成功時は `2xx` を返す想定。レスポンス本文は必須ではないが、最低限以下のどちらかがあると扱いやすい。

```json
{
  "accepted": true,
  "job_id": "6d8f4b5e-9ef3-413f-aac0-27d29d15c2d7"
}
```

または

```json
{
  "printed": true,
  "job_id": "6d8f4b5e-9ef3-413f-aac0-27d29d15c2d7"
}
```

## Jetson-side Environment Variables

```bash
PRINTER_TRANSPORT=http
PRINTER_ENDPOINT_URL=http://raspberrypi.local:8000/print-jobs
PRINTER_TIMEOUT_SEC=5.0
PRINTER_SOURCE_DEVICE=jetson-nano
PRINTER_AUTH_TOKEN=
```
