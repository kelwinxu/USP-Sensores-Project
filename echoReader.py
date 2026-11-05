import wave
import numpy as np
import constants as c
import functions as f

# --- Settings ---
INPUT_FILE = "echo_stego_music.wav"

D0 = c.D0
D1 = c.D1
D2 = c.D2
FRAME_LEN = c.FRAME_LEN

def load_wav(filename):
    """Load a 16-bit WAV audio file and return normalized floating-point mono audio."""
    with wave.open(filename, "rb") as wav:
        channels = wav.getnchannels()           # Channels: mono=1, stereo=2
        n_frames = wav.getnframes()             # Number of samples
        raw_bytes = wav.readframes(n_frames)

    # Convert 16-bit signed PCM little-endian (generator & default Audacity) to float
    audio = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float64) / 32768.0

    # If Audacity exported as stereo (2 channels), average them into mono
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)

    return audio


def decode_message(signal):
    """Extract symbols ('0', '1', '2') using Real Cepstrum and reconstruct the text."""
    total_frames = len(signal) // FRAME_LEN
    symbols = []

    # 1. Detect the strongest echo (D0, D1, or D2) in each frame
    for k in range(total_frames):
        frame = signal[k * FRAME_LEN : (k + 1) * FRAME_LEN]
    
        c0, c1, c2 = f.analyze_frame(frame)

        # Whichever delay has the highest peak wins (with noise threshold for D2)
        if c2 >= c0 and c2 >= c1 and (c2 - max(c0, c1)) >= c.NOISE_THRESHOLD:
            symbols.append("2")
        elif c1 >= c0:
            symbols.append("1")
        else:
            symbols.append("0")

    symbol_str = "".join(symbols)

    # 2. Find every '2' (start marker) and read the next 8 bits as a character
    chars = []
    i = 0
    while i < len(symbol_str):
        if symbol_str[i] == "2":
            # Grab the 8 bits right after the '2' marker
            byte_str = symbol_str[i + 1 : i + 9]
            if len(byte_str) == 8:
                # Guarantee only '0' and '1' are passed to int() in case of noise
                clean_bits = ""
                for b in byte_str:
                    clean_bits += "1" if b == "1" else "0"

                ascii_code = int(clean_bits, 2)
                chars.append(chr(ascii_code))

            i += 9  # Jump to the next potential character (1 marker + 8 bits)
        else:
            i += 1  # Keep searching for the '2' start marker

    text = "".join(chars)
    return symbol_str, text


print("=== ECHO HIDING AUDIO DECODER ===")
filename = input(f"Enter WAV file to decode (press Enter for '{INPUT_FILE}'): ")

if not filename:
    filename = INPUT_FILE

print(f"\nLoading '{filename}'...")
audio = load_wav(filename)

print("Analyzing echoes and extracting message...")
symbols, decoded_text = decode_message(audio)
if c.DEBUG:
    debug_text = ""
    for char in symbols:
        if char == "2": debug_text += " "
        debug_text += char
    print(f"\nDecoded Symbols: {debug_text}")
print(f"Decoded Message: {decoded_text}")