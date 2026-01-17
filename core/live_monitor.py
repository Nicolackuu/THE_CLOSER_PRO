"""
THE CLOSER PRO v0.25 - Live Monitoring Loop
Boucle de monitoring en temps réel pour affichage continu du Talk-Ratio.
Intégration avec Real-time UI et Sales Intelligence.

Author: THE CLOSER PRO Team
Version: 0.25 (Elite Edition)
"""

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main_v25 import TheCloserProV25


async def live_monitoring_loop(app: 'TheCloserProV25'):
    """
    Boucle de monitoring live.
    Affiche le Talk-Ratio et les alertes en temps réel.
    
    Args:
        app: Instance de TheCloserProV25
    """
    last_warning_check = None
    
    while app._is_running:
        try:
            # Calculer la durée de session
            if app._session_start:
                session_duration = (datetime.now() - app._session_start).total_seconds()
            else:
                session_duration = 0.0
            
            # Récupérer le ratio actuel
            ratio = app.analytics.get_current_ratio()
            
            # Récupérer le smart summary
            summary = app.sales_intelligence.get_smart_summary()
            
            # Afficher les stats live
            app.realtime_ui.display_live_stats(
                vous_pct=ratio["vous_percentage"],
                client_pct=ratio["client_percentage"],
                session_duration=session_duration,
                objections_count=summary["objections"]["active"],
                last_agreement=summary["last_agreement"]
            )
            
            # Vérifier et afficher les warnings (toutes les 30s)
            if last_warning_check is None or (datetime.now() - last_warning_check).total_seconds() > 30:
                app.realtime_ui.check_and_display_warnings(ratio["vous_percentage"])
                last_warning_check = datetime.now()
            
            # Attendre avant la prochaine mise à jour
            await asyncio.sleep(2.0)
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            app.logger.error(f"Error in live monitoring loop: {e}", exc_info=True)
            await asyncio.sleep(2.0)


def check_realtime_alerts(app: 'TheCloserProV25', text: str):
    """
    Vérifie et affiche les alertes en temps réel.
    
    Args:
        app: Instance de TheCloserProV25
        text: Texte à analyser
    """
    # Vérifier les nouvelles objections
    if app.sales_intelligence.objections:
        latest_objection = app.sales_intelligence.objections[-1]
        
        # Afficher l'alerte si c'est une nouvelle objection
        app.realtime_ui.display_objection_alert(
            objection_type=latest_objection.type,
            objection_text=latest_objection.text,
            severity=latest_objection.severity
        )
    
    # Vérifier les nouveaux budgets
    if app.sales_intelligence.budgets:
        latest_budget = app.sales_intelligence.budgets[-1]
        
        # Afficher l'alerte
        app.realtime_ui.display_budget_alert(
            amount=latest_budget.amount,
            currency=latest_budget.currency,
            speaker=latest_budget.speaker
        )
    
    # Vérifier les nouveaux accords
    if app.sales_intelligence.agreement_points:
        latest_agreement = app.sales_intelligence.agreement_points[-1]
        
        # Afficher l'alerte
        app.realtime_ui.display_agreement_alert(
            agreement_text=latest_agreement.description
        )


def export_session_summary(app: 'TheCloserProV25'):
    """
    Exporte le résumé de session enrichi.
    
    Args:
        app: Instance de TheCloserProV25
    """
    try:
        # Calculer la durée
        if app._session_start:
            session_duration = (datetime.now() - app._session_start).total_seconds()
        else:
            session_duration = 0.0
        
        # Récupérer toutes les données
        dashboard = app.analytics.get_dashboard_data()
        intelligence = app.sales_intelligence.get_smart_summary()
        transcriber_stats = app.transcriber.get_stats()
        gpu_stats = app.transcriber.gpu_manager.get_performance_report()
        
        # Exporter
        output_path = app.session_exporter.export_session(
            analytics_data=dashboard,
            intelligence_data=intelligence,
            transcriber_stats=transcriber_stats,
            gpu_stats=gpu_stats,
            session_duration=session_duration,
            transcription_file=app._output_file
        )
        
        print(f"\n{Fore.GREEN}[EXPORT]{Style.RESET_ALL} Session summary: {output_path}")
        
        # Afficher les recommandations IA
        recommendation = app.sales_intelligence.generate_ai_recommendation()
        print(f"\n{Fore.CYAN}{'═'*70}")
        print(f"{Fore.CYAN}AI RECOMMENDATIONS FOR FOLLOW-UP{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'═'*70}{Style.RESET_ALL}")
        print(f"\n{recommendation}\n")
        
    except Exception as e:
        app.logger.error(f"Failed to export session summary: {e}", exc_info=True)
