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

from config.manager import get_config
from core.audio_streamer import AudioStreamer, AudioChunk
from core.transcriber_new import get_transcriber, TranscriptionSegment
from core.processor import get_processor, ProcessedTranscription


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
        
        self.logger.info("="*70)
        self.logger.info("THE CLOSER PRO - Version 1.0.0 (Genesis)")
        self.logger.info("="*70)
    
    def _setup_logging(self) -> logging.Logger:
        """
        Configure le système de logging.
        
        Returns:
            Logger configuré
        """
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        log_level = getattr(logging, self.config.system.log_level.upper(), logging.INFO)
        
        logging.basicConfig(
            level=log_level,
            format=log_format,
            handlers=[
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        return logging.getLogger(__name__)
    
    def _signal_handler(self, signum, frame):
        """
        Gestionnaire de signaux pour arrêt propre (Ctrl+C).
        
        Args:
            signum: Numéro du signal
            frame: Frame d'exécution
        """
        self.logger.info("\n" + "="*70)
        self.logger.info("SIGNAL D'ARRÊT REÇU (Ctrl+C)")
        self.logger.info("="*70)
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
        Affiche et sauvegarde une transcription.
        
        Args:
            text: Texte transcrit à afficher
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_line = f"[{timestamp}] {text}"
        
        if self.config.system.output_format in ["console", "both"]:
            print(f"\n{formatted_line}", flush=True)
        
        if self.config.system.output_format in ["file", "both"] and self._output_file:
            try:
                with open(self._output_file, 'a', encoding='utf-8') as f:
                    f.write(formatted_line + "\n")
            except Exception as e:
                self.logger.error(f"Erreur d'écriture dans le fichier: {e}")
    
    def start(self):
        """
        Démarre le système de transcription.
        
        Raises:
            RuntimeError: Si le système est déjà démarré
        """
        if self._is_running:
            raise RuntimeError("THE CLOSER PRO est déjà en cours d'exécution")
        
        try:
            self.logger.info("Validation de la configuration...")
            self.config.validate()
            
            self.logger.info("Configuration du fichier de sortie...")
            self._setup_output_file()
            
            self.logger.info("Démarrage du transcriber...")
            self.transcriber.start()
            
            self.logger.info("Démarrage de l'audio streamer...")
            self.audio_streamer = AudioStreamer(callback=self._audio_callback)
            self.audio_streamer.start()
            
            self._is_running = True
            self._session_start_time = datetime.now()
            
            self.logger.info("="*70)
            self.logger.info("SYSTÈME OPÉRATIONNEL - PRÊT POUR LE CLOSING")
            self.logger.info("="*70)
            self.logger.info(f"Modèle: {self.config.transcription.model_name}")
            self.logger.info(f"Device: {self.config.transcription.device} ({self.config.transcription.compute_type})")
            self.logger.info(f"Audio: Device ID {self.config.audio.device_id} @ {self.config.audio.sample_rate}Hz")
            self.logger.info(f"Langue: {self.config.transcription.language.upper()}")
            self.logger.info("="*70)
            self.logger.info("Parlez maintenant... (Ctrl+C pour arrêter)")
            self.logger.info("="*70 + "\n")
            
        except Exception as e:
            self.logger.error(f"Échec du démarrage: {e}", exc_info=True)
            self.stop()
            raise
    
    def stop(self):
        """Arrête proprement tous les composants."""
        if not self._is_running:
            return
        
        self.logger.info("\n" + "="*70)
        self.logger.info("ARRÊT DU SYSTÈME EN COURS...")
        self.logger.info("="*70)
        
        self._is_running = False
        
        if self._audio_buffer:
            self.logger.info("Traitement du buffer audio restant...")
            self._process_buffer()
        
        if self.audio_streamer:
            self.logger.info("Arrêt de l'audio streamer...")
            self.audio_streamer.stop()
        
        self.logger.info("Arrêt du transcriber...")
        self.transcriber.stop()
        
        self._print_session_stats()
        
        self.logger.info("="*70)
        self.logger.info("SYSTÈME ARRÊTÉ - SESSION TERMINÉE")
        self.logger.info("="*70)
    
    def _print_session_stats(self):
        """Affiche les statistiques de la session."""
        if self._session_start_time:
            duration = datetime.now() - self._session_start_time
            duration_str = str(duration).split('.')[0]
            
            self.logger.info("\n" + "="*70)
            self.logger.info("STATISTIQUES DE SESSION")
            self.logger.info("="*70)
            self.logger.info(f"Durée: {duration_str}")
            self.logger.info(f"Segments transcrits: {self._total_segments_processed}")
            self.logger.info(f"Segments valides: {self._total_valid_segments}")
            
            if self._total_segments_processed > 0:
                valid_rate = (self._total_valid_segments / self._total_segments_processed) * 100
                self.logger.info(f"Taux de validité: {valid_rate:.1f}%")
            
            if self.audio_streamer:
                audio_stats = self.audio_streamer.get_stats()
                self.logger.info(f"Chunks audio: {audio_stats['total_chunks']}")
                self.logger.info(f"Perte audio: {audio_stats['loss_rate_percent']:.2f}%")
            
            transcriber_stats = self.transcriber.get_stats()
            self.logger.info(f"Temps d'inférence moyen: {transcriber_stats['avg_inference_time']:.2f}s")
            
            if 'vram_allocated_gb' in transcriber_stats:
                self.logger.info(f"VRAM utilisée: {transcriber_stats['vram_allocated_gb']:.2f} GB")
            
            if self._output_file:
                self.logger.info(f"Transcription sauvegardée: {self._output_file}")
            
            self.logger.info("="*70)
    
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
