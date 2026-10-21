import sounddevice as sd
import numpy as np
import matplotlib.pyplot as plt

# Configurações
sample_rate = 44100
block_size = 2048  # Quantidade de amostras por quadro do gráfico
graphsize = 16*2048  # Quantidade de amostras por quadro do gráfico
graphindex = 0

# Buffer global para armazenar o último bloco capturado
audio_buffer = np.zeros((graphsize, 1))

# Função callback chamada a cada novo bloco capturado pelo microfone
def callback(indata, frames, time, status):
    global audio_buffer, graphindex
    audio_buffer[graphindex:block_size+graphindex] = indata.copy()
    graphindex += block_size
    if graphindex == graphsize: graphindex = 0

# Configuração da janela do gráfico
fig, ax = plt.subplots(figsize=(10, 4))
x_axis = np.arange(0, graphsize)
line, = ax.plot(x_axis, audio_buffer[:, 0], color='limegreen', linewidth=1)

ax.set_ylim(-1.2, 1.2)  # Escala de amplitude (ajuste se seu som for fraco/forte)
ax.set_xlim(0, graphsize)
ax.set_title("Captura de Áudio em Tempo Real")
ax.set_xlabel("Amostras")
ax.set_ylabel("Amplitude")
ax.grid(True)

print("🎙️ Capturando áudio em tempo real... Feche a janela para encerrar.")

# Inicia o fluxo do microfone e atualiza o gráfico em loop
with sd.InputStream(channels=1, samplerate=sample_rate, blocksize=block_size, callback=callback):
    while plt.fignum_exists(fig.number):
        line.set_ydata(audio_buffer[:, 0])
        plt.pause(0.02)  # Atualiza o gráfico a 50 quadros por segundo
