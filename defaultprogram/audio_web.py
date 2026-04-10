from flask import Flask, jsonify, Response
import sounddevice as sd
import numpy as np
import threading
import time

app = Flask(__name__)

SAMPLERATE = 44100
BLOCKSIZE = 1024
BANDS = 16

latest_bands = np.zeros(BANDS)
latest_volume = 0.0
latest_centroid = 0.0
lock = threading.Lock()

freqs = np.fft.rfftfreq(BLOCKSIZE, d=1.0 / SAMPLERATE)

HTML_PAGE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Audio Visualizer</title>
  <style>
    body {
      font-family: sans-serif;
      background: #111;
      color: #eee;
      margin: 20px;
    }
    h1 {
      font-size: 24px;
    }
    .info {
      margin-bottom: 16px;
      font-size: 18px;
    }
    .bars {
      display: flex;
      align-items: flex-end;
      height: 300px;
      border: 1px solid #555;
      padding: 10px;
      gap: 6px;
      background: #1a1a1a;
    }
    .bar-wrap {
      flex: 1;
      display: flex;
      align-items: flex-end;
      justify-content: center;
      height: 100%;
    }
    .bar {
      width: 100%;
      background: #4fc3f7;
      min-height: 2px;
    }
    .labels {
      display: flex;
      gap: 6px;
      margin-top: 6px;
    }
    .label {
      flex: 1;
      text-align: center;
      font-size: 12px;
      color: #aaa;
    }
  </style>
</head>
<body>
  <h1>Jetson Nano Audio Visualizer</h1>
  <div class="info">
    <div>Volume: <span id="volume">0</span></div>
    <div>Centroid: <span id="centroid">0</span> Hz</div>
  </div>

  <div class="bars" id="bars"></div>
  <div class="labels" id="labels"></div>

  <script>
    const bandCount = 16;
    const barsContainer = document.getElementById("bars");
    const labelsContainer = document.getElementById("labels");
    const barElems = [];

    for (let i = 0; i < bandCount; i++) {
      const wrap = document.createElement("div");
      wrap.className = "bar-wrap";

      const bar = document.createElement("div");
      bar.className = "bar";
      bar.style.height = "2px";

      wrap.appendChild(bar);
      barsContainer.appendChild(wrap);
      barElems.push(bar);

      const label = document.createElement("div");
      label.className = "label";
      label.textContent = i;
      labelsContainer.appendChild(label);
    }

    async function updateData() {
      try {
        const res = await fetch("/data");
        const data = await res.json();

        document.getElementById("volume").textContent = data.volume.toFixed(5);
        document.getElementById("centroid").textContent = data.centroid.toFixed(1);

        const low = data.bands.slice(0, 5).reduce((a, b) => a + b, 0);
        const mid = data.bands.slice(5, 10).reduce((a, b) => a + b, 0);
        const high = data.bands.slice(10, 16).reduce((a, b) => a + b, 0);

        for (let i = 0; i < bandCount; i++) {
          const v = data.bands[i];
          const px = Math.max(2, Math.min(280, v * 40));
          barElems[i].style.height = px + "px";

          if (i < 5) {
            barElems[i].style.background = "#ef5350";
          } else if (i < 10) {
            barElems[i].style.background = "#ffee58";
          } else {
            barElems[i].style.background = "#66bb6a";
          }
        }

        document.body.style.backgroundColor =
          `rgb(${Math.min(40, low * 3)}, ${Math.min(40, mid * 2)}, ${Math.min(40, high * 3)})`;
      } catch (e) {
        console.log(e);
      }
    }

    setInterval(updateData, 50);
    updateData();
  </script>
</body>
</html>
"""

def audio_callback(indata, frames, time_info, status):
    global latest_bands, latest_volume, latest_centroid

    if status:
        print(status)

    audio = indata[:, 0]

    volume = np.sqrt(np.mean(audio * audio))

    fft_vals = np.abs(np.fft.rfft(audio))
    fft_sum = np.sum(fft_vals)

    if fft_sum > 0:
        centroid = np.sum(freqs * fft_vals) / fft_sum
    else:
        centroid = 0.0

    band_size = len(fft_vals) // BANDS
    bands = []

    for i in range(BANDS):
        start = i * band_size
        end = (i + 1) * band_size

        if i == BANDS - 1:
            end = len(fft_vals)

        if end > start:
            band_val = np.mean(fft_vals[start:end])
        else:
            band_val = 0.0

        bands.append(band_val)

    bands = np.array(bands)
    bands = np.log1p(bands)

    with lock:
        latest_volume = float(volume)
        latest_centroid = float(centroid)
        latest_bands = bands

def audio_worker():
    stream = sd.InputStream(
        channels=1,
        samplerate=SAMPLERATE,
        blocksize=BLOCKSIZE,
        callback=audio_callback
    )

    with stream:
        print("Audio stream started")
        while True:
            time.sleep(1)

@app.route("/")
def index():
    return Response(HTML_PAGE, mimetype="text/html")

@app.route("/data")
def data():
    with lock:
        return jsonify({
            "volume": latest_volume,
            "centroid": latest_centroid,
            "bands": latest_bands.tolist()
        })

if __name__ == "__main__":
    t = threading.Thread(target=audio_worker)
    t.daemon = True
    t.start()

    print("Open http://<jetson_ip>:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
