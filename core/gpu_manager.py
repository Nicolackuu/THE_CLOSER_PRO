"""
THE CLOSER PRO V25 - GPU Self-Healing Manager
Gestion dynamique de la charge GPU avec ajustement automatique des buffers.
Maintient le système en temps réel strict même sous charge élevée.

Author: THE CLOSER PRO Team
Version: 2.5.0 (Elite)
"""

import torch
import psutil
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Callable
import asyncio


@dataclass
class GPUMetrics:
    """Métriques GPU en temps réel."""
    vram_allocated_gb: float
    vram_reserved_gb: float
    vram_free_gb: float
    utilization_percent: float
    temperature_celsius: Optional[float] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class PerformanceProfile:
    """Profil de performance adaptatif."""
    buffer_duration: float
    max_queue_size: int
    beam_size: int
    compute_type: str
    vad_threshold: float
    
    @property
    def profile_name(self) -> str:
        """Retourne le nom du profil."""
        if self.buffer_duration <= 2.0:
            return "ULTRA_FAST"
        elif self.buffer_duration <= 3.0:
            return "FAST"
        elif self.buffer_duration <= 5.0:
            return "BALANCED"
        else:
            return "QUALITY"


class GPUSelfHealingManager:
    """
    Gestionnaire auto-adaptatif de la charge GPU.
    Ajuste dynamiquement les paramètres pour maintenir le temps réel.
    """
    
    # Profils prédéfinis
    PROFILES = {
        "ULTRA_FAST": PerformanceProfile(
            buffer_duration=1.5,
            max_queue_size=20,
            beam_size=3,
            compute_type="float16",
            vad_threshold=0.7
        ),
        "FAST": PerformanceProfile(
            buffer_duration=3.0,
            max_queue_size=30,
            beam_size=5,
            compute_type="float16",
            vad_threshold=0.6
        ),
        "BALANCED": PerformanceProfile(
            buffer_duration=5.0,
            max_queue_size=50,
            beam_size=5,
            compute_type="float16",
            vad_threshold=0.5
        ),
        "QUALITY": PerformanceProfile(
            buffer_duration=8.0,
            max_queue_size=100,
            beam_size=7,
            compute_type="float16",
            vad_threshold=0.4
        )
    }
    
    def __init__(
        self,
        target_vram_percent: float = 80.0,
        monitoring_interval: float = 2.0,
        adjustment_callback: Optional[Callable] = None
    ):
        """
        Initialise le gestionnaire GPU.
        
        Args:
            target_vram_percent: Seuil VRAM cible (%)
            monitoring_interval: Intervalle de monitoring (secondes)
            adjustment_callback: Callback appelé lors d'un ajustement
        """
        self.target_vram_percent = target_vram_percent
        self.monitoring_interval = monitoring_interval
        self.adjustment_callback = adjustment_callback
        
        self.logger = logging.getLogger(__name__)
        
        # État actuel
        self.current_profile = self.PROFILES["FAST"]
        self.current_metrics: Optional[GPUMetrics] = None
        
        # Historique des métriques
        self.metrics_history = []
        self.max_history_size = 100
        
        # Monitoring task
        self._monitor_task: Optional[asyncio.Task] = None
        self._is_monitoring = False
        
        # Compteurs de performance
        self.lag_events = 0
        self.adjustments_count = 0
        self.last_adjustment_time: Optional[datetime] = None
        
        # Cooldown pour éviter les ajustements trop fréquents
        self.adjustment_cooldown = timedelta(seconds=10)
    
    def get_gpu_metrics(self) -> GPUMetrics:
        """
        Récupère les métriques GPU actuelles.
        
        Returns:
            GPUMetrics avec les données en temps réel
        """
        if not torch.cuda.is_available():
            return GPUMetrics(
                vram_allocated_gb=0.0,
                vram_reserved_gb=0.0,
                vram_free_gb=0.0,
                utilization_percent=0.0
            )
        
        # Métriques VRAM
        allocated = torch.cuda.memory_allocated(0) / (1024**3)
        reserved = torch.cuda.memory_reserved(0) / (1024**3)
        
        # VRAM totale (RTX 3070 = 8GB)
        total_vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        free_vram = total_vram - allocated
        
        utilization = (allocated / total_vram) * 100
        
        metrics = GPUMetrics(
            vram_allocated_gb=allocated,
            vram_reserved_gb=reserved,
            vram_free_gb=free_vram,
            utilization_percent=utilization
        )
        
        self.current_metrics = metrics
        self.metrics_history.append(metrics)
        
        # Limiter la taille de l'historique
        if len(self.metrics_history) > self.max_history_size:
            self.metrics_history.pop(0)
        
        return metrics
    
    def should_adjust_performance(self) -> bool:
        """
        Détermine si un ajustement de performance est nécessaire.
        
        Returns:
            True si un ajustement est requis
        """
        if not self.current_metrics:
            return False
        
        # Vérifier le cooldown
        if self.last_adjustment_time:
            if datetime.now() - self.last_adjustment_time < self.adjustment_cooldown:
                return False
        
        # Critères d'ajustement
        vram_overload = self.current_metrics.utilization_percent > self.target_vram_percent
        
        # Vérifier la tendance (moyenne des 5 dernières mesures)
        if len(self.metrics_history) >= 5:
            recent_avg = sum(m.utilization_percent for m in self.metrics_history[-5:]) / 5
            trending_up = recent_avg > self.target_vram_percent
        else:
            trending_up = False
        
        return vram_overload or trending_up
    
    def adjust_performance_profile(self, direction: str = "auto") -> PerformanceProfile:
        """
        Ajuste le profil de performance.
        
        Args:
            direction: "up" (plus rapide), "down" (plus qualité), ou "auto"
        
        Returns:
            Nouveau profil de performance
        """
        current_name = self.current_profile.profile_name
        profile_order = ["ULTRA_FAST", "FAST", "BALANCED", "QUALITY"]
        current_index = profile_order.index(current_name)
        
        if direction == "auto":
            # Décider automatiquement
            if self.should_adjust_performance():
                direction = "up"  # Plus rapide pour réduire la charge
            else:
                direction = "down"  # Plus de qualité si possible
        
        if direction == "up" and current_index > 0:
            # Passer à un profil plus rapide
            new_profile_name = profile_order[current_index - 1]
            self.current_profile = self.PROFILES[new_profile_name]
            self.logger.warning(f"GPU overload detected - switching to {new_profile_name}")
            
        elif direction == "down" and current_index < len(profile_order) - 1:
            # Passer à un profil plus qualitatif
            new_profile_name = profile_order[current_index + 1]
            self.current_profile = self.PROFILES[new_profile_name]
            self.logger.info(f"GPU headroom available - switching to {new_profile_name}")
        
        self.adjustments_count += 1
        self.last_adjustment_time = datetime.now()
        
        # Appeler le callback si défini
        if self.adjustment_callback:
            self.adjustment_callback(self.current_profile)
        
        return self.current_profile
    
    async def start_monitoring(self):
        """Démarre le monitoring GPU en arrière-plan."""
        if self._is_monitoring:
            return
        
        self._is_monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        self.logger.info("GPU self-healing monitoring started")
    
    async def stop_monitoring(self):
        """Arrête le monitoring GPU."""
        if not self._is_monitoring:
            return
        
        self._is_monitoring = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("GPU monitoring stopped")
    
    async def _monitor_loop(self):
        """Boucle de monitoring GPU."""
        while self._is_monitoring:
            try:
                # Récupérer les métriques
                metrics = self.get_gpu_metrics()
                
                # Vérifier si un ajustement est nécessaire
                if self.should_adjust_performance():
                    self.adjust_performance_profile("auto")
                
                # Attendre avant la prochaine mesure
                await asyncio.sleep(self.monitoring_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in GPU monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(self.monitoring_interval)
    
    def cleanup_vram(self):
        """Nettoie la VRAM (garbage collection)."""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            self.logger.debug("VRAM cache cleared")
    
    def get_performance_report(self) -> dict:
        """
        Génère un rapport de performance.
        
        Returns:
            Dict avec les statistiques de performance
        """
        if not self.current_metrics:
            self.get_gpu_metrics()
        
        avg_vram = 0.0
        if self.metrics_history:
            avg_vram = sum(m.vram_allocated_gb for m in self.metrics_history) / len(self.metrics_history)
        
        return {
            "current_profile": self.current_profile.profile_name,
            "current_vram_gb": self.current_metrics.vram_allocated_gb if self.current_metrics else 0.0,
            "average_vram_gb": avg_vram,
            "vram_utilization_percent": self.current_metrics.utilization_percent if self.current_metrics else 0.0,
            "total_adjustments": self.adjustments_count,
            "lag_events": self.lag_events,
            "buffer_duration": self.current_profile.buffer_duration,
            "beam_size": self.current_profile.beam_size
        }
    
    def report_lag_event(self):
        """Signale un événement de lag détecté."""
        self.lag_events += 1
        self.logger.warning(f"Lag event detected (total: {self.lag_events})")
        
        # Ajustement immédiat si trop de lag
        if self.lag_events % 3 == 0:
            self.adjust_performance_profile("up")
