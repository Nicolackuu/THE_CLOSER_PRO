"""
Configuration Manager for THE CLOSER PRO.
Centralizes all system parameters, audio settings, and AI model configurations.
"""

from dataclasses import dataclass
from typing import Optional
import os


@dataclass
class AudioConfig:
    """
    Configuration pour la capture audio.
    
    Attributes:
        device_id: ID du périphérique audio (33 pour VoiceMeeter Virtual B1)
        sample_rate: Taux d'échantillonnage en Hz (16000 pour Whisper)
        channels: Nombre de canaux audio (1 = mono)
        chunk_duration: Durée d'un chunk audio en secondes
        silence_threshold: Seuil de détection de silence (amplitude RMS)
        silence_duration: Durée de silence avant flush en secondes
    """
    device_id: int = 33
    sample_rate: int = 48000
    channels: int = 2
    chunk_duration: float = 0.5
    silence_threshold: float = 0.01
    silence_duration: float = 2.0


@dataclass
class TranscriptionConfig:
    """
    Configuration pour le moteur de transcription Faster-Whisper.
    
    Attributes:
        model_name: Nom du modèle Whisper à utiliser
        device: Device de calcul ('cuda' ou 'cpu')
        compute_type: Type de précision ('float16', 'int8', 'float32')
        language: Langue forcée pour la transcription
        task: Type de tâche ('transcribe' ou 'translate')
        beam_size: Taille du beam search (5 = bon compromis vitesse/qualité)
        vad_filter: Activer le filtre Voice Activity Detection
        initial_prompt: Prompt de conditionnement pour le contexte métier
    """
    model_name: str = "distil-large-v3"
    device: str = "cuda"
    compute_type: str = "float16"
    language: str = "fr"
    task: str = "transcribe"
    beam_size: int = 5
    vad_filter: bool = False
    initial_prompt: str = (
        "Session de Closing High-Ticket. Analyse des besoins et traitement d'objections. "
        "Terminologie : Pipeline, Deal, Setter, Qualif, Go-High-Level, Prospect, "
        "Objection, Close, Upsell, Downsell, Framework, ROI, Investissement."
    )


@dataclass
class ProcessingConfig:
    """
    Configuration pour le nettoyage et le traitement des transcriptions.
    
    Attributes:
        hallucination_patterns: Liste des patterns à éliminer (hallucinations Whisper)
        fuzzy_threshold: Seuil de similarité pour le fuzzy matching (0-100)
        min_word_length: Longueur minimale d'un mot valide
        enable_cleanup: Activer le nettoyage automatique
    """
    hallucination_patterns: list = None
    fuzzy_threshold: int = 85
    min_word_length: int = 2
    enable_cleanup: bool = True
    
    def __post_init__(self):
        if self.hallucination_patterns is None:
            self.hallucination_patterns = [
                "Amara.org",
                "Sous-titres réalisés para la communauté d'Amara.org",
                "Abonnez-vous",
                "Merci d'avoir regardé",
                "Merci de vous abonner",
                "N'oubliez pas de liker",
                "Mettez un pouce bleu",
                "Sous-titrage",
                "www.",
                "http"
            ]


@dataclass
class SystemConfig:
    """
    Configuration système globale.
    
    Attributes:
        enable_gpu_cache_cleanup: Activer le nettoyage automatique du cache GPU
        cache_cleanup_interval: Intervalle de nettoyage en secondes
        max_queue_size: Taille maximale de la queue audio
        log_level: Niveau de logging ('DEBUG', 'INFO', 'WARNING', 'ERROR')
        output_format: Format de sortie ('console', 'file', 'both')
        output_file: Fichier de sortie pour les transcriptions
    """
    enable_gpu_cache_cleanup: bool = True
    cache_cleanup_interval: float = 5.0
    max_queue_size: int = 100
    log_level: str = "INFO"
    output_format: str = "console"
    output_file: Optional[str] = "transcriptions.txt"


class ConfigManager:
    """
    Gestionnaire centralisé de configuration.
    Singleton pattern pour garantir une instance unique dans toute l'application.
    """
    
    _instance = None
    
    def __new__(cls):
        """
        Implémentation du pattern Singleton.
        Garantit qu'une seule instance de ConfigManager existe.
        """
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """
        Initialise le gestionnaire de configuration avec les valeurs par défaut.
        Ne s'exécute qu'une seule fois grâce au flag _initialized.
        """
        if self._initialized:
            return
        
        self.audio = AudioConfig()
        self.transcription = TranscriptionConfig()
        self.processing = ProcessingConfig()
        self.system = SystemConfig()
        
        self._initialized = True
    
    def validate(self) -> bool:
        """
        Valide la cohérence de la configuration.
        
        Returns:
            True si la configuration est valide, False sinon.
        """
        validations = [
            (self.audio.sample_rate > 0, "Sample rate must be positive"),
            (self.audio.device_id >= 0, "Device ID must be non-negative"),
            (self.transcription.beam_size > 0, "Beam size must be positive"),
            (0 <= self.processing.fuzzy_threshold <= 100, "Fuzzy threshold must be 0-100"),
            (self.system.max_queue_size > 0, "Queue size must be positive"),
        ]
        
        for is_valid, error_msg in validations:
            if not is_valid:
                raise ValueError(f"Configuration validation failed: {error_msg}")
        
        return True
    
    def get_model_path(self) -> str:
        """
        Retourne le chemin du modèle Whisper.
        Utilise le cache HuggingFace par défaut.
        
        Returns:
            Chemin vers le modèle ou nom du modèle pour téléchargement auto.
        """
        return self.transcription.model_name
    
    def __repr__(self) -> str:
        """Représentation lisible de la configuration."""
        return (
            f"ConfigManager(\n"
            f"  Audio: {self.audio}\n"
            f"  Transcription: {self.transcription}\n"
            f"  Processing: {self.processing}\n"
            f"  System: {self.system}\n"
            f")"
        )


def get_config() -> ConfigManager:
    """
    Factory function pour obtenir l'instance unique de ConfigManager.
    
    Returns:
        Instance singleton de ConfigManager.
    
    Usage:
        >>> config = get_config()
        >>> print(config.audio.device_id)
        33
    """
    return ConfigManager()
