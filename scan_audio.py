import pyaudio

p = pyaudio.PyAudio()

print("\n=== LISTE DES MICROS DISPONIBLES ===")
print("Cherche la ligne : 'VoiceMeeter Output (VB-Audio VoiceMeeter VAIO)'\n")

for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info['maxInputChannels'] > 0: # On ne veut que les entrées (micros)
        print(f"ID {i}: {info['name']}")

print("\n====================================")
input("Appuie sur Entrée pour fermer...")