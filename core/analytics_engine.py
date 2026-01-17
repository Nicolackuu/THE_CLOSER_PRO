"""
THE CLOSER PRO V25 - Analytics Engine
Moteur d'analyse en temps réel pour le Talk-to-Listen Ratio.
Dashboard de performance pour optimiser les sessions de closing.

Author: THE CLOSER PRO Team
Version: 2.5.0 (Elite)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import deque
import logging


@dataclass
class SpeakerMetrics:
    """Métriques détaillées par locuteur."""
    total_speech_time: float = 0.0
    total_segments: int = 0
    average_segment_duration: float = 0.0
    longest_segment: float = 0.0
    shortest_segment: float = float('inf')
    interruptions: int = 0
    last_speech_time: Optional[datetime] = None
    
    def update(self, duration: float, timestamp: datetime):
        """Met à jour les métriques avec un nouveau segment."""
        self.total_speech_time += duration
        self.total_segments += 1
        self.last_speech_time = timestamp
        
        if duration > self.longest_segment:
            self.longest_segment = duration
        if duration < self.shortest_segment:
            self.shortest_segment = duration
        
        if self.total_segments > 0:
            self.average_segment_duration = self.total_speech_time / self.total_segments


@dataclass
class TalkRatioSnapshot:
    """Snapshot du ratio de parole à un instant T."""
    timestamp: datetime
    vous_percentage: float
    client_percentage: float
    vous_duration: float
    client_duration: float
    total_duration: float
    quality_score: float  # Score de qualité du closing (0-100)


class AnalyticsEngine:
    """
    Moteur d'analyse temps réel pour les sessions de closing.
    Calcule le Talk-to-Listen Ratio et génère des insights.
    """
    
    # Règles de closing (best practices)
    IDEAL_RATIO_VOUS = 30.0  # Vous devriez parler ~30% du temps
    IDEAL_RATIO_CLIENT = 70.0  # Le client devrait parler ~70% du temps
    
    def __init__(self, snapshot_interval: int = 30):
        """
        Initialise le moteur d'analytics.
        
        Args:
            snapshot_interval: Intervalle entre snapshots (secondes)
        """
        self.snapshot_interval = snapshot_interval
        
        # Métriques par locuteur
        self.vous_metrics = SpeakerMetrics()
        self.client_metrics = SpeakerMetrics()
        
        # Historique des snapshots
        self.snapshots: deque[TalkRatioSnapshot] = deque(maxlen=100)
        
        # Session tracking
        self.session_start: Optional[datetime] = None
        self.last_snapshot_time: Optional[datetime] = None
        
        # Détection d'interruptions
        self.last_speaker: Optional[str] = None
        self.last_speech_end: Optional[datetime] = None
        
        self.logger = logging.getLogger(__name__)
    
    def start_session(self):
        """Démarre une nouvelle session d'analyse."""
        self.session_start = datetime.now()
        self.last_snapshot_time = self.session_start
        self.vous_metrics = SpeakerMetrics()
        self.client_metrics = SpeakerMetrics()
        self.snapshots.clear()
        self.logger.info("Analytics session started")
    
    def record_speech(
        self,
        speaker: str,
        duration: float,
        timestamp: Optional[datetime] = None
    ):
        """
        Enregistre un segment de parole.
        
        Args:
            speaker: "VOUS" ou "CLIENT"
            duration: Durée du segment (secondes)
            timestamp: Timestamp du segment
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        # Mettre à jour les métriques du locuteur
        if speaker == "VOUS":
            self.vous_metrics.update(duration, timestamp)
        elif speaker == "CLIENT":
            self.client_metrics.update(duration, timestamp)
        
        # Détecter les interruptions
        if self.last_speaker and self.last_speaker != speaker:
            if self.last_speech_end:
                gap = (timestamp - self.last_speech_end).total_seconds()
                if gap < 0.5:  # Interruption si < 0.5s de gap
                    if speaker == "VOUS":
                        self.vous_metrics.interruptions += 1
                    else:
                        self.client_metrics.interruptions += 1
        
        self.last_speaker = speaker
        self.last_speech_end = timestamp + timedelta(seconds=duration)
        
        # Créer un snapshot si nécessaire
        if self.should_create_snapshot():
            self.create_snapshot()
    
    def should_create_snapshot(self) -> bool:
        """Détermine si un snapshot doit être créé."""
        if not self.last_snapshot_time:
            return True
        
        elapsed = (datetime.now() - self.last_snapshot_time).total_seconds()
        return elapsed >= self.snapshot_interval
    
    def create_snapshot(self) -> TalkRatioSnapshot:
        """
        Crée un snapshot du ratio actuel.
        
        Returns:
            TalkRatioSnapshot avec les données actuelles
        """
        ratio = self.get_current_ratio()
        quality = self.calculate_quality_score(
            ratio["vous_percentage"],
            ratio["client_percentage"]
        )
        
        snapshot = TalkRatioSnapshot(
            timestamp=datetime.now(),
            vous_percentage=ratio["vous_percentage"],
            client_percentage=ratio["client_percentage"],
            vous_duration=ratio["vous_duration"],
            client_duration=ratio["client_duration"],
            total_duration=ratio["total_duration"],
            quality_score=quality
        )
        
        self.snapshots.append(snapshot)
        self.last_snapshot_time = datetime.now()
        
        return snapshot
    
    def get_current_ratio(self) -> Dict[str, float]:
        """
        Calcule le ratio de parole actuel.
        
        Returns:
            Dict avec les pourcentages et durées
        """
        total_speech = self.vous_metrics.total_speech_time + self.client_metrics.total_speech_time
        
        if total_speech == 0:
            return {
                "vous_percentage": 0.0,
                "client_percentage": 0.0,
                "vous_duration": 0.0,
                "client_duration": 0.0,
                "total_duration": 0.0
            }
        
        vous_pct = (self.vous_metrics.total_speech_time / total_speech) * 100
        client_pct = (self.client_metrics.total_speech_time / total_speech) * 100
        
        return {
            "vous_percentage": vous_pct,
            "client_percentage": client_pct,
            "vous_duration": self.vous_metrics.total_speech_time,
            "client_duration": self.client_metrics.total_speech_time,
            "total_duration": total_speech
        }
    
    def calculate_quality_score(
        self,
        vous_pct: float,
        client_pct: float
    ) -> float:
        """
        Calcule un score de qualité du closing (0-100).
        Plus le ratio est proche de l'idéal (30/70), meilleur est le score.
        
        Args:
            vous_pct: Pourcentage de parole VOUS
            client_pct: Pourcentage de parole CLIENT
        
        Returns:
            Score de 0 à 100
        """
        if vous_pct == 0 and client_pct == 0:
            return 0.0
        
        # Calculer la déviation par rapport à l'idéal
        vous_deviation = abs(vous_pct - self.IDEAL_RATIO_VOUS)
        client_deviation = abs(client_pct - self.IDEAL_RATIO_CLIENT)
        
        # Moyenne des déviations
        avg_deviation = (vous_deviation + client_deviation) / 2
        
        # Convertir en score (0 déviation = 100, 50 déviation = 0)
        score = max(0, 100 - (avg_deviation * 2))
        
        return score
    
    def get_dashboard_data(self) -> Dict:
        """
        Génère les données pour le dashboard.
        
        Returns:
            Dict avec toutes les métriques formatées
        """
        ratio = self.get_current_ratio()
        quality = self.calculate_quality_score(
            ratio["vous_percentage"],
            ratio["client_percentage"]
        )
        
        # Calculer la durée de session
        session_duration = 0.0
        if self.session_start:
            session_duration = (datetime.now() - self.session_start).total_seconds()
        
        # Tendance (amélioration ou dégradation)
        trend = self._calculate_trend()
        
        return {
            "ratio": ratio,
            "quality_score": quality,
            "quality_grade": self._get_quality_grade(quality),
            "trend": trend,
            "session_duration": session_duration,
            "vous_metrics": {
                "total_segments": self.vous_metrics.total_segments,
                "average_duration": self.vous_metrics.average_segment_duration,
                "interruptions": self.vous_metrics.interruptions,
                "longest_segment": self.vous_metrics.longest_segment
            },
            "client_metrics": {
                "total_segments": self.client_metrics.total_segments,
                "average_duration": self.client_metrics.average_segment_duration,
                "interruptions": self.client_metrics.interruptions,
                "longest_segment": self.client_metrics.longest_segment
            },
            "recommendation": self._get_recommendation(ratio["vous_percentage"])
        }
    
    def _calculate_trend(self) -> str:
        """
        Calcule la tendance du quality score.
        
        Returns:
            "improving", "stable", ou "declining"
        """
        if len(self.snapshots) < 3:
            return "stable"
        
        # Comparer les 3 derniers snapshots
        recent = list(self.snapshots)[-3:]
        scores = [s.quality_score for s in recent]
        
        # Calculer la pente
        if scores[-1] > scores[0] + 5:
            return "improving"
        elif scores[-1] < scores[0] - 5:
            return "declining"
        else:
            return "stable"
    
    def _get_quality_grade(self, score: float) -> str:
        """
        Convertit le score en grade.
        
        Args:
            score: Score de qualité (0-100)
        
        Returns:
            Grade (S, A, B, C, D, F)
        """
        if score >= 90:
            return "S"  # Elite
        elif score >= 80:
            return "A"  # Excellent
        elif score >= 70:
            return "B"  # Bon
        elif score >= 60:
            return "C"  # Moyen
        elif score >= 50:
            return "D"  # Faible
        else:
            return "F"  # Critique
    
    def _get_recommendation(self, vous_pct: float) -> str:
        """
        Génère une recommandation basée sur le ratio.
        
        Args:
            vous_pct: Pourcentage de parole VOUS
        
        Returns:
            Recommandation textuelle
        """
        if vous_pct > 50:
            return "⚠️ Vous parlez trop ! Posez plus de questions et écoutez."
        elif vous_pct > 40:
            return "⚡ Réduisez légèrement votre temps de parole."
        elif vous_pct >= 25 and vous_pct <= 35:
            return "✅ Ratio optimal ! Continuez comme ça."
        elif vous_pct < 20:
            return "💬 Vous pouvez parler un peu plus pour guider la conversation."
        else:
            return "📊 Ratio correct, restez à l'écoute."
    
    def get_formatted_ratio_bar(self, width: int = 50) -> str:
        """
        Génère une barre de progression visuelle du ratio.
        
        Args:
            width: Largeur de la barre en caractères
        
        Returns:
            Barre de progression formatée
        """
        ratio = self.get_current_ratio()
        vous_pct = ratio["vous_percentage"]
        
        vous_width = int((vous_pct / 100) * width)
        client_width = width - vous_width
        
        bar = "█" * vous_width + "░" * client_width
        
        return f"[{bar}] VOUS: {vous_pct:.1f}% | CLIENT: {ratio['client_percentage']:.1f}%"
    
    def export_session_report(self) -> Dict:
        """
        Exporte un rapport complet de session.
        
        Returns:
            Dict avec toutes les données de session
        """
        dashboard = self.get_dashboard_data()
        
        return {
            "session_start": self.session_start.isoformat() if self.session_start else None,
            "session_duration": dashboard["session_duration"],
            "final_ratio": dashboard["ratio"],
            "quality_score": dashboard["quality_score"],
            "quality_grade": dashboard["quality_grade"],
            "trend": dashboard["trend"],
            "vous_stats": dashboard["vous_metrics"],
            "client_stats": dashboard["client_metrics"],
            "snapshots_count": len(self.snapshots),
            "recommendation": dashboard["recommendation"]
        }
