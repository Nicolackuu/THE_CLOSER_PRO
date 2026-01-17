"""
THE CLOSER PRO v0.25 - Session Exporter
Génère session_summary.json avec score, objections et recommandations IA.
Export enrichi pour analyse post-session.

Author: THE CLOSER PRO Team
Version: 0.25 (Elite Edition)
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
import logging


class SessionExporter:
    """
    Exporteur de sessions enrichies.
    Génère des rapports JSON détaillés avec recommandations IA.
    """
    
    def __init__(self, output_dir: str = "sessions"):
        """
        Initialise l'exporteur.
        
        Args:
            output_dir: Répertoire de sortie pour les sessions
        """
        self.logger = logging.getLogger(__name__)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def export_session(
        self,
        analytics_data: Dict,
        intelligence_data: Dict,
        transcriber_stats: Dict,
        gpu_stats: Dict,
        session_duration: float,
        transcription_file: Optional[Path] = None
    ) -> Path:
        """
        Exporte une session complète en JSON.
        
        Args:
            analytics_data: Données du moteur d'analytics
            intelligence_data: Smart summary de l'intelligence
            transcriber_stats: Stats du transcripteur
            gpu_stats: Stats GPU
            session_duration: Durée de session (secondes)
            transcription_file: Fichier de transcription brute
        
        Returns:
            Path du fichier JSON généré
        """
        # Générer le nom de fichier
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"session_summary_{timestamp}.json"
        output_path = self.output_dir / filename
        
        # Construire le rapport
        report = {
            "metadata": {
                "session_date": datetime.now().isoformat(),
                "session_duration_seconds": session_duration,
                "session_duration_formatted": self._format_duration(session_duration),
                "version": "0.25 (Elite Edition)",
                "transcription_file": str(transcription_file) if transcription_file else None
            },
            
            "performance": {
                "talk_ratio": {
                    "vous_percentage": analytics_data["ratio"]["vous_percentage"],
                    "client_percentage": analytics_data["ratio"]["client_percentage"],
                    "vous_duration_seconds": analytics_data["ratio"]["vous_duration"],
                    "client_duration_seconds": analytics_data["ratio"]["client_duration"],
                    "quality_score": analytics_data["quality_score"],
                    "quality_grade": analytics_data["quality_grade"],
                    "trend": analytics_data["trend"]
                },
                
                "speaker_metrics": {
                    "vous": {
                        "total_segments": analytics_data["vous_metrics"]["total_segments"],
                        "average_segment_duration": analytics_data["vous_metrics"]["average_duration"],
                        "interruptions": analytics_data["vous_metrics"]["interruptions"],
                        "longest_segment": analytics_data["vous_metrics"]["longest_segment"]
                    },
                    "client": {
                        "total_segments": analytics_data["client_metrics"]["total_segments"],
                        "average_segment_duration": analytics_data["client_metrics"]["average_duration"],
                        "interruptions": analytics_data["client_metrics"]["interruptions"],
                        "longest_segment": analytics_data["client_metrics"]["longest_segment"]
                    }
                }
            },
            
            "sales_intelligence": {
                "budgets": {
                    "client_budget_average": intelligence_data["budgets"]["client_budget_avg"],
                    "your_price_average": intelligence_data["budgets"]["your_price_avg"],
                    "total_mentions": intelligence_data["budgets"]["total_mentions"],
                    "price_gap": intelligence_data["budgets"]["your_price_avg"] - intelligence_data["budgets"]["client_budget_avg"]
                },
                
                "objections": {
                    "total_detected": intelligence_data["objections"]["total"],
                    "active_unresolved": intelligence_data["objections"]["active"],
                    "by_type": intelligence_data["objections"]["by_type"],
                    "most_severe": intelligence_data["objections"]["most_severe"]
                },
                
                "entities": {
                    "names_detected": intelligence_data["entities"]["names"],
                    "total_entities": intelligence_data["entities"]["total"]
                },
                
                "agreements": {
                    "total_count": intelligence_data["agreement_count"],
                    "last_agreement": intelligence_data["last_agreement"]
                }
            },
            
            "technical_stats": {
                "transcription": {
                    "total_transcriptions": transcriber_stats["total_transcriptions"],
                    "average_inference_time": transcriber_stats["average_inference_time"],
                    "errors_count": transcriber_stats["errors_count"],
                    "context_segments": transcriber_stats["context_segments"]
                },
                
                "gpu": {
                    "profile_used": gpu_stats["current_profile"],
                    "vram_usage_gb": gpu_stats["current_vram_gb"],
                    "average_vram_gb": gpu_stats["average_vram_gb"],
                    "total_adjustments": gpu_stats["total_adjustments"],
                    "lag_events": gpu_stats["lag_events"]
                }
            },
            
            "ai_recommendations": {
                "overall_score": analytics_data["quality_score"],
                "grade": analytics_data["quality_grade"],
                "main_recommendation": analytics_data["recommendation"],
                "follow_up_strategy": self._generate_followup_strategy(
                    analytics_data,
                    intelligence_data
                ),
                "action_items": self._generate_action_items(
                    analytics_data,
                    intelligence_data
                )
            }
        }
        
        # Sauvegarder en JSON
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Session summary exported to {output_path}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"Failed to export session: {e}", exc_info=True)
            raise
    
    def _format_duration(self, seconds: float) -> str:
        """
        Formate une durée en HH:MM:SS.
        
        Args:
            seconds: Durée en secondes
        
        Returns:
            Durée formatée
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"
    
    def _generate_followup_strategy(
        self,
        analytics: Dict,
        intelligence: Dict
    ) -> str:
        """
        Génère une stratégie de follow-up personnalisée.
        
        Args:
            analytics: Données analytics
            intelligence: Données intelligence
        
        Returns:
            Stratégie de follow-up
        """
        strategies = []
        
        # Basé sur le quality score
        score = analytics["quality_score"]
        
        if score >= 80:
            strategies.append(
                "✅ Excellente session ! Envoyez un email de confirmation dans les 2h "
                "avec un récapitulatif des points d'accord."
            )
        elif score >= 60:
            strategies.append(
                "⚡ Session correcte. Follow-up dans les 24h pour clarifier les points "
                "restants et traiter les objections."
            )
        else:
            strategies.append(
                "⚠️ Session difficile. Requalifiez le besoin avant le prochain contact. "
                "Attendez 48h puis relancez avec une nouvelle approche."
            )
        
        # Basé sur les objections
        if intelligence["objections"]["active"] > 0:
            main_obj = intelligence["objections"]["most_severe"]
            if main_obj:
                strategies.append(
                    f"🎯 Préparez une réponse solide à l'objection '{main_obj['type']}' "
                    "avant le prochain contact."
                )
        
        # Basé sur le dernier accord
        if intelligence["last_agreement"]:
            strategies.append(
                f"📌 Rappelez le dernier point d'accord : \"{intelligence['last_agreement']}\""
            )
        
        return " | ".join(strategies)
    
    def _generate_action_items(
        self,
        analytics: Dict,
        intelligence: Dict
    ) -> list[str]:
        """
        Génère une liste d'actions à faire.
        
        Args:
            analytics: Données analytics
            intelligence: Données intelligence
        
        Returns:
            Liste d'actions
        """
        actions = []
        
        # Action sur le ratio
        vous_pct = analytics["ratio"]["vous_percentage"]
        if vous_pct > 60:
            actions.append(
                "🎯 Améliorer le ratio de parole : Posez plus de questions ouvertes (SPIN)"
            )
        
        # Actions sur les objections
        obj_types = intelligence["objections"]["by_type"]
        for obj_type, count in obj_types.items():
            if count > 0:
                actions.append(
                    f"⚠️ Préparer une réponse à {count} objection(s) de type '{obj_type}'"
                )
        
        # Action sur le budget
        if intelligence["budgets"]["client_budget_avg"] > 0:
            price_gap = intelligence["budgets"]["your_price_avg"] - intelligence["budgets"]["client_budget_avg"]
            if price_gap > 0:
                actions.append(
                    f"💰 Justifier l'écart de prix : {price_gap:.0f}€ au-dessus du budget client"
                )
        
        # Action sur les entités
        if intelligence["entities"]["names"]:
            actions.append(
                f"📝 Personnaliser le follow-up avec les noms : {', '.join(intelligence['entities']['names'][:3])}"
            )
        
        # Action par défaut
        if not actions:
            actions.append("📞 Envoyer un email de suivi dans les 24h")
        
        return actions


# Singleton
_exporter_instance: Optional[SessionExporter] = None

def get_session_exporter() -> SessionExporter:
    """Retourne l'instance singleton."""
    global _exporter_instance
    if _exporter_instance is None:
        _exporter_instance = SessionExporter()
    return _exporter_instance
