"""
THE CLOSER PRO V25 - Dual Stream Manager
Gestion asynchrone des deux canaux audio indépendants (VOUS vs CLIENT).
Architecture zéro-overlap avec queues dédiées.

Author: THE CLOSER PRO Team
Version: 2.5.0 (Elite)
"""

import asyncio
import numpy as np
from dataclasses import dataclass
from typing import Optional, Callable
from datetime import datetime
import logging


@dataclass
class AudioStream:
    """Représente un flux audio mono avec métadonnées."""
    data: np.ndarray
    timestamp: datetime
    channel: str  # "LEFT" ou "RIGHT"
    duration: float
    sample_rate: int


@dataclass
class StreamStats:
    """Statistiques par canal."""
    total_duration: float = 0.0
    active_speech_duration: float = 0.0
    segments_count: int = 0
    last_activity: Optional[datetime] = None
    
    @property
    def talk_percentage(self) -> float:
        """Calcule le pourcentage de temps de parole."""
        if self.total_duration == 0:
            return 0.0
        return (self.active_speech_duration / self.total_duration) * 100


class DualStreamManager:
    """
    Gestionnaire de flux audio dual-stream.
    Traite les canaux GAUCHE et DROIT de manière totalement indépendante.
    """
    
    def __init__(
        self,
        left_callback: Callable[[AudioStream], asyncio.Future],
        right_callback: Callable[[AudioStream], asyncio.Future],
        max_queue_size: int = 50,
        sample_rate: int = 48000
    ):
        """
        Initialise le gestionnaire dual-stream.
        
        Args:
            left_callback: Fonction async pour traiter le canal gauche (VOUS)
            right_callback: Fonction async pour traiter le canal droit (CLIENT)
            max_queue_size: Taille maximale des queues
            sample_rate: Fréquence d'échantillonnage
        """
        self.left_callback = left_callback
        self.right_callback = right_callback
        self.sample_rate = sample_rate
        
        # Queues asynchrones indépendantes
        self.left_queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self.right_queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        
        # Statistiques par canal
        self.left_stats = StreamStats()
        self.right_stats = StreamStats()
        
        # Workers asynchrones
        self._left_worker: Optional[asyncio.Task] = None
        self._right_worker: Optional[asyncio.Task] = None
        self._is_running = False
        
        self.logger = logging.getLogger(__name__)
        
        # Session tracking
        self._session_start: Optional[datetime] = None
    
    async def start(self):
        """Démarre les workers de traitement asynchrone."""
        if self._is_running:
            raise RuntimeError("DualStreamManager already running")
        
        self._is_running = True
        self._session_start = datetime.now()
        
        # Lancement des workers indépendants
        self._left_worker = asyncio.create_task(self._process_left_stream())
        self._right_worker = asyncio.create_task(self._process_right_stream())
        
        self.logger.info("DualStreamManager started - Zero-overlap mode active")
    
    async def stop(self):
        """Arrête proprement les workers."""
        if not self._is_running:
            return
        
        self._is_running = False
        
        # Attendre que les queues se vident
        await self.left_queue.join()
        await self.right_queue.join()
        
        # Annuler les workers
        if self._left_worker:
            self._left_worker.cancel()
            try:
                await self._left_worker
            except asyncio.CancelledError:
                pass
        
        if self._right_worker:
            self._right_worker.cancel()
            try:
                await self._right_worker
            except asyncio.CancelledError:
                pass
        
        self.logger.info("DualStreamManager stopped")
    
    async def submit_stereo_chunk(self, stereo_data: np.ndarray, timestamp: datetime):
        """
        Soumet un chunk stéréo et le sépare automatiquement.
        Gère le fallback mono si le périphérique ne supporte pas le stéréo.
        
        Args:
            stereo_data: Données audio stéréo (shape: [samples, 2]) ou mono (shape: [samples,])
            timestamp: Timestamp du chunk
        """
        if not self._is_running:
            raise RuntimeError("DualStreamManager not running")
        
        # Gérer le cas mono (fallback si device ne supporte pas stéréo)
        if len(stereo_data.shape) == 1:
            # Audio mono - dupliquer sur les deux canaux
            self.logger.warning("Mono audio detected - duplicating to both channels (stereo not available)")
            left_channel = stereo_data.copy()
            right_channel = stereo_data.copy()
        elif stereo_data.shape[1] == 1:
            # Audio mono en format 2D
            mono_data = stereo_data[:, 0]
            left_channel = mono_data.copy()
            right_channel = mono_data.copy()
        elif stereo_data.shape[1] == 2:
            # Audio stéréo normal
            left_channel = stereo_data[:, 0].copy()
            right_channel = stereo_data[:, 1].copy()
        else:
            # Plus de 2 canaux - prendre les 2 premiers
            self.logger.warning(f"Multi-channel audio detected ({stereo_data.shape[1]} channels) - using first 2")
            left_channel = stereo_data[:, 0].copy()
            right_channel = stereo_data[:, 1].copy()
        
        duration = len(left_channel) / self.sample_rate
        
        # Création des streams
        left_stream = AudioStream(
            data=left_channel,
            timestamp=timestamp,
            channel="LEFT",
            duration=duration,
            sample_rate=self.sample_rate
        )
        
        right_stream = AudioStream(
            data=right_channel,
            timestamp=timestamp,
            channel="RIGHT",
            duration=duration,
            sample_rate=self.sample_rate
        )
        
        # Soumission asynchrone aux queues indépendantes
        try:
            await asyncio.gather(
                self.left_queue.put(left_stream),
                self.right_queue.put(right_stream)
            )
        except asyncio.QueueFull:
            self.logger.warning("Queue overflow - dropping chunk")
    
    async def _process_left_stream(self):
        """Worker pour le canal GAUCHE (VOUS)."""
        while self._is_running:
            try:
                stream = await self.left_queue.get()
                
                # Vérifier si le canal contient de la parole (énergie > seuil)
                energy = np.sum(stream.data ** 2)
                
                if energy > 0.001:  # Seuil de détection de parole
                    # Traiter avec le callback
                    await self.left_callback(stream)
                    
                    # Mettre à jour les stats
                    self.left_stats.active_speech_duration += stream.duration
                    self.left_stats.segments_count += 1
                    self.left_stats.last_activity = stream.timestamp
                
                self.left_stats.total_duration += stream.duration
                self.left_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in left stream worker: {e}", exc_info=True)
                self.left_queue.task_done()
    
    async def _process_right_stream(self):
        """Worker pour le canal DROIT (CLIENT)."""
        while self._is_running:
            try:
                stream = await self.right_queue.get()
                
                # Vérifier si le canal contient de la parole
                energy = np.sum(stream.data ** 2)
                
                if energy > 0.001:
                    await self.right_callback(stream)
                    
                    self.right_stats.active_speech_duration += stream.duration
                    self.right_stats.segments_count += 1
                    self.right_stats.last_activity = stream.timestamp
                
                self.right_stats.total_duration += stream.duration
                self.right_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in right stream worker: {e}", exc_info=True)
                self.right_queue.task_done()
    
    def get_talk_ratio(self) -> dict:
        """
        Calcule le ratio de parole VOUS vs CLIENT.
        
        Returns:
            Dict avec les pourcentages et durées
        """
        total_speech = (
            self.left_stats.active_speech_duration + 
            self.right_stats.active_speech_duration
        )
        
        if total_speech == 0:
            return {
                "vous_percentage": 0.0,
                "client_percentage": 0.0,
                "vous_duration": 0.0,
                "client_duration": 0.0,
                "total_duration": 0.0
            }
        
        vous_pct = (self.left_stats.active_speech_duration / total_speech) * 100
        client_pct = (self.right_stats.active_speech_duration / total_speech) * 100
        
        return {
            "vous_percentage": vous_pct,
            "client_percentage": client_pct,
            "vous_duration": self.left_stats.active_speech_duration,
            "client_duration": self.right_stats.active_speech_duration,
            "total_duration": total_speech
        }
    
    def get_queue_health(self) -> dict:
        """
        Retourne l'état de santé des queues pour le self-healing.
        
        Returns:
            Dict avec les métriques de charge
        """
        return {
            "left_queue_size": self.left_queue.qsize(),
            "right_queue_size": self.right_queue.qsize(),
            "left_queue_full": self.left_queue.full(),
            "right_queue_full": self.right_queue.full(),
            "is_healthy": not (self.left_queue.full() or self.right_queue.full())
        }
