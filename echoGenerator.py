import math
import wave
import numpy as np
import constants as c
import functions as f
# --- Settings ---
OUTPUT_FILE = "echo_stego_music.wav"

SAMPLE_RATE = c.SAMPLE_RATE
BPM = c.BPM("MARIO")
D0 = c.D0
D1 = c.D1
D2 = c.D2
FRAME_LEN = c.FRAME_LEN
BASE_MELODY = c.MARIO                   # Base melody: list of (Note, Duration in beats)
ALPHA = c.ALPHA                         # Echo volume (attenuation factor)
K = c.K                                 # Transition smoothing length

def embed_message(audio, bits):
    """Hide the binary bits inside the audio using Echo Hiding."""
    total_frames = len(audio) // FRAME_LEN
    capacity_bits = total_frames - (total_frames % 9)

    if len(bits) > capacity_bits:
        print("Warning: Message is too long and will be truncated")
        bits = bits[:capacity_bits]
    else:
        # Pad the remaining capacity with trailing zeros
        missing_zeros = capacity_bits - len(bits)
        bits = bits + ("0" * missing_zeros)

    # Create delayed echo copies (for 0, 1, and 2)
    echo_zero = np.zeros_like(audio)
    echo_zero[D0:] = ALPHA * audio[:-D0]

    echo_one = np.zeros_like(audio)
    echo_one[D1:] = ALPHA * audio[:-D1]

    echo_two = np.zeros_like(audio)
    echo_two[D2:] = ALPHA * audio[:-D2]

    # Blend the original audio with the echoes based on the message bits
    mix_0 = f.create_mixer_signal(bits, FRAME_LEN, "0")
    mix_1 = f.create_mixer_signal(bits, FRAME_LEN, "1")
    mix_2 = f.create_mixer_signal(bits, FRAME_LEN, "2")
    region_length = capacity_bits * FRAME_LEN

    stego_audio = audio.copy()
    stego_audio[:region_length] = (
        audio[:region_length]
        + echo_zero[:region_length] * mix_0
        + echo_one[:region_length] * mix_1
        + echo_two[:region_length] * mix_2
    )

    return stego_audio


def save_wav(filename, audio):
    """Convert floating-point audio to 16-bit PCM and save as a .wav file."""
    clipped_audio = np.clip(np.round(audio * 32767.0), -32768, 32767)
    pcm_data = clipped_audio.astype(np.int16)

    with wave.open(filename, "wb") as wav_file:
        wav_file.setnchannels(1)          # 1 channel (Mono)
        wav_file.setsampwidth(2)          # 2 bytes per sample (16-bit)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(pcm_data.tobytes())


print("=== ECHO HIDING AUDIO GENERATOR ===")
message = input("Enter the secret message to hide in the audio: ")

if not message:
    message = "Default test message"
    print(f"No input provided. Using default: '{message}'")

# Convert text to binary string (0s and 1s)
bits = f.text_to_bits(message)
required_bits = len(bits)

# Calculate how many melody loops are needed to fit the message
samples_per_cycle = int(round(64 * (60.0 / BPM) * SAMPLE_RATE))
frames_per_cycle = samples_per_cycle // FRAME_LEN
loops = max(1, math.ceil(required_bits / frames_per_cycle))

print(f"\nGenerating music ({loops} loops to fit {len(message)} characters)...")
full_notes = BASE_MELODY * loops
clean_audio = f.generate_melody(full_notes)

# Embed the bits into the audio
print("Embedding secret message into the audio...")
stego_audio = embed_message(clean_audio, bits)

# Save the result to a .wav file
save_wav(OUTPUT_FILE, stego_audio)
print(f"Done! File '{OUTPUT_FILE}' successfully generated.")