"""
THE CLOSER PRO V25 - Elite Main Orchestrator
Architecture asynchrone professionnelle avec dual-stream, analytics et self-healing.
Conçu pour les sessions de closing haute performance.

Author: THE CLOSER PRO Team
Version: 2.5.0 (Elite)
"""

# CRITICAL: Force Windows to load DLLs from project directory FIRST
import os
if os.name == 'nt':
    import ctypes
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.add_dll_directory(project_dir)

import asyncio
import signal
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from colorama import init, Fore, Style

# Apply CUDA DLL fix BEFORE any torch imports
from core.cuda_dll_fixer import apply_cuda_fix
apply_cuda_fix()

from config.manager import get_config
from core.audio_streamer import AudioStreamer, AudioChunk
from core.dual_stream_manager import DualStreamManager, AudioStream
from core.transcriber_v25 import get_elite_transcriber, TranscriptionResult
from core.analytics_engine import AnalyticsEngine
from core.processor import get_processor
from core.sales_intelligence import get_sales_intelligence
from core.realtime_ui import get_realtime_ui
from core.vram_guardian import get_vram_guardian
from core.session_exporter import get_session_exporter

init(autoreset=True)


class TheCloserProV25:
    """
    Orchestrateur Elite V25 - Architecture asynchrone professionnelle.
    Intègre dual-stream, context memory, GPU self-healing et analytics temps réel.
    """
    
    def __init__(self):
        """Initialise l'orchestrateur V25."""
        self.config = get_config()
        self.logger = self._setup_logging()
        
        # Composants Elite v0.25
        self.transcriber = get_elite_transcriber()
        self.analytics = AnalyticsEngine(snapshot_interval=30)
        self.processor = get_processor()
        self.sales_intelligence = get_sales_intelligence()
        self.realtime_ui = get_realtime_ui()
        self.vram_guardian = get_vram_guardian()
        self.session_exporter = get_session_exporter()
        
        # Dual-stream manager
        self.dual_stream: Optional[DualStreamManager] = None
        
        # Audio streamer
        self.audio_streamer: Optional[AudioStreamer] = None
        
        # État
        self._is_running = False
        self._output_file: Optional[Path] = None
        self._session_start: Optional[datetime] = None
        
        # Live monitoring
        self._live_monitor_task: Optional[asyncio.Task] = None
        
        # Asyncio event loop
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        
        # Signal handling
        self._shutdown_event = asyncio.Event()
    
    def _setup_logging(self) -> logging.Logger:
        """Configure le logging vers fichier uniquement."""
        log_file = Path('system_v25.log')
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, mode='w', encoding='utf-8')
            ]
        )
        
        # Silence les modules bruyants
        logging.getLogger('faster_whisper').setLevel(logging.WARNING)
        logging.getLogger('core.audio_streamer').setLevel(logging.WARNING)
        
        return logging.getLogger(__name__)
    
    def _setup_output_file(self):
        """Configure le fichier de sortie."""
        if self.config.system.output_format in ["file", "both"]:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._output_file = Path(f"transcription_v25_{timestamp}.txt")
            self._output_file.parent.mkdir(parents=True, exist_ok=True)
    
    async def _process_left_channel(self, stream: AudioStream):
        """
        Traite le canal GAUCHE (VOUS) de manière asynchrone.
        
        Args:
            stream: Flux audio du canal gauche
        """
        try:
            # Transcrire avec context memory
            result = await self.transcriber.transcribe_stream(
                audio_data=stream.data,
                speaker="VOUS",
                timestamp=stream.timestamp
            )
            
            if result and result.text:
                # Nettoyer avec le processor
                cleaned = self.processor.clean_text(result.text)
                
                if cleaned and not self.processor.is_hallucination(cleaned):
                    # Analyser avec Sales Intelligence
                    self.sales_intelligence.analyze_text(
                        text=cleaned,
                        speaker="VOUS",
                        timestamp=result.timestamp
                    )
                    
                    # Enregistrer dans analytics
                    self.analytics.record_speech(
                        speaker="VOUS",
                        duration=result.duration,
                        timestamp=result.timestamp
                    )
                    
                    # Afficher
                    self._display_transcription(result, cleaned)
                    
        except Exception as e:
            self.logger.error(f"Error processing left channel: {e}", exc_info=True)
    
    async def _process_right_channel(self, stream: AudioStream):
        """
        Traite le canal DROIT (CLIENT) de manière asynchrone.
        
        Args:
            stream: Flux audio du canal droit
        """
        try:
            result = await self.transcriber.transcribe_stream(
                audio_data=stream.data,
                speaker="CLIENT",
                timestamp=stream.timestamp
            )
            
            if result and result.text:
                cleaned = self.processor.clean_text(result.text)
                
                if cleaned and not self.processor.is_hallucination(cleaned):
                    # Analyser avec Sales Intelligence
                    self.sales_intelligence.analyze_text(
                        text=cleaned,
                        speaker="CLIENT",
                        timestamp=result.timestamp
                    )
                    
                    # Enregistrer dans analytics
                    self.analytics.record_speech(
                        speaker="CLIENT",
                        duration=result.duration,
                        timestamp=result.timestamp
                    )
                    
                    # Afficher
                    self._display_transcription(result, cleaned)
                    
                    # Alertes en temps réel pour objections/budgets
                    self._check_realtime_alerts(cleaned)
                    
        except Exception as e:
            self.logger.error(f"Error processing right channel: {e}", exc_info=True)
    
    def _check_realtime_alerts(self, text: str):
        """
        Vérifie et affiche les alertes en temps réel.
        
        Args:
            text: Texte à analyser
        """
        # Vérifier les nouvelles objections
        if self.sales_intelligence.objections:
            latest_objection = self.sales_intelligence.objections[-1]
            if (datetime.now() - latest_objection.timestamp).total_seconds() < 2.0:
                self.realtime_ui.display_objection_alert(
                    objection_type=latest_objection.type,
                    objection_text=latest_objection.text,
                    severity=latest_objection.severity
                )
        
        # Vérifier les nouveaux budgets
        if self.sales_intelligence.budgets:
            latest_budget = self.sales_intelligence.budgets[-1]
            if (datetime.now() - latest_budget.timestamp).total_seconds() < 2.0:
                self.realtime_ui.display_budget_alert(
                    amount=latest_budget.amount,
                    currency=latest_budget.currency,
                    speaker=latest_budget.speaker
                )
        
        # Vérifier les nouveaux accords
        if self.sales_intelligence.agreement_points:
            latest_agreement = self.sales_intelligence.agreement_points[-1]
            if (datetime.now() - latest_agreement.timestamp).total_seconds() < 2.0:
                self.realtime_ui.display_agreement_alert(
                    agreement_text=latest_agreement.description
                )
    
    async def _live_monitoring_loop(self):
        """
        Boucle de monitoring live.
        Affiche le Talk-Ratio et les alertes en temps réel.
        """
        last_warning_check = None
        
        while self._is_running:
            try:
                # Calculer la durée de session
                if self._session_start:
                    session_duration = (datetime.now() - self._session_start).total_seconds()
                else:
                    session_duration = 0.0
                
                # Récupérer le ratio actuel
                ratio = self.analytics.get_current_ratio()
                
                # Récupérer le smart summary
                summary = self.sales_intelligence.get_smart_summary()
                
                # Afficher les stats live
                self.realtime_ui.display_live_stats(
                    vous_pct=ratio["vous_percentage"],
                    client_pct=ratio["client_percentage"],
                    session_duration=session_duration,
                    objections_count=summary["objections"]["active"],
                    last_agreement=summary["last_agreement"]
                )
                
                # Vérifier et afficher les warnings (toutes les 30s)
                if last_warning_check is None or (datetime.now() - last_warning_check).total_seconds() > 30:
                    self.realtime_ui.check_and_display_warnings(ratio["vous_percentage"])
                    last_warning_check = datetime.now()
                
                # Attendre avant la prochaine mise à jour
                await asyncio.sleep(2.0)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in live monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(2.0)
    
    def _display_transcription(self, result: TranscriptionResult, text: str):
        """
        Affiche une transcription avec le format chat Elite.
        
        Args:
            result: Résultat de transcription
            text: Texte nettoyé
        """
        timestamp = result.timestamp.strftime("%H:%M:%S")
        
        # Couleur selon le speaker
        if result.speaker == "VOUS":
            color = Fore.GREEN
        else:
            color = Fore.CYAN
        
        # Affichage console
        formatted = f"[{timestamp}] {color}[{result.speaker}]{Style.RESET_ALL} -> \"{text}\""
        print(formatted, flush=True)
        
        # Sauvegarde fichier
        if self._output_file:
            try:
                plain = f"[{timestamp}] [{result.speaker}] -> \"{text}\"\n"
                with open(self._output_file, 'a', encoding='utf-8') as f:
                    f.write(plain)
            except Exception as e:
                self.logger.error(f"File write error: {e}")
    
    def _audio_callback(self, chunk: AudioChunk):
        """
        Callback pour les chunks audio du streamer.
        Soumet au dual-stream manager de manière asynchrone.
        
        Args:
            chunk: Chunk audio stéréo
        """
        if self.dual_stream and self.loop:
            # Soumettre de manière thread-safe
            asyncio.run_coroutine_threadsafe(
                self.dual_stream.submit_stereo_chunk(chunk.data, chunk.timestamp),
                self.loop
            )
    
    async def start(self):
        """Démarre le système V25."""
        if self._is_running:
            raise RuntimeError("System already running")
        
        try:
            # Clear screen et banner
            os.system('cls' if os.name == 'nt' else 'clear')
            
            print(f"{Fore.CYAN}" + "="*70)
            print(f"{Fore.CYAN}╔═══════════════════════════════════════════════════════════════════╗")
            print(f"{Fore.CYAN}║{Fore.WHITE}              THE CLOSER PRO - v0.25 (Core Engine)                {Fore.CYAN}║")
            print(f"{Fore.CYAN}║{Fore.WHITE}        Dual-Stream • Context Memory • Self-Healing GPU           {Fore.CYAN}║")
            print(f"{Fore.CYAN}╚═══════════════════════════════════════════════════════════════════╝")
            print(f"{Fore.CYAN}" + "="*70 + Style.RESET_ALL)
            print()
            
            # Validation config
            self.config.validate()
            self._setup_output_file()
            
            # Initialiser le transcripteur Elite
            print(f"{Fore.YELLOW}[INIT]{Style.RESET_ALL} Chargement du modèle Whisper Elite...")
            await self.transcriber.initialize()
            
            # Démarrer analytics
            self.analytics.start_session()
            
            # Démarrer VRAM Guardian
            print(f"{Fore.YELLOW}[INIT]{Style.RESET_ALL} Activation du VRAM Guardian...")
            await self.vram_guardian.start_monitoring()
            
            # Créer le dual-stream manager
            print(f"{Fore.YELLOW}[INIT]{Style.RESET_ALL} Initialisation du système dual-stream...")
            self.dual_stream = DualStreamManager(
                left_callback=self._process_left_channel,
                right_callback=self._process_right_channel,
                max_queue_size=50,
                sample_rate=self.config.audio.sample_rate
            )
            await self.dual_stream.start()
            
            # Démarrer l'audio streamer
            print(f"{Fore.YELLOW}[INIT]{Style.RESET_ALL} Démarrage de la capture audio...")
            self.audio_streamer = AudioStreamer(callback=self._audio_callback)
            self.audio_streamer.start()
            
            self._is_running = True
            self._session_start = datetime.now()
            
            print(f"{Fore.GREEN}[READY]{Style.RESET_ALL} Système v0.25 Elite opérationnel - Parlez maintenant !")
            print(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Architecture: Dual-Stream Zero-Overlap")
            print(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Intelligence: Entity & Objection Detection")
            print(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Analytics: Live Talk-Ratio Monitoring")
            print(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} GPU: VRAM Guardian + Self-Healing")
            print(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Appuyez sur Ctrl+C pour arrêter\n")
            
            # Afficher l'en-tête de monitoring
            self.realtime_ui.display_session_header()
            
            # Démarrer le monitoring live
            self._live_monitor_task = asyncio.create_task(self._live_monitoring_loop())
            
        except Exception as e:
            self.logger.error(f"Startup failed: {e}", exc_info=True)
            await self.stop()
            raise
    
    async def stop(self):
        """Arrête proprement tous les composants."""
        if not self._is_running:
            return
        
        print(f"\n\n{Fore.YELLOW}[SHUTDOWN]{Style.RESET_ALL} Arrêt du système V25...")
        
        self._is_running = False
        
        # Arrêter l'audio streamer
        if self.audio_streamer:
            self.audio_streamer.stop()
        
        # Arrêter le monitoring live
        if self._live_monitor_task:
            self._live_monitor_task.cancel()
            try:
                await self._live_monitor_task
            except asyncio.CancelledError:
                pass
        
        # Arrêter le dual-stream
        if self.dual_stream:
            await self.dual_stream.stop()
        
        # Arrêter le VRAM Guardian
        await self.vram_guardian.stop_monitoring()
        
        # Arrêter le transcripteur
        await self.transcriber.shutdown()
        
        # Afficher les statistiques finales
        self._display_final_stats()
        
        # Exporter la session
        self._export_session_summary()
        
        print(f"\n{Fore.GREEN}[DONE]{Style.RESET_ALL} Session terminée.")
    
    def _export_session_summary(self):
        """
        Exporte le résumé de session enrichi.
        """
        try:
            # Calculer la durée
            if self._session_start:
                session_duration = (datetime.now() - self._session_start).total_seconds()
            else:
                session_duration = 0.0
            
            # Récupérer toutes les données
            dashboard = self.analytics.get_dashboard_data()
            intelligence = self.sales_intelligence.get_smart_summary()
            transcriber_stats = self.transcriber.get_stats()
            gpu_stats = self.transcriber.gpu_manager.get_performance_report()
            
            # Exporter
            output_path = self.session_exporter.export_session(
                analytics_data=dashboard,
                intelligence_data=intelligence,
                transcriber_stats=transcriber_stats,
                gpu_stats=gpu_stats,
                session_duration=session_duration,
                transcription_file=self._output_file
            )
            
            print(f"\n{Fore.GREEN}[EXPORT]{Style.RESET_ALL} Session summary: {output_path}")
            
            # Afficher les recommandations IA
            recommendation = self.sales_intelligence.generate_ai_recommendation()
            print(f"\n{Fore.CYAN}{'═'*70}")
            print(f"{Fore.CYAN}AI RECOMMENDATIONS FOR FOLLOW-UP{Style.RESET_ALL}")
            print(f"{Fore.CYAN}{'═'*70}{Style.RESET_ALL}")
            print(f"\n{recommendation}\n")
            
        except Exception as e:
            self.logger.error(f"Failed to export session summary: {e}", exc_info=True)
        if self._output_file:
            print(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Transcription: {self._output_file}\n")
    
    def _display_final_stats(self):
        """Affiche les statistiques finales de session."""
        print(f"\n{Fore.CYAN}" + "═"*70 + Style.RESET_ALL)
        print(f"{Fore.CYAN}║{Fore.WHITE}                     STATISTIQUES DE SESSION V25                   {Fore.CYAN}║")
        print(f"{Fore.CYAN}" + "═"*70 + Style.RESET_ALL)
        
        # Analytics
        dashboard = self.analytics.get_dashboard_data()
        ratio = dashboard["ratio"]
        
        # Talk Ratio
        print(f"\n{Fore.WHITE}📊 TALK-TO-LISTEN RATIO:{Style.RESET_ALL}")
        print(self.analytics.get_formatted_ratio_bar(50))
        print(f"{Fore.GREEN}   VOUS:{Style.RESET_ALL}   {ratio['vous_duration']:.1f}s ({ratio['vous_percentage']:.1f}%)")
        print(f"{Fore.CYAN}   CLIENT:{Style.RESET_ALL} {ratio['client_duration']:.1f}s ({ratio['client_percentage']:.1f}%)")
        
        # Quality Score
        quality = dashboard["quality_score"]
        grade = dashboard["quality_grade"]
        
        grade_color = Fore.GREEN if grade in ["S", "A"] else Fore.YELLOW if grade == "B" else Fore.RED
        print(f"\n{Fore.WHITE}🎯 QUALITY SCORE:{Style.RESET_ALL} {quality:.1f}/100 {grade_color}[{grade}]{Style.RESET_ALL}")
        print(f"{Fore.WHITE}📈 TENDANCE:{Style.RESET_ALL} {dashboard['trend'].upper()}")
        
        # Recommandation
        print(f"\n{Fore.WHITE}💡 RECOMMANDATION:{Style.RESET_ALL}")
        print(f"   {dashboard['recommendation']}")
        
        # Métriques détaillées
        print(f"\n{Fore.WHITE}📋 DÉTAILS:{Style.RESET_ALL}")
        print(f"   VOUS: {dashboard['vous_metrics']['total_segments']} segments, "
              f"moy {dashboard['vous_metrics']['average_duration']:.1f}s, "
              f"{dashboard['vous_metrics']['interruptions']} interruptions")
        print(f"   CLIENT: {dashboard['client_metrics']['total_segments']} segments, "
              f"moy {dashboard['client_metrics']['average_duration']:.1f}s, "
              f"{dashboard['client_metrics']['interruptions']} interruptions")
        
        # Stats transcripteur
        trans_stats = self.transcriber.get_stats()
        print(f"\n{Fore.WHITE}⚡ PERFORMANCE GPU:{Style.RESET_ALL}")
        print(f"   Profil: {trans_stats['gpu_profile']}")
        print(f"   VRAM: {trans_stats['vram_usage_gb']:.2f} GB")
        print(f"   Transcriptions: {trans_stats['total_transcriptions']}")
        print(f"   Temps moyen: {trans_stats['average_inference_time']:.2f}s")
        print(f"   Ajustements auto: {trans_stats['gpu_adjustments']}")
        
        # Dual-stream health
        if self.dual_stream:
            health = self.dual_stream.get_queue_health()
            health_icon = "✅" if health["is_healthy"] else "⚠️"
            print(f"\n{Fore.WHITE}🔄 DUAL-STREAM:{Style.RESET_ALL} {health_icon}")
            print(f"   Queue VOUS: {health['left_queue_size']}")
            print(f"   Queue CLIENT: {health['right_queue_size']}")
        
        print(f"\n{Fore.CYAN}" + "═"*70 + Style.RESET_ALL)
    
    async def run(self):
        """Lance le système et maintient l'exécution."""
        try:
            await self.start()
            
            # Attendre le signal d'arrêt
            await self._shutdown_event.wait()
            
        except KeyboardInterrupt:
            pass
        finally:
            await self.stop()
    
    def _signal_handler(self, signum, frame):
        """Gestionnaire de signaux (Ctrl+C)."""
        if self.loop:
            self.loop.call_soon_threadsafe(self._shutdown_event.set)


async def main():
    """Point d'entrée principal."""
    app = TheCloserProV25()
    
    # Configurer les signaux
    loop = asyncio.get_event_loop()
    app.loop = loop
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, app._signal_handler)
    
    # Lancer l'application
    await app.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Fore.RED}[STOP]{Style.RESET_ALL} Arrêt forcé.")
    except Exception as e:
        print(f"\n{Fore.RED}[ERROR]{Style.RESET_ALL} Erreur fatale: {e}")
        logging.exception("Fatal error")
        sys.exit(1)
