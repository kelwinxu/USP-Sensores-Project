import sys
import numpy as np
import sounddevice as sd
import constants as c
import functions as f

# --- Settings ---
SAMPLE_RATE = c.SAMPLE_RATE
D0 = c.D0
D1 = c.D1
D2 = c.D2
FRAME_LEN = c.FRAME_LEN
STEP_SIZE = FRAME_LEN//4                # Sliding step (1/4 of a frame) to align with D2 automatically
NOISE_THRESHOLD = c.NOISE_THRESHOLD

print("=== CONTINUOUS ECHO HIDING RECEIVER ===")
print("Listening to microphone... Waiting for secret messages.")
print("Press Ctrl+C to stop.\n")
print("Decoded Text: ", end="", flush=True)

# Rolling audio buffer of size FRAME_LEN
audio_buffer = np.zeros(FRAME_LEN)
with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32") as stream:
    try:
        while True:
            # 1. Slide the window by STEP_SIZE (FRAME_LEN//4 samples) while searching for 'D2'
            new_data, _ = stream.read(STEP_SIZE)
            audio_buffer = np.concatenate([audio_buffer[STEP_SIZE:], new_data[:, 0]])

            c0, c1, c2 = f.analyze_frame(audio_buffer)

            # Check if D2 is clearly stronger than D0 and D1 (threshold avoids noise triggers)
            if c2 > c0 and c2 > c1 and (c2 - max(c0, c1)) > NOISE_THRESHOLD:
                # Take one more step to see if D2 is still rising (center alignment)
                peek_data, _ = stream.read(STEP_SIZE)
                peek_buffer = np.concatenate([audio_buffer[STEP_SIZE:], peek_data[:, 0]])
                _, _, next_c2 = f.analyze_frame(peek_buffer)

                if next_c2 > c2:
                    # The peak was one step ahead; align buffer there
                    audio_buffer = peek_buffer
                    bits_Lookahead = None
                else:
                    # Current audio_buffer was the exact center! Save peek_data for bit 1
                    bits_Lookahead = peek_data[:, 0]

                # 2. Now we are aligned! Read the next 8 full frames (8 bits = 1 character)
                bits = ""
                for bit_idx in range(8):
                    if bit_idx == 0 and bits_Lookahead is not None:
                        # We already read 2048 samples during the peek; read the remaining 6144
                        rest_data, _ = stream.read(FRAME_LEN - STEP_SIZE)
                        bit_frame = np.concatenate([bits_Lookahead, rest_data[:, 0]])
                    else:
                        full_data, _ = stream.read(FRAME_LEN)
                        bit_frame = full_data[:, 0]

                    b0, b1, _ = f.analyze_frame(bit_frame)
                    bits += "1" if b1 > b0 else "0"

                #Keep buffer updated with the last frame read
                audio_buffer = bit_frame.copy()

                # 3. Convert the 8 bits into an ASCII character and print it live
                ascii_code = int(bits, 2)
                if 32 <= ascii_code <= 126:
                    sys.stdout.write(chr(ascii_code))
                else:
                    sys.stdout.write("?")
                sys.stdout.flush()

    except KeyboardInterrupt:
        print("\nReceiver stopped.")