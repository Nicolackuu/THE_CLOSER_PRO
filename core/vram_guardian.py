"""
THE CLOSER PRO v0.25 - VRAM Guardian
Garbage Collector agressif pour sessions longues (1h+).
Empêche la saturation VRAM de la RTX 3070.

Author: THE CLOSER PRO Team
Version: 0.25 (Elite Edition)
"""

import torch
import gc
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass


@dataclass
class VRAMSnapshot:
    """Snapshot de l'utilisation VRAM."""
    timestamp: datetime
    allocated_gb: float
    reserved_gb: float
    free_gb: float
    utilization_percent: float


class VRAMGuardian:
    """
    Gardien VRAM agressif.
    Nettoie automatiquement la mémoire GPU pour éviter la saturation.
    """
    
    # Seuils de nettoyage
    CLEANUP_THRESHOLD_PERCENT = 70.0  # Nettoyer si > 70%
    AGGRESSIVE_THRESHOLD_PERCENT = 85.0  # Nettoyage agressif si > 85%
    
    # Intervalles de nettoyage
    NORMAL_INTERVAL = 60.0  # Nettoyage normal toutes les 60s
    AGGRESSIVE_INTERVAL = 10.0  # Nettoyage agressif toutes les 10s
    
    def __init__(self, max_vram_gb: float = 8.0):
        """
        Initialise le gardien VRAM.
        
        Args:
            max_vram_gb: VRAM maximale du GPU (8GB pour RTX 3070)
        """
        self.logger = logging.getLogger(__name__)
        self.max_vram_gb = max_vram_gb
        
        # État
        self._is_monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        # Statistiques
        self.total_cleanups = 0
        self.aggressive_cleanups = 0
        self.snapshots: list[VRAMSnapshot] = []
        self.max_snapshots = 100
        
        # Derniers nettoyages
        self._last_cleanup: Optional[datetime] = None
        self._last_aggressive_cleanup: Optional[datetime] = None
    
    def get_vram_usage(self) -> VRAMSnapshot:
        """
        Récupère l'utilisation VRAM actuelle.
        
        Returns:
            VRAMSnapshot avec les métriques
        """
        if not torch.cuda.is_available():
            return VRAMSnapshot(
                timestamp=datetime.now(),
                allocated_gb=0.0,
                reserved_gb=0.0,
                free_gb=self.max_vram_gb,
                utilization_percent=0.0
            )
        
        allocated = torch.cuda.memory_allocated(0) / (1024**3)
        reserved = torch.cuda.memory_reserved(0) / (1024**3)
        free = self.max_vram_gb - allocated
        utilization = (allocated / self.max_vram_gb) * 100
        
        snapshot = VRAMSnapshot(
            timestamp=datetime.now(),
            allocated_gb=allocated,
            reserved_gb=reserved,
            free_gb=free,
            utilization_percent=utilization
        )
        
        # Ajouter aux snapshots
        self.snapshots.append(snapshot)
        if len(self.snapshots) > self.max_snapshots:
            self.snapshots.pop(0)
        
        return snapshot
    
    def cleanup_vram(self, aggressive: bool = False):
        """
        Nettoie la VRAM.
        
        Args:
            aggressive: Mode agressif (force le garbage collection Python)
        """
        if not torch.cuda.is_available():
            return
        
        before = self.get_vram_usage()
        
        # Nettoyage CUDA
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        
        if aggressive:
            # Garbage collection Python agressif
            gc.collect()
            gc.collect()  # Double pass
            gc.collect()
            
            # Re-nettoyer CUDA après GC
            torch.cuda.empty_cache()
            
            self.aggressive_cleanups += 1
            self.logger.info("Aggressive VRAM cleanup performed")
        
        self.total_cleanups += 1
        self._last_cleanup = datetime.now()
        
        if aggressive:
            self._last_aggressive_cleanup = datetime.now()
        
        # Mesurer l'effet
        after = self.get_vram_usage()
        freed = before.allocated_gb - after.allocated_gb
        
        if freed > 0.1:  # Si au moins 100MB libérés
            self.logger.info(
                f"VRAM cleanup freed {freed:.2f} GB "
                f"({before.allocated_gb:.2f} → {after.allocated_gb:.2f} GB)"
            )
    
    def should_cleanup(self) -> tuple[bool, bool]:
        """
        Détermine si un nettoyage est nécessaire.
        
        Returns:
            (should_cleanup, should_be_aggressive)
        """
        snapshot = self.get_vram_usage()
        
        # Vérifier si nettoyage agressif nécessaire
        if snapshot.utilization_percent > self.AGGRESSIVE_THRESHOLD_PERCENT:
            # Vérifier le cooldown
            if self._last_aggressive_cleanup:
                time_since = (datetime.now() - self._last_aggressive_cleanup).total_seconds()
                if time_since < self.AGGRESSIVE_INTERVAL:
                    return False, False
            return True, True
        
        # Vérifier si nettoyage normal nécessaire
        if snapshot.utilization_percent > self.CLEANUP_THRESHOLD_PERCENT:
            if self._last_cleanup:
                time_since = (datetime.now() - self._last_cleanup).total_seconds()
                if time_since < self.NORMAL_INTERVAL:
                    return False, False
            return True, False
        
        return False, False
    
    async def start_monitoring(self):
        """Démarre le monitoring VRAM en arrière-plan."""
        if self._is_monitoring:
            return
        
        self._is_monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        self.logger.info("VRAM Guardian monitoring started")
    
    async def stop_monitoring(self):
        """Arrête le monitoring VRAM."""
        if not self._is_monitoring:
            return
        
        self._is_monitoring = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("VRAM Guardian monitoring stopped")
    
    async def _monitor_loop(self):
        """Boucle de monitoring VRAM."""
        while self._is_monitoring:
            try:
                # Vérifier si nettoyage nécessaire
                should_clean, aggressive = self.should_cleanup()
                
                if should_clean:
                    self.cleanup_vram(aggressive=aggressive)
                
                # Attendre avant la prochaine vérification
                await asyncio.sleep(5.0)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in VRAM monitor loop: {e}", exc_info=True)
                await asyncio.sleep(5.0)
    
    def get_stats(self) -> dict:
        """
        Retourne les statistiques du gardien.
        
        Returns:
            Dict avec les métriques
        """
        current = self.get_vram_usage()
        
        # Calculer la moyenne d'utilisation
        avg_utilization = 0.0
        if self.snapshots:
            avg_utilization = sum(s.utilization_percent for s in self.snapshots) / len(self.snapshots)
        
        # Pic d'utilisation
        peak_utilization = 0.0
        if self.snapshots:
            peak_utilization = max(s.utilization_percent for s in self.snapshots)
        
        return {
            "current_allocated_gb": current.allocated_gb,
            "current_utilization_percent": current.utilization_percent,
            "average_utilization_percent": avg_utilization,
            "peak_utilization_percent": peak_utilization,
            "total_cleanups": self.total_cleanups,
            "aggressive_cleanups": self.aggressive_cleanups,
            "snapshots_count": len(self.snapshots)
        }
    
    def print_report(self):
        """Affiche un rapport détaillé."""
        stats = self.get_stats()
        
        print("\n" + "="*70)
        print("VRAM GUARDIAN REPORT")
        print("="*70 + "\n")
        
        print(f"Current Usage: {stats['current_allocated_gb']:.2f} GB "
              f"({stats['current_utilization_percent']:.1f}%)")
        print(f"Average Usage: {stats['average_utilization_percent']:.1f}%")
        print(f"Peak Usage: {stats['peak_utilization_percent']:.1f}%")
        print(f"\nTotal Cleanups: {stats['total_cleanups']}")
        print(f"Aggressive Cleanups: {stats['aggressive_cleanups']}")
        
        print("\n" + "="*70 + "\n")


# Singleton
_guardian_instance: Optional[VRAMGuardian] = None

def get_vram_guardian() -> VRAMGuardian:
    """Retourne l'instance singleton."""
    global _guardian_instance
    if _guardian_instance is None:
        _guardian_instance = VRAMGuardian(max_vram_gb=8.0)
    return _guardian_instance
