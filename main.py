"""
THE CLOSER PRO - Main Orchestrator
Système de transcription temps réel pour sessions de Closing High-Ticket.

Architecture:
    - Audio Streamer: Capture continue sans perte de paquets
    - Transcriber: Inférence Faster-Whisper en thread séparé
    - Processor: Nettoyage anti-hallucination avec fuzzy matching
    - Signal Handler: Arrêt propre sur Ctrl+C

Author: THE CLOSER PRO Team
Version: 1.0.0 (Genesis)
"""

import sys
import signal
import logging
import time
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Optional
import os

from colorama import init, Fore, Style

from config.manager import get_config
from core.audio_streamer import AudioStreamer, AudioChunk
from core.transcriber_new import get_transcriber, TranscriptionSegment
from core.processor import get_processor, ProcessedTranscription

init(autoreset=True)


class TheCloserPro:
    """
    Orchestrateur principal de THE CLOSER PRO.
    Coordonne la capture audio, la transcription et le traitement.
    """
    
    def __init__(self):
        """Initialise l'orchestrateur et tous les composants."""
        self.config = get_config()
        self.logger = self._setup_logging()
        
        self.audio_streamer: Optional[AudioStreamer] = None
        self.transcriber = get_transcriber()
        self.processor = get_processor()
        
        self._audio_buffer = []
        self._buffer_duration = 0.0
        self._target_buffer_duration = 3.0
        
        self._is_running = False
        self._output_file: Optional[Path] = None
        
        self._session_start_time: Optional[datetime] = None
        self._total_segments_processed = 0
        self._total_valid_segments = 0
        
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _setup_logging(self) -> logging.Logger:
        """
        Configure le système de logging.
        Redirige les logs techniques vers un fichier, garde seulement l'UI propre.
        
        Returns:
            Logger configuré
        """
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        log_level = getattr(logging, self.config.system.log_level.upper(), logging.INFO)
        
        log_file = Path('system.log')
        
        logging.basicConfig(
            level=log_level,
            format=log_format,
            handlers=[
                logging.FileHandler(log_file, mode='w', encoding='utf-8')
            ]
        )
        
        logging.getLogger('faster_whisper').setLevel(logging.WARNING)
        logging.getLogger('core.audio_streamer').setLevel(logging.WARNING)
        logging.getLogger('core.transcriber_new').setLevel(logging.WARNING)
        logging.getLogger('core.processor').setLevel(logging.WARNING)
        
        return logging.getLogger(__name__)
    
    def _signal_handler(self, signum, frame):
        """
        Gestionnaire de signaux pour arrêt propre (Ctrl+C).
        
        Args:
            signum: Numéro du signal
            frame: Frame d'exécution
        """
        print(f"\n\n{Fore.RED}[STOP]{Style.RESET_ALL} Arrêt demandé...")
        self.stop()
        sys.exit(0)
    
    def _setup_output_file(self):
        """Configure le fichier de sortie pour les transcriptions."""
        if self.config.system.output_format in ["file", "both"]:
            if self.config.system.output_file:
                self._output_file = Path(self.config.system.output_file)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_dir = self._output_file.parent
                output_name = f"{self._output_file.stem}_{timestamp}{self._output_file.suffix}"
                self._output_file = output_dir / output_name
                
                self._output_file.parent.mkdir(parents=True, exist_ok=True)
                
                with open(self._output_file, 'w', encoding='utf-8') as f:
                    f.write(f"=== THE CLOSER PRO - Session de Closing ===\n")
                    f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Configuration: {self.config.transcription.model_name} | {self.config.transcription.compute_type}\n")
                    f.write(f"="*70 + "\n\n")
                
                self.logger.info(f"Fichier de sortie: {self._output_file}")
    
    def _audio_callback(self, chunk: AudioChunk):
        """
        Callback appelé pour chaque chunk audio capturé.
        Accumule l'audio et déclenche la transcription quand le buffer est plein.
        
        Args:
            chunk: Chunk audio capturé
        """
        if not self._is_running:
            return
        
        self._audio_buffer.append(chunk.data.flatten())
        self._buffer_duration += len(chunk.data) / chunk.sample_rate
        
        if self._buffer_duration >= self._target_buffer_duration:
            self._process_buffer()
    
    def _process_buffer(self):
        """
        Traite le buffer audio accumulé.
        Envoie l'audio au transcriber et traite les résultats.
        """
        if not self._audio_buffer:
            return
        
        audio_data = np.concatenate(self._audio_buffer)
        
        self._audio_buffer = []
        self._buffer_duration = 0.0
        
        try:
            result_queue = self.transcriber.transcribe_async(audio_data)
            
            segments = result_queue.get(timeout=30.0)
            
            if segments:
                self._handle_transcription_results(segments)
            
        except Exception as e:
            self.logger.error(f"Erreur lors du traitement du buffer: {e}", exc_info=True)
    
    def _handle_transcription_results(self, segments: list[TranscriptionSegment]):
        """
        Traite les résultats de transcription.
        
        Args:
            segments: Liste de segments transcrits
        """
        processed_results = self.processor.process_segments(segments)
        
        valid_texts = self.processor.get_valid_texts(processed_results)
        
        self._total_segments_processed += len(segments)
        self._total_valid_segments += len(valid_texts)
        
        for text in valid_texts:
            self._output_transcription(text)
    
    def _output_transcription(self, text: str):
        """
        Affiche et sauvegarde une transcription avec interface chat colorée.
        Format: [HH:MM:SS] [SPEAKER] -> "texte"
        
        Args:
            text: Texte transcrit (format: [SPEAKER]|COLOR|texte)
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if "|" in text:
            parts = text.split("|")
            if len(parts) == 3:
                speaker = parts[0]
                color = parts[1]
                message = parts[2]
                
                color_code = Fore.GREEN if color == "GREEN" else Fore.CYAN
                
                formatted_line = f"[{timestamp}] {color_code}{speaker}{Style.RESET_ALL} -> \"{message}\""
                
                print(formatted_line, flush=True)
                
                if self._output_file:
                    try:
                        plain_line = f"[{timestamp}] {speaker} -> \"{message}\""
                        with open(self._output_file, 'a', encoding='utf-8') as f:
                            f.write(plain_line + "\n")
                    except Exception as e:
                        self.logger.error(f"Erreur d'écriture dans le fichier: {e}")
            else:
                print(f"[{timestamp}] {text}", flush=True)
        else:
            print(f"[{timestamp}] {text}", flush=True)
    
    def start(self):
        """
        Démarre le système de transcription.
        
        Raises:
            RuntimeError: Si le système est déjà démarré
        """
        if self._is_running:
            raise RuntimeError("THE CLOSER PRO est déjà en cours d'exécution")
        
        try:
            os.system('cls' if os.name == 'nt' else 'clear')
            
            print(f"{Fore.CYAN}" + "="*70)
            print(f"{Fore.CYAN}╔═══════════════════════════════════════════════════════════════════╗")
            print(f"{Fore.CYAN}║{Fore.WHITE}                    THE CLOSER PRO - v1.0.0                        {Fore.CYAN}║")
            print(f"{Fore.CYAN}║{Fore.WHITE}           Transcription Temps Réel - Interface Chat             {Fore.CYAN}║")
            print(f"{Fore.CYAN}╚═══════════════════════════════════════════════════════════════════╝")
            print(f"{Fore.CYAN}" + "="*70 + Style.RESET_ALL)
            print()
            
            self.config.validate()
            self._setup_output_file()
            
            print(f"{Fore.YELLOW}[INIT]{Style.RESET_ALL} Chargement du modèle Whisper...")
            self.transcriber.start()
            
            print(f"{Fore.YELLOW}[INIT]{Style.RESET_ALL} Démarrage de la capture audio...")
            self.audio_streamer = AudioStreamer(callback=self._audio_callback)
            self.audio_streamer.start()
            
            self._is_running = True
            self._session_start_time = datetime.now()
            
            print(f"{Fore.GREEN}[READY]{Style.RESET_ALL} Système opérationnel - Parlez maintenant !")
            print(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Appuyez sur Ctrl+C pour arrêter\n")
            print(f"{Fore.CYAN}" + "─"*70 + Style.RESET_ALL)
            print()
            
        except Exception as e:
            self.logger.error(f"Échec du démarrage: {e}", exc_info=True)
            self.stop()
            raise
    
    def stop(self):
        """Arrête proprement tous les composants."""
        if not self._is_running:
            return
        
        self._is_running = False
        
        if self._audio_buffer:
            self._process_buffer()
        
        if self.audio_streamer:
            self.audio_streamer.stop()
        
        self.transcriber.stop()
        
        self._print_session_stats()
        
        print(f"\n{Fore.GREEN}[DONE]{Style.RESET_ALL} Session terminée.")
        if self._output_file:
            print(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Transcription sauvegardée: {self._output_file}\n")
    
    def _print_session_stats(self):
        """Affiche les statistiques de la session."""
        if self._session_start_time:
            duration = datetime.now() - self._session_start_time
            duration_str = str(duration).split('.')[0]
            
            print(f"\n{Fore.CYAN}" + "─"*70 + Style.RESET_ALL)
            print(f"{Fore.CYAN}STATISTIQUES DE SESSION{Style.RESET_ALL}")
            print(f"{Fore.CYAN}" + "─"*70 + Style.RESET_ALL)
            print(f"Durée: {duration_str}")
            print(f"Segments transcrits: {self._total_segments_processed}")
            print(f"Segments valides: {self._total_valid_segments}")
            
            if self._total_segments_processed > 0:
                valid_rate = (self._total_valid_segments / self._total_segments_processed) * 100
                print(f"Taux de validité: {valid_rate:.1f}%")
            
            if self.audio_streamer:
                audio_stats = self.audio_streamer.get_stats()
                print(f"Perte audio: {audio_stats['loss_rate_percent']:.2f}%")
            
            print(f"{Fore.CYAN}" + "─"*70 + Style.RESET_ALL)
    
    def run(self):
        """
        Lance le système et maintient l'exécution.
        Boucle principale qui attend l'arrêt.
        """
        try:
            self.start()
            
            while self._is_running:
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            self.logger.info("\nInterruption clavier détectée")
        except Exception as e:
            self.logger.error(f"Erreur fatale: {e}", exc_info=True)
        finally:
            self.stop()


def main():
    """
    Point d'entrée principal de l'application.
    """
    print("""
    ╔═══════════════════════════════════════════════════════════════════╗
    ║                                                                   ║
    ║                    THE CLOSER PRO - v1.0.0                        ║
    ║                                                                   ║
    ║           Transcription Temps Réel pour Closing High-Ticket      ║
    ║                                                                   ║
    ║   Architecture: Asynchrone | Modèle: distil-large-v3 | GPU      ║
    ║                                                                   ║
    ╚═══════════════════════════════════════════════════════════════════╝
    """)
    
    try:
        app = TheCloserPro()
        app.run()
    except Exception as e:
        logging.error(f"Erreur critique: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
