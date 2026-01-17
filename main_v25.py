"""
THE CLOSER PRO V25 - Elite Main Orchestrator
Architecture asynchrone professionnelle avec dual-stream, analytics et self-healing.
Conçu pour les sessions de closing haute performance.

Author: THE CLOSER PRO Team
Version: 2.5.0 (Elite)
"""

import asyncio
import signal
import logging
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

from colorama import init, Fore, Style

from config.manager import get_config
from core.audio_streamer import AudioStreamer, AudioChunk
from core.dual_stream_manager import DualStreamManager, AudioStream
from core.transcriber_v25 import get_elite_transcriber, TranscriptionResult
from core.analytics_engine import AnalyticsEngine
from core.processor import get_processor

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
        
        # Composants Elite
        self.transcriber = get_elite_transcriber()
        self.analytics = AnalyticsEngine(snapshot_interval=30)
        self.processor = get_processor()
        
        # Dual-stream manager
        self.dual_stream: Optional[DualStreamManager] = None
        
        # Audio streamer
        self.audio_streamer: Optional[AudioStreamer] = None
        
        # État
        self._is_running = False
        self._output_file: Optional[Path] = None
        self._session_start: Optional[datetime] = None
        
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
                    self.analytics.record_speech(
                        speaker="CLIENT",
                        duration=result.duration,
                        timestamp=result.timestamp
                    )
                    
                    self._display_transcription(result, cleaned)
                    
        except Exception as e:
            self.logger.error(f"Error processing right channel: {e}", exc_info=True)
    
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
            print(f"{Fore.CYAN}║{Fore.WHITE}                 THE CLOSER PRO - V25 ELITE                        {Fore.CYAN}║")
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
            
            print(f"{Fore.GREEN}[READY]{Style.RESET_ALL} Système V25 opérationnel - Parlez maintenant !")
            print(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Architecture: Dual-Stream Zero-Overlap")
            print(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Analytics: Talk-to-Listen Ratio activé")
            print(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} GPU: Self-Healing activé")
            print(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Appuyez sur Ctrl+C pour arrêter\n")
            print(f"{Fore.CYAN}" + "─"*70 + Style.RESET_ALL)
            print()
            
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
        
        # Arrêter le dual-stream
        if self.dual_stream:
            await self.dual_stream.stop()
        
        # Arrêter le transcripteur
        await self.transcriber.shutdown()
        
        # Afficher les statistiques finales
        self._display_final_stats()
        
        print(f"\n{Fore.GREEN}[DONE]{Style.RESET_ALL} Session terminée.")
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
