"""
Audio Streamer Module - THE CLOSER PRO.
Capture audio en continu depuis VoiceMeeter Virtual B1 avec gestion asynchrone.
Utilise threading et queue.Queue pour garantir zéro perte de paquets.
"""

import numpy as np
import sounddevice as sd
import threading
import queue
import time
import logging
from typing import Optional, Callable
from dataclasses import dataclass

from config.manager import get_config


@dataclass
class AudioChunk:
    """
    Représente un chunk audio capturé.
    
    Attributes:
        data: Données audio brutes (numpy array)
        timestamp: Timestamp de capture (epoch)
        sample_rate: Taux d'échantillonnage
        is_silence: Indicateur de silence détecté
    """
    data: np.ndarray
    timestamp: float
    sample_rate: int
    is_silence: bool = False


class AudioStreamer:
    """
    Streamer audio temps réel avec buffer thread-safe.
    Capture l'audio en continu sans interruption, même si le consommateur est lent.
    
    Architecture:
        - Thread principal: Callback sounddevice (haute priorité)
        - Queue thread-safe: Buffer FIFO pour découpler capture/traitement
        - Thread consommateur: Traitement asynchrone des chunks
    """
    
    def __init__(self, callback: Optional[Callable[[AudioChunk], None]] = None):
        """
        Initialise le streamer audio.
        
        Args:
            callback: Fonction appelée pour chaque chunk audio capturé.
                     Signature: callback(AudioChunk) -> None
        """
        self.config = get_config()
        self.logger = logging.getLogger(__name__)
        
        self.audio_queue = queue.Queue(maxsize=self.config.system.max_queue_size)
        self.callback = callback
        
        self._stream: Optional[sd.InputStream] = None
        self._is_running = False
        self._consumer_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        self._total_chunks = 0
        self._dropped_chunks = 0
        self._silence_start: Optional[float] = None
        
        self.logger.info(f"AudioStreamer initialized - Device ID: {self.config.audio.device_id}")
    
    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        """
        Callback appelé par sounddevice pour chaque chunk audio capturé.
        S'exécute dans un thread haute priorité - doit être ultra-rapide.
        
        Args:
            indata: Données audio capturées (numpy array)
            frames: Nombre de frames
            time_info: Informations temporelles
            status: Statut de la capture
        """
        if status:
            self.logger.warning(f"Audio callback status: {status}")
        
        if not self._is_running:
            return
        
        audio_copy = indata.copy()
        
        rms = np.sqrt(np.mean(audio_copy**2))
        is_silence = rms < self.config.audio.silence_threshold
        
        chunk = AudioChunk(
            data=audio_copy,
            timestamp=time.time(),
            sample_rate=self.config.audio.sample_rate,
            is_silence=is_silence
        )
        
        try:
            self.audio_queue.put_nowait(chunk)
            self._total_chunks += 1
        except queue.Full:
            self._dropped_chunks += 1
            if self._dropped_chunks % 10 == 0:
                self.logger.error(
                    f"Audio queue full! Dropped {self._dropped_chunks} chunks. "
                    f"Consumer too slow or queue size too small."
                )
    
    def _consumer_loop(self):
        """
        Boucle de consommation des chunks audio.
        S'exécute dans un thread séparé pour ne pas bloquer la capture.
        """
        self.logger.info("Audio consumer thread started")
        
        while self._is_running:
            try:
                chunk = self.audio_queue.get(timeout=0.1)
                
                if chunk.is_silence:
                    if self._silence_start is None:
                        self._silence_start = chunk.timestamp
                    elif (chunk.timestamp - self._silence_start) > self.config.audio.silence_duration:
                        self.logger.debug("Silence prolongé détecté - Opportunité de nettoyage GPU")
                else:
                    self._silence_start = None
                
                if self.callback:
                    try:
                        self.callback(chunk)
                    except Exception as e:
                        self.logger.error(f"Error in audio callback: {e}", exc_info=True)
                
                self.audio_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error in consumer loop: {e}", exc_info=True)
        
        self.logger.info("Audio consumer thread stopped")
    
    def start(self):
        """
        Démarre la capture audio et le thread de consommation.
        
        Raises:
            RuntimeError: Si le streamer est déjà en cours d'exécution.
            OSError: Si le périphérique audio n'est pas accessible.
        """
        with self._lock:
            if self._is_running:
                raise RuntimeError("AudioStreamer is already running")
            
            self.logger.info("Starting audio streamer...")
            
            try:
                self._stream = sd.InputStream(
                    device=self.config.audio.device_id,
                    channels=self.config.audio.channels,
                    samplerate=self.config.audio.sample_rate,
                    blocksize=int(self.config.audio.sample_rate * self.config.audio.chunk_duration),
                    callback=self._audio_callback,
                    dtype=np.float32
                )
                
                self._is_running = True
                
                self._consumer_thread = threading.Thread(
                    target=self._consumer_loop,
                    name="AudioConsumerThread",
                    daemon=True
                )
                self._consumer_thread.start()
                
                self._stream.start()
                
                self.logger.info(
                    f"Audio streamer started successfully\n"
                    f"  Device: {self.config.audio.device_id}\n"
                    f"  Sample Rate: {self.config.audio.sample_rate} Hz\n"
                    f"  Channels: {self.config.audio.channels}\n"
                    f"  Chunk Duration: {self.config.audio.chunk_duration}s"
                )
                
            except Exception as e:
                self._is_running = False
                self.logger.error(f"Failed to start audio streamer: {e}", exc_info=True)
                raise
    
    def stop(self):
        """
        Arrête proprement la capture audio et le thread de consommation.
        Attend que tous les chunks en queue soient traités.
        """
        with self._lock:
            if not self._is_running:
                self.logger.warning("AudioStreamer is not running")
                return
            
            self.logger.info("Stopping audio streamer...")
            self._is_running = False
            
            if self._stream:
                self._stream.stop()
                self._stream.close()
                self._stream = None
            
            if self._consumer_thread and self._consumer_thread.is_alive():
                self._consumer_thread.join(timeout=5.0)
            
            try:
                while not self.audio_queue.empty():
                    self.audio_queue.get_nowait()
                    self.audio_queue.task_done()
            except queue.Empty:
                pass
            
            self.logger.info(
                f"Audio streamer stopped\n"
                f"  Total chunks: {self._total_chunks}\n"
                f"  Dropped chunks: {self._dropped_chunks}\n"
                f"  Loss rate: {(self._dropped_chunks / max(self._total_chunks, 1)) * 100:.2f}%"
            )
    
    def is_running(self) -> bool:
        """
        Vérifie si le streamer est en cours d'exécution.
        
        Returns:
            True si le streamer est actif, False sinon.
        """
        return self._is_running
    
    def get_stats(self) -> dict:
        """
        Retourne les statistiques de capture audio.
        
        Returns:
            Dictionnaire contenant les métriques de performance.
        """
        return {
            "is_running": self._is_running,
            "total_chunks": self._total_chunks,
            "dropped_chunks": self._dropped_chunks,
            "queue_size": self.audio_queue.qsize(),
            "loss_rate_percent": (self._dropped_chunks / max(self._total_chunks, 1)) * 100
        }
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        return False


