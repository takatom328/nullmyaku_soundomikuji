import sounddevice as sd
import numpy as np
import matplotlib.pyplot as plt
import time

SAMPLERATE = 44100
BLOCKSIZE = 1024
BANDS = 16

latest_bands = np.zeros(BANDS)
latest_volume = 0.0
latest_centroid = 0.0

# 周波数軸（rfft用）
freqs = np.fft.rfftfreq(BLOCKSIZE, d=1.0 / SAMPLERATE)

def callback(indata, frames, time_info, status):
    global latest_bands
    global latest_volume
    global latest_centroid

    if status:
        print(status)

    audio = indata[:, 0]

    # 音量（RMS）
    volume = np.sqrt(np.mean(audio * audio))
    latest_volume = volume

    # FFT
    fft_vals = np.abs(np.fft.rfft(audio))

    # スペクトル重心
    fft_sum = np.sum(fft_vals)
    if fft_sum > 0:
        centroid = np.sum(freqs * fft_vals) / fft_sum
    else:
        centroid = 0.0
    latest_centroid = centroid

    # 16帯域に分割
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

    # 見やすくするため対数圧縮
    bands = np.log1p(bands)

    latest_bands = bands

def main():
    global latest_bands
    global latest_volume
    global latest_centroid

    plt.ion()

    fig, ax = plt.subplots()
    x = np.arange(BANDS)
    bars = ax.bar(x, np.zeros(BANDS), align='center')

    ax.set_xlim(-0.5, BANDS - 0.5)
    ax.set_ylim(0, 8)
    ax.set_xlabel("Band")
    ax.set_ylabel("Level")
    ax.set_title("Real-time 16-band Audio Spectrum")

    info_text = ax.text(
        0.02, 0.95, "",
        transform=ax.transAxes,
        verticalalignment='top'
    )

    stream = sd.InputStream(
        channels=1,
        samplerate=SAMPLERATE,
        blocksize=BLOCKSIZE,
        callback=callback
    )

    with stream:
        print("Listening... Close the graph window or Ctrl+C to stop")

        while True:
            for i in range(BANDS):
                bars[i].set_height(latest_bands[i])

            info_text.set_text(
                "Volume (RMS): {:.5f}\nCentroid: {:.1f} Hz".format(
                    latest_volume, latest_centroid
                )
            )

            fig.canvas.draw()
            fig.canvas.flush_events()
            time.sleep(0.03)

if __name__ == "__main__":
    main()
