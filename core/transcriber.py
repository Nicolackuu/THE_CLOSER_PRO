import sys
import time
import signal
import gc
import json
import numpy as np
import pyaudio
from faster_whisper import WhisperModel

# --- CONFIGURATION ---
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
except FileNotFoundError:
    print("[ERREUR] config.json introuvable. Utilisation des defauts.")
    config = {"model_size": "distil-large-v3", "device": "cuda", "compute_type": "float16", "device_index": 36, "sample_rate": 48000, "channels": 2}

MODEL_SIZE = config.get("model_size", "distil-large-v3")
DEVICE = config.get("device", "cuda")
COMPUTE_TYPE = config.get("compute_type", "float16")
DEVICE_INDEX = config.get("device_index", 33)
SAMPLE_RATE = config.get("sample_rate", 48000)
CHANNELS = config.get("channels", 2)

CHUNK = 4096 
MAX_BUFFER_DURATION = 30 
LOG_FILE = "session_log.txt"

# --- LISTE NOIRE (Héritage V8) ---
# Ces phrases sont des hallucinations fréquentes de Whisper dans le silence
HALLUCINATIONS = [
    "Sous-titres réalisés par",
    "Amara.org",
    "Poursuivez le visionnage",
    "Abonnez-vous",
    "www."
]

def signal_handler(sig, frame):
    print("\n[ARRET] Arret demande par l'utilisateur via Ctrl+C", flush=True)
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def write_to_log(text):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(text + "\n")

def is_hallucination(text):
    """Verifie si le texte est une hallucination connue"""
    for h in HALLUCINATIONS:
        if h.lower() in text.lower():
            return True
    return False

def main():
    open(LOG_FILE, 'w').close()

    print(f"\n{'='*50}", flush=True)
    print(f"[INIT] THE CLOSER - Alpha 0.3 (Hybrid History)", flush=True)
    print(f"[INIT] GPU: RTX 3070 | Modele: {MODEL_SIZE}", flush=True)
    
    try:
        model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
        print(f"[SUCCES] Modele chargé en VRAM", flush=True)
    except Exception as e:
        print(f"[ERREUR] Echec chargement IA : {e}", flush=True)
        return

    p = pyaudio.PyAudio()
    
    try:
        stream = p.open(format=pyaudio.paFloat32,
                        channels=CHANNELS,
                        rate=SAMPLE_RATE,
                        input=True,
                        input_device_index=DEVICE_INDEX,
                        frames_per_buffer=CHUNK)
        print(f"[AUDIO] Source ID {DEVICE_INDEX} connectée ({SAMPLE_RATE}Hz)", flush=True)
    except Exception as e:
        print(f"[ERREUR AUDIO] ID {DEVICE_INDEX} invalide : {e}", flush=True)
        return

    print(f"[PRET] Parlez ! (Closing / Pipeline / High-Ticket)", flush=True)
    print(f"{'='*50}\n", flush=True)

    buffer_audio = []
    last_transcription_time = time.time()
    
    try:
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            audio_chunk = np.frombuffer(data, dtype=np.float32)
            
            # --- VU-METRE ---
            audio_stereo = audio_chunk.reshape(-1, 2)
            left_channel = audio_stereo[:, 0]
            right_channel = audio_stereo[:, 1]
            
            vol_left = np.sqrt(np.mean(left_channel**2))
            vol_right = np.sqrt(np.mean(right_channel**2))
            max_vol = max(vol_left, vol_right)

            if max_vol > 0.01:
                bars = int(max_vol * 100)
                speaker_hint = "MOI" if vol_left > vol_right else "CLIENT"
                print(f"\r[{speaker_hint}] Vol: {'|' * bars:<15}", end="", flush=True)

            # --- TRANSCRIPTION ---
            # Resampling basique 48k -> 16k (1 point sur 3)
            mono_mix = np.mean(audio_stereo, axis=1)
            resampled_chunk = mono_mix[::3]
            
            buffer_audio.append(resampled_chunk)
            full_audio = np.concatenate(buffer_audio)
            
            # Transcription toutes les 2s d'audio accumulé
            if len(full_audio) > 16000 * 2:
                speaker_tag = "[MOI]" if vol_left > vol_right * 1.1 else "[CLIENT]"
                if vol_right > vol_left * 1.1: speaker_tag = "[CLIENT]"

                
                # PROMPT BLINDÉ POUR FORCER LE FRANÇAIS
                segments, _ = model.transcribe(
                    full_audio, 
                    language="fr",      # On force le français
                    task="transcribe",  # On interdit la traduction
                    vad_filter=True,
                    # L'astuce est ici : on lui donne une phrase complète en FR pour l'amorcer
                    initial_prompt="La phrase est en français. On utilise des termes techniques comme Pipeline, Closing, High-Ticket. Ne traduis pas en anglais."
                )
                
                text_found = False
                for segment in segments:
                    clean_text = segment.text.strip()
                    
                    # FILTRE ANTI-HALLUCINATION (Héritage V8)
                    if clean_text and not is_hallucination(clean_text):
                        timestamp = time.strftime('%H:%M:%S')
                        formatted_line = f"{timestamp} {speaker_tag} {clean_text}"
                        
                        # Affichage console
                        print(f"\r{' '*50}", end="\r") 
                        print(formatted_line, flush=True)
                        
                        write_to_log(formatted_line)
                        text_found = True
                
                # Nettoyage buffer : On vide si on a trouvé du texte OU si ça fait trop longtemps (>30s)
                if len(full_audio) > 16000 * MAX_BUFFER_DURATION or text_found:
                    buffer_audio = []
                    # Garbage Collector manuel pour aider la RTX 3070 (Leçon du Crash V19)
                    if not text_found: gc.collect()

    except KeyboardInterrupt:
        pass
    finally:
        print("\n[ARRET] Sauvegarde terminée.", flush=True)
        stream.stop_stream()
        stream.close()
        p.terminate()

if __name__ == "__main__":
    main()