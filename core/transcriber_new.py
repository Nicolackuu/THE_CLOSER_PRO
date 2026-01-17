"""
Transcriber Module - THE CLOSER PRO.
Moteur de transcription basé sur Faster-Whisper distil-large-v3.
Implémentation Singleton avec inférence déportée dans un thread séparé.
"""

import numpy as np
import threading
import queue
import logging
import time
import torch
from typing import Optional, Generator, Tuple
from dataclasses import dataclass

from faster_whisper import WhisperModel
from config.manager import get_config


@dataclass
class TranscriptionSegment:
    """
    Représente un segment de transcription.
    
    Attributes:
        text: Texte transcrit
        start: Timestamp de début (secondes)
        end: Timestamp de fin (secondes)
        confidence: Score de confiance (0-1)
        language: Langue détectée
    """
    text: str
    start: float
    end: float
    confidence: float
    language: str


@dataclass
class TranscriptionRequest:
    """
    Requête de transcription à traiter.
    
    Attributes:
        audio_data: Données audio (numpy array, 16kHz mono)
        request_id: ID unique de la requête
        timestamp: Timestamp de la requête
        result_queue: Queue pour recevoir le résultat
    """
    audio_data: np.ndarray
    request_id: str
    timestamp: float
    result_queue: queue.Queue


class WhisperTranscriber:
    """
    Transcriber singleton basé sur Faster-Whisper.
    Gère le modèle en VRAM et traite les requêtes de manière asynchrone.
    
    Architecture:
        - Instance unique (Singleton) pour éviter de charger le modèle plusieurs fois
        - Thread worker dédié pour l'inférence (ne bloque pas le thread principal)
        - Queue de requêtes pour découpler l'envoi et le traitement
        - Gestion automatique du cache GPU pendant les périodes de silence
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """
        Implémentation du pattern Singleton.
        Garantit qu'une seule instance existe (= un seul modèle en VRAM).
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(WhisperTranscriber, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """
        Initialise le transcriber (une seule fois grâce au Singleton).
        Charge le modèle Whisper en VRAM.
        """
        if self._initialized:
            return
        
        self.config = get_config()
        self.logger = logging.getLogger(__name__)
        
        self.model: Optional[WhisperModel] = None
        self._request_queue = queue.Queue(maxsize=10)
        self._worker_thread: Optional[threading.Thread] = None
        self._is_running = False
        
        self._total_requests = 0
        self._successful_transcriptions = 0
        self._failed_transcriptions = 0
        self._total_inference_time = 0.0
        
        self._last_cleanup_time = time.time()
        
        self._load_model()
        self._initialized = True
    
    def _load_model(self):
        """
        Charge le modèle Faster-Whisper en mémoire GPU.
        
        Raises:
            RuntimeError: Si le chargement échoue (CUDA non disponible, VRAM insuffisante, etc.)
        """
        try:
            self.logger.info(f"Loading Whisper model: {self.config.transcription.model_name}")
            self.logger.info(f"Device: {self.config.transcription.device}, Compute: {self.config.transcription.compute_type}")
            
            if self.config.transcription.device == "cuda" and not torch.cuda.is_available():
                self.logger.warning("CUDA requested but not available, falling back to CPU")
                self.config.transcription.device = "cpu"
                self.config.transcription.compute_type = "int8"
            
            self.model = WhisperModel(
                self.config.transcription.model_name,
                device=self.config.transcription.device,
                compute_type=self.config.transcription.compute_type,
                download_root=None
            )
            
            if self.config.transcription.device == "cuda":
                vram_allocated = torch.cuda.memory_allocated() / 1024**3
                vram_reserved = torch.cuda.memory_reserved() / 1024**3
                self.logger.info(
                    f"Model loaded successfully in VRAM\n"
                    f"  Allocated: {vram_allocated:.2f} GB\n"
                    f"  Reserved: {vram_reserved:.2f} GB"
                )
            else:
                self.logger.info("Model loaded successfully in CPU")
            
        except Exception as e:
            self.logger.error(f"Failed to load Whisper model: {e}", exc_info=True)
            raise RuntimeError(f"Cannot initialize transcriber: {e}")
    
    def _worker_loop(self):
        """
        Boucle de traitement des requêtes de transcription.
        S'exécute dans un thread séparé pour ne pas bloquer l'application.
        """
        self.logger.info("Transcription worker thread started")
        
        while self._is_running:
            try:
                request = self._request_queue.get(timeout=0.5)
                
                self.logger.debug(f"Processing transcription request {request.request_id}")
                
                start_time = time.time()
                result = self._transcribe_audio(request.audio_data)
                inference_time = time.time() - start_time
                
                self._total_inference_time += inference_time
                
                if result:
                    self._successful_transcriptions += 1
                    self.logger.debug(
                        f"Transcription completed in {inference_time:.2f}s - "
                        f"{len(result)} segments"
                    )
                else:
                    self._failed_transcriptions += 1
                
                request.result_queue.put(result)
                self._request_queue.task_done()
                
                if self.config.system.enable_gpu_cache_cleanup:
                    current_time = time.time()
                    if (current_time - self._last_cleanup_time) > self.config.system.cache_cleanup_interval:
                        self._cleanup_gpu_cache()
                        self._last_cleanup_time = current_time
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error in transcription worker: {e}", exc_info=True)
        
        self.logger.info("Transcription worker thread stopped")
    
    def _transcribe_audio(self, audio_data: np.ndarray) -> list[TranscriptionSegment]:
        """
        Transcrit un buffer audio avec Faster-Whisper.
        Sépare les canaux stéréo pour identifier le locuteur (Gauche=VOUS, Droite=CLIENT).
        
        Args:
            audio_data: Données audio (numpy array, float32, peut être stéréo 48kHz)
        
        Returns:
            Liste de segments transcrits avec préfixe locuteur et couleur.
        """
        if self.model is None:
            self.logger.error("Model not loaded")
            return []
        
        try:
            speaker_tag = ""
            speaker_color = ""
            
            if len(audio_data.shape) == 1:
                data = audio_data.reshape(-1, 2)
            else:
                data = audio_data
            
            if data.shape[1] == 2:
                left_channel = data[:, 0]
                right_channel = data[:, 1]
                
                energy_left = np.sum(left_channel**2)
                energy_right = np.sum(right_channel**2)
                
                if energy_left > energy_right:
                    speaker_tag = "VOUS"
                    speaker_color = "GREEN"
                    processed_audio = left_channel
                else:
                    speaker_tag = "CLIENT"
                    speaker_color = "CYAN"
                    processed_audio = right_channel
                
                self.logger.debug(f"Speaker: {speaker_tag} (E_L={energy_left:.2f}, E_R={energy_right:.2f})")
            else:
                processed_audio = data.flatten()
            
            if self.config.audio.sample_rate != 16000:
                original_length = len(processed_audio)
                target_length = int(original_length * 16000 / self.config.audio.sample_rate)
                indices = np.linspace(0, original_length - 1, target_length)
                processed_audio = np.interp(indices, np.arange(original_length), processed_audio)
            
            processed_audio = processed_audio.astype(np.float32)
            
            segments, info = self.model.transcribe(
                processed_audio,
                language="fr",
                task="transcribe",
                beam_size=self.config.transcription.beam_size,
                vad_filter=self.config.transcription.vad_filter,
                initial_prompt=self.config.transcription.initial_prompt,
                condition_on_previous_text=True,
                temperature=0.0,
                compression_ratio_threshold=2.4,
                log_prob_threshold=-1.0,
                no_speech_threshold=0.6
            )
            
            results = []
            for segment in segments:
                text = segment.text.strip()
                if speaker_tag:
                    text = f"[{speaker_tag}]|{speaker_color}|{text}"
                
                results.append(TranscriptionSegment(
                    text=text,
                    start=segment.start,
                    end=segment.end,
                    confidence=segment.avg_logprob if hasattr(segment, 'avg_logprob') else 0.0,
                    language="fr"
                ))
            
            return results
            
        except Exception as e:
            self.logger.error(f"Transcription failed: {e}", exc_info=True)
            return []
    
    def _cleanup_gpu_cache(self):
        """
        Nettoie le cache GPU pour libérer de la VRAM.
        Appelé périodiquement pendant les périodes de faible activité.
        """
        if self.config.transcription.device == "cuda":
            try:
                torch.cuda.empty_cache()
                self.logger.debug("GPU cache cleaned")
            except Exception as e:
                self.logger.warning(f"Failed to clean GPU cache: {e}")
    
    def start(self):
        """
        Démarre le thread worker de transcription.
        
        Raises:
            RuntimeError: Si le worker est déjà démarré.
        """
        if self._is_running:
            raise RuntimeError("Transcriber worker is already running")
        
        self.logger.info("Starting transcription worker...")
        self._is_running = True
        
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="TranscriptionWorkerThread",
            daemon=True
        )
        self._worker_thread.start()
        
        self.logger.info("Transcription worker started successfully")
    
    def stop(self):
        """
        Arrête proprement le thread worker.
        Attend que toutes les requêtes en cours soient traitées.
        """
        if not self._is_running:
            self.logger.warning("Transcriber worker is not running")
            return
        
        self.logger.info("Stopping transcription worker...")
        self._is_running = False
        
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10.0)
        
        try:
            while not self._request_queue.empty():
                self._request_queue.get_nowait()
                self._request_queue.task_done()
        except queue.Empty:
            pass
        
        self.logger.info(
            f"Transcription worker stopped\n"
            f"  Total requests: {self._total_requests}\n"
            f"  Successful: {self._successful_transcriptions}\n"
            f"  Failed: {self._failed_transcriptions}\n"
            f"  Avg inference time: {self._total_inference_time / max(self._successful_transcriptions, 1):.2f}s"
        )
    
    def transcribe_async(self, audio_data: np.ndarray, request_id: str = None) -> queue.Queue:
        """
        Soumet une requête de transcription asynchrone.
        
        Args:
            audio_data: Données audio à transcrire (numpy array, 16kHz mono)
            request_id: ID unique de la requête (généré automatiquement si None)
        
        Returns:
            Queue dans laquelle le résultat sera placé une fois prêt.
        
        Raises:
            RuntimeError: Si le worker n'est pas démarré.
            queue.Full: Si la queue de requêtes est pleine.
        """
        if not self._is_running:
            raise RuntimeError("Transcriber worker is not running. Call start() first.")
        
        if request_id is None:
            request_id = f"req_{self._total_requests}_{time.time()}"
        
        result_queue = queue.Queue(maxsize=1)
        
        request = TranscriptionRequest(
            audio_data=audio_data,
            request_id=request_id,
            timestamp=time.time(),
            result_queue=result_queue
        )
        
        try:
            self._request_queue.put(request, timeout=1.0)
            self._total_requests += 1
            return result_queue
        except queue.Full:
            self.logger.error("Transcription request queue is full")
            raise
    
    def transcribe_sync(self, audio_data: np.ndarray, timeout: float = 30.0) -> list[TranscriptionSegment]:
        """
        Transcrit de l'audio de manière synchrone (bloquante).
        
        Args:
            audio_data: Données audio à transcrire
            timeout: Timeout en secondes
        
        Returns:
            Liste de segments transcrits.
        
        Raises:
            TimeoutError: Si la transcription dépasse le timeout.
        """
        result_queue = self.transcribe_async(audio_data)
        
        try:
            result = result_queue.get(timeout=timeout)
            return result
        except queue.Empty:
            raise TimeoutError(f"Transcription timed out after {timeout}s")
    
    def get_stats(self) -> dict:
        """
        Retourne les statistiques du transcriber.
        
        Returns:
            Dictionnaire contenant les métriques de performance.
        """
        stats = {
            "is_running": self._is_running,
            "total_requests": self._total_requests,
            "successful": self._successful_transcriptions,
            "failed": self._failed_transcriptions,
            "queue_size": self._request_queue.qsize(),
            "avg_inference_time": self._total_inference_time / max(self._successful_transcriptions, 1)
        }
        
        if self.config.transcription.device == "cuda" and torch.cuda.is_available():
            stats["vram_allocated_gb"] = torch.cuda.memory_allocated() / 1024**3
            stats["vram_reserved_gb"] = torch.cuda.memory_reserved() / 1024**3
        
        return stats
    
    def is_running(self) -> bool:
        """Vérifie si le worker est actif."""
        return self._is_running


def get_transcriber() -> WhisperTranscriber:
    """
    Factory function pour obtenir l'instance unique du transcriber.
    
    Returns:
        Instance singleton de WhisperTranscriber.
    
    Usage:
        >>> transcriber = get_transcriber()
        >>> transcriber.start()
        >>> result_queue = transcriber.transcribe_async(audio_data)
        >>> segments = result_queue.get(timeout=10)
    """
    return WhisperTranscriber()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("Testing WhisperTranscriber...")
    
    transcriber = get_transcriber()
    transcriber.start()
    
    dummy_audio = np.random.randn(16000 * 3).astype(np.float32)
    
    print("Submitting test transcription...")
    result_queue = transcriber.transcribe_async(dummy_audio, request_id="test_1")
    
    print("Waiting for result...")
    segments = result_queue.get(timeout=30)
    
    print(f"Received {len(segments)} segments")
    for seg in segments:
        print(f"  [{seg.start:.2f}s - {seg.end:.2f}s] {seg.text}")
    
    print("\nStats:", transcriber.get_stats())
    
    transcriber.stop()
    print("Test completed!")