def list_audio_devices():
    """
    Liste tous les périphériques audio disponibles sur le système.
    Utile pour identifier l'ID de VoiceMeeter Virtual B1.
    
    Returns:
        Liste des périphériques audio avec leurs IDs et noms.
    """
    devices = sd.query_devices()
    print("\n=== PÉRIPHÉRIQUES AUDIO DISPONIBLES ===\n")
    
    for idx, device in enumerate(devices):
        device_type = []
        if device['max_input_channels'] > 0:
            device_type.append("INPUT")
        if device['max_output_channels'] > 0:
            device_type.append("OUTPUT")
        
        print(f"[{idx}] {device['name']}")
        print(f"    Type: {' | '.join(device_type)}")
        print(f"    Channels: IN={device['max_input_channels']}, OUT={device['max_output_channels']}")
        print(f"    Sample Rate: {device['default_samplerate']} Hz")
        print()
    
    return devices


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    list_audio_devices()
    
    def test_callback(chunk: AudioChunk):
        rms = np.sqrt(np.mean(chunk.data**2))
        print(f"Chunk received - RMS: {rms:.4f} - Silence: {chunk.is_silence}")
    
    print("\nTesting audio streamer for 10 seconds...")
    
    with AudioStreamer(callback=test_callback) as streamer:
        time.sleep(10)
    
    print("\nTest completed!")
