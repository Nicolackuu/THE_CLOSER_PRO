"""
THE CLOSER PRO V25 - Elite Transcriber
Transcripteur asynchrone avec intégration context memory et dual-stream.
Architecture professionnelle pour transcription temps réel haute performance.

Author: THE CLOSER PRO Team
Version: 2.5.0 (Elite)
"""

import asyncio
import numpy as np
import torch
import logging
from typing import Optional, Dict
from datetime import datetime
from dataclasses import dataclass
from faster_whisper import WhisperModel

from core.context_memory import ContextMemory
from core.gpu_manager import GPUSelfHealingManager
from config.manager import get_config


@dataclass
class TranscriptionResult:
    """Résultat de transcription enrichi."""
    text: str
    speaker: str  # "VOUS" ou "CLIENT"
    timestamp: datetime
    duration: float
    confidence: float
    language: str = "fr"


class EliteTranscriber:
    """
    Transcripteur Elite avec context memory et auto-adaptation GPU.
    Conçu pour le traitement dual-stream asynchrone.
    """
    
    _instance: Optional['EliteTranscriber'] = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialise le transcripteur Elite."""
        if hasattr(self, '_initialized'):
            return
        
        self.config = get_config()
        self.logger = logging.getLogger(__name__)
        
        # Composants Elite
        self.context_memory = ContextMemory(
            context_window_seconds=30.0,
            max_segments=50,
            sample_rate=16000
        )
        
        self.gpu_manager = GPUSelfHealingManager(
            target_vram_percent=75.0,
            monitoring_interval=2.0,
            adjustment_callback=self._on_performance_adjustment
        )
        
        # Modèle Whisper
        self.model: Optional[WhisperModel] = None
        self._model_lock = asyncio.Lock()
        
        # Statistiques
        self.total_transcriptions = 0
        self.total_inference_time = 0.0
        self.errors_count = 0
        
        self._initialized = True
        self._is_running = False
    
    async def initialize(self):
        """Initialise le modèle et démarre les composants."""
        async with self._lock:
            if self._is_running:
                return
            
            self.logger.info("Initializing Elite Transcriber...")
            
            # Charger le modèle Whisper
            await self._load_model()
            
            # Démarrer le GPU manager
            await self.gpu_manager.start_monitoring()
            
            self._is_running = True
            self.logger.info("Elite Transcriber initialized successfully")
    
    async def _load_model(self):
        """Charge le modèle Whisper de manière asynchrone."""
        def _load():
            return WhisperModel(
                self.config.transcription.model_name,
                device=self.config.transcription.device,
                compute_type=self.config.transcription.compute_type,
                download_root=None,
                local_files_only=False
            )
        
        # Charger dans un thread executor pour ne pas bloquer
        loop = asyncio.get_event_loop()
        self.model = await loop.run_in_executor(None, _load)
        
        self.logger.info(f"Model {self.config.transcription.model_name} loaded on {self.config.transcription.device}")
    
    async def transcribe_stream(
        self,
        audio_data: np.ndarray,
        speaker: str,
        timestamp: Optional[datetime] = None
    ) -> Optional[TranscriptionResult]:
        """
        Transcrit un flux audio avec context memory.
        
        Args:
            audio_data: Données audio mono (float32, 16kHz ou 48kHz)
            speaker: "VOUS" ou "CLIENT"
            timestamp: Timestamp du segment
        
        Returns:
            TranscriptionResult ou None si échec
        """
        if not self._is_running or self.model is None:
            self.logger.error("Transcriber not initialized")
            return None
        
        if timestamp is None:
            timestamp = datetime.now()
        
        try:
            # Prétraitement audio
            processed_audio = await self._preprocess_audio(audio_data)
            
            # Obtenir le prompt de contexte
            context_prompt = self.context_memory.get_context_prompt(speaker)
            
            # Obtenir le profil de performance actuel
            profile = self.gpu_manager.current_profile
            
            # Transcription asynchrone
            start_time = datetime.now()
            
            result = await self._transcribe_async(
                processed_audio,
                context_prompt,
                profile.beam_size
            )
            
            inference_time = (datetime.now() - start_time).total_seconds()
            self.total_inference_time += inference_time
            self.total_transcriptions += 1
            
            if not result:
                return None
            
            # Créer le résultat
            transcription = TranscriptionResult(
                text=result["text"],
                speaker=speaker,
                timestamp=timestamp,
                duration=result["duration"],
                confidence=result["confidence"],
                language="fr"
            )
            
            # Ajouter au contexte
            self.context_memory.add_segment(
                text=result["text"],
                speaker=speaker,
                timestamp=timestamp,
                duration=result["duration"]
            )
            
            # Nettoyage GPU si nécessaire
            if self.total_transcriptions % 10 == 0:
                self.gpu_manager.cleanup_vram()
            
            return transcription
            
        except Exception as e:
            self.logger.error(f"Transcription error: {e}", exc_info=True)
            self.errors_count += 1
            return None
    
    async def _preprocess_audio(self, audio_data: np.ndarray) -> np.ndarray:
        """
        Prétraite l'audio pour Whisper.
        
        Args:
            audio_data: Audio brut
        
        Returns:
            Audio prétraité (16kHz, float32, mono)
        """
        # Conversion asynchrone dans un executor
        def _process():
            # Assurer que c'est mono
            if len(audio_data.shape) > 1:
                processed = audio_data.mean(axis=1)
            else:
                processed = audio_data
            
            # Resampling si nécessaire (48kHz -> 16kHz)
            if self.config.audio.sample_rate != 16000:
                original_length = len(processed)
                target_length = int(original_length * 16000 / self.config.audio.sample_rate)
                indices = np.linspace(0, original_length - 1, target_length)
                processed = np.interp(indices, np.arange(original_length), processed)
            
            # Assurer float32
            return processed.astype(np.float32)
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _process)
    
    async def _transcribe_async(
        self,
        audio_data: np.ndarray,
        initial_prompt: str,
        beam_size: int
    ) -> Optional[Dict]:
        """
        Effectue la transcription de manière asynchrone.
        
        Args:
            audio_data: Audio prétraité
            initial_prompt: Prompt de contexte
            beam_size: Taille du beam search
        
        Returns:
            Dict avec text, duration, confidence
        """
        async with self._model_lock:
            def _transcribe():
                segments, info = self.model.transcribe(
                    audio_data,
                    language="fr",
                    task="transcribe",
                    beam_size=beam_size,
                    vad_filter=self.config.transcription.vad_filter,
                    initial_prompt=initial_prompt,
                    condition_on_previous_text=True,
                    temperature=0.0,
                    compression_ratio_threshold=2.4,
                    log_prob_threshold=-1.0,
                    no_speech_threshold=0.6
                )
                
                # Collecter les segments
                text_parts = []
                total_confidence = 0.0
                segment_count = 0
                
                for segment in segments:
                    text_parts.append(segment.text.strip())
                    if hasattr(segment, 'avg_logprob'):
                        total_confidence += segment.avg_logprob
                    segment_count += 1
                
                if segment_count == 0:
                    return None
                
                full_text = " ".join(text_parts)
                avg_confidence = total_confidence / segment_count if segment_count > 0 else 0.0
                
                return {
                    "text": full_text,
                    "duration": len(audio_data) / 16000,
                    "confidence": avg_confidence
                }
            
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _transcribe)
    
    def _on_performance_adjustment(self, new_profile):
        """Callback appelé lors d'un ajustement de performance."""
        self.logger.info(
            f"Performance adjusted to {new_profile.profile_name}: "
            f"buffer={new_profile.buffer_duration}s, beam={new_profile.beam_size}"
        )
    
    async def shutdown(self):
        """Arrête proprement le transcripteur."""
        if not self._is_running:
            return
        
        self.logger.info("Shutting down Elite Transcriber...")
        
        # Arrêter le GPU manager
        await self.gpu_manager.stop_monitoring()
        
        # Nettoyer le contexte
        self.context_memory.clear()
        
        # Nettoyer la VRAM
        self.gpu_manager.cleanup_vram()
        
        self._is_running = False
        self.logger.info("Elite Transcriber shutdown complete")
    
    def get_stats(self) -> Dict:
        """
        Retourne les statistiques du transcripteur.
        
        Returns:
            Dict avec les métriques
        """
        avg_inference = 0.0
        if self.total_transcriptions > 0:
            avg_inference = self.total_inference_time / self.total_transcriptions
        
        gpu_report = self.gpu_manager.get_performance_report()
        context_stats = self.context_memory.get_speaker_stats()
        
        return {
            "total_transcriptions": self.total_transcriptions,
            "average_inference_time": avg_inference,
            "errors_count": self.errors_count,
            "gpu_profile": gpu_report["current_profile"],
            "vram_usage_gb": gpu_report["current_vram_gb"],
            "context_segments": context_stats["total_segments"],
            "gpu_adjustments": gpu_report["total_adjustments"]
        }


# Singleton getter
_transcriber_instance: Optional[EliteTranscriber] = None

def get_elite_transcriber() -> EliteTranscriber:
    """Retourne l'instance singleton du transcripteur Elite."""
    global _transcriber_instance
    if _transcriber_instance is None:
        _transcriber_instance = EliteTranscriber()
    return _transcriber_instance
