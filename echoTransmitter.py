import queue
import numpy as np
import sounddevice as sd
import constants as c
import functions as f

# --- Settings ---
SAMPLE_RATE = c.SAMPLE_RATE
BPM = c.BPM
D0 = c.D0
D1 = c.D1
D2 = c.D2
FRAME_LEN = c.FRAME_LEN
NOISE_THRESHOLD = c.NOISE_THRESHOLD
BASE_MELODY = c.ULTRASOUND              # Base melody
ALPHA = c.ALPHA                         # Echo volume (attenuation factor)
K = c.K                                 # Transition smoothing length
sd.default.device = "pulse"

# --- State Variables for Continuous Playback ---
bit_queue = queue.Queue()
melody = f.generate_melody(BASE_MELODY)
melody_len = len(melody)
pos = 0
history = np.zeros(D2)
prev_symbol = "0"


def audio_callback(outdata, frames, time_info, status):
    """Called automatically by the sound card every time it needs 8192 samples."""
    global pos, history, prev_symbol

    # 1. Fetch next chunk of music (fast numpy slicing)
    indices = (np.arange(FRAME_LEN) + pos) % melody_len
    chunk = melody[indices] + np.random.normal(0.0, 0.006, size=FRAME_LEN)
    pos = (pos + FRAME_LEN) % melody_len

    # 2. Get the next symbol from the queue (or '0' if queue is empty)
    if not bit_queue.empty():
        curr_symbol = bit_queue.get()
    else:
        curr_symbol = "0"

    # 3. Create the 3 delayed echoes using history + current chunk
    extended = np.concatenate([history, chunk])
    echo_zero = ALPHA * extended[D2 - D0 : D2 - D0 + FRAME_LEN]
    echo_one  = ALPHA * extended[D2 - D1 : D2 - D1 + FRAME_LEN]
    echo_two  = ALPHA * extended[0 : FRAME_LEN]

    # 4. Mix smoothly
    mix_0 = f.create_chunk_mixer(prev_symbol, curr_symbol, "0")
    mix_1 = f.create_chunk_mixer(prev_symbol, curr_symbol, "1")
    mix_2 = f.create_chunk_mixer(prev_symbol, curr_symbol, "2")

    stego_chunk = chunk + (echo_zero * mix_0) + (echo_one * mix_1) + (echo_two * mix_2)

    # 5. Save history for next frame and write to speaker buffer (shape: 8192 x 1)
    history = chunk[-D2:].copy()
    prev_symbol = curr_symbol
    outdata[:, 0] = stego_chunk.astype(np.float32)


print("=== CONTINUOUS ECHO HIDING TRANSMITTER ===")
print("Active Audio Device:", sd.query_devices(kind="output")["name"])
print("Playing music... Type a message and press Enter!")
print("Type 'exit' to stop.\n")

# blocksize=FRAME_LEN guarantees the callback always processes exactly 1 symbol (8192 samples)
with sd.OutputStream(
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype="float32",
    blocksize=FRAME_LEN,
    callback=audio_callback,
):
    while True:
        try:
            msg = input("Message > ")
            if msg.lower() == "exit":
                break

            if msg:
                symbols = f.text_to_bits(msg + " ")
                for s in symbols:
                    bit_queue.put(s)
                print(f"  [Queued {len(msg)} chars -> {bit_queue.qsize()} symbols remaining]")
        except (KeyboardInterrupt, EOFError):
            print("\nCtrl+C detectado! Fechando a stream e liberando o dispositivo...")
            break

print("Transmitter safely closed.")