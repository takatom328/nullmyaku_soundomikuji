import sounddevice as sd
import numpy as np
import time

SAMPLERATE = 44100
BLOCKSIZE = 1024

def callback(indata, frames, time_info, status):
    if status:
        print(status)

    audio = indata[:, 0]
    vol = np.sqrt(np.mean(audio * audio))

    bar_len = int(min(60, vol * 1000))
    bar = "#" * bar_len
    print("\r{:<60} {:.5f}".format(bar, vol), end="")

stream = sd.InputStream(
    channels=1,
    samplerate=SAMPLERATE,
    blocksize=BLOCKSIZE,
    callback=callback
)

with stream:
    print("Listening... Ctrl+C で終了")
    while True:
        time.sleep(0.1)
