import sounddevice as sd
import numpy as np
import time

SAMPLERATE = 44100
BLOCKSIZE = 1024
BANDS = 16

latest_bands = np.zeros(BANDS)

def callback(indata, frames, time_info, status):
    global latest_bands

    if status:
        print(status)

    audio = indata[:, 0]

    fft_vals = np.abs(np.fft.rfft(audio))
    fft_vals = fft_vals[:len(fft_vals)]

    band_size = len(fft_vals) // BANDS
    bands = []

    for i in range(BANDS):
        start = i * band_size
        end = (i + 1) * band_size
        if end > len(fft_vals):
            end = len(fft_vals)
        if end > start:
            bands.append(np.mean(fft_vals[start:end]))
        else:
            bands.append(0.0)

    latest_bands = np.log1p(np.array(bands))

stream = sd.InputStream(
    channels=1,
    samplerate=SAMPLERATE,
    blocksize=BLOCKSIZE,
    callback=callback
)

with stream:
    print("Listening... Ctrl+C で終了")
    while True:
        lines = []
        for v in latest_bands:
            bar_len = int(min(40, v * 8))
            lines.append("{:<40}".format("#" * bar_len))
        print("\033[2J\033[H", end="")
        print("16-band FFT monitor")
        for i, line in enumerate(lines):
            print("{:02d}: {}".format(i, line))
        time.sleep(0.05)
