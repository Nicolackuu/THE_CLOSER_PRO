"""
THE CLOSER PRO V25 - Context Memory Engine
Buffer de contexte intelligent pour améliorer la cohérence des transcriptions.
Maintient 30 secondes de contexte pour noms propres, prix, marques.

Author: THE CLOSER PRO Team
Version: 2.5.0 (Elite)
"""

import numpy as np
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional
import logging


@dataclass
class ContextSegment:
    """Segment de contexte avec métadonnées."""
    text: str
    timestamp: datetime
    speaker: str  # "VOUS" ou "CLIENT"
    audio_data: Optional[np.ndarray] = None
    duration: float = 0.0


class ContextMemory:
    """
    Moteur de mémoire contextuelle pour Whisper.
    Maintient un buffer glissant de 30 secondes pour améliorer la cohérence.
    """
    
    def __init__(
        self,
        context_window_seconds: float = 30.0,
        max_segments: int = 50,
        sample_rate: int = 16000
    ):
        """
        Initialise le moteur de contexte.
        
        Args:
            context_window_seconds: Durée de la fenêtre de contexte
            max_segments: Nombre maximum de segments en mémoire
            sample_rate: Fréquence d'échantillonnage pour l'audio
        """
        self.context_window = timedelta(seconds=context_window_seconds)
        self.max_segments = max_segments
        self.sample_rate = sample_rate
        
        # Buffer circulaire pour les segments texte
        self.text_buffer: deque[ContextSegment] = deque(maxlen=max_segments)
        
        # Buffer audio pour reconstitution
        self.audio_buffer: deque[np.ndarray] = deque(maxlen=10)
        
        self.logger = logging.getLogger(__name__)
        
        # Dictionnaire d'entités détectées (noms, prix, marques)
        self.entities = {
            "names": set(),
            "prices": set(),
            "brands": set(),
            "numbers": set()
        }
    
    def add_segment(
        self,
        text: str,
        speaker: str,
        timestamp: Optional[datetime] = None,
        audio_data: Optional[np.ndarray] = None,
        duration: float = 0.0
    ):
        """
        Ajoute un segment au contexte.
        
        Args:
            text: Texte transcrit
            speaker: Locuteur ("VOUS" ou "CLIENT")
            timestamp: Timestamp du segment
            audio_data: Données audio optionnelles
            duration: Durée du segment
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        segment = ContextSegment(
            text=text,
            timestamp=timestamp,
            speaker=speaker,
            audio_data=audio_data,
            duration=duration
        )
        
        self.text_buffer.append(segment)
        
        # Extraire les entités du texte
        self._extract_entities(text)
        
        # Nettoyer les segments trop anciens
        self._cleanup_old_segments()
    
    def _cleanup_old_segments(self):
        """Supprime les segments hors de la fenêtre temporelle."""
        if not self.text_buffer:
            return
        
        cutoff_time = datetime.now() - self.context_window
        
        # Retirer les segments trop anciens
        while self.text_buffer and self.text_buffer[0].timestamp < cutoff_time:
            self.text_buffer.popleft()
    
    def _extract_entities(self, text: str):
        """
        Extrait les entités importantes du texte (noms, prix, marques).
        
        Args:
            text: Texte à analyser
        """
        words = text.split()
        
        for i, word in enumerate(words):
            # Détection de prix (€, $, euros, dollars)
            if any(currency in word.lower() for currency in ['€', '$', 'euro', 'dollar']):
                # Chercher le nombre associé
                for j in range(max(0, i-2), min(len(words), i+3)):
                    if words[j].replace(',', '').replace('.', '').isdigit():
                        self.entities["prices"].add(f"{words[j]} {word}")
            
            # Détection de nombres importants
            clean_word = word.replace(',', '').replace('.', '')
            if clean_word.isdigit() and len(clean_word) >= 3:
                self.entities["numbers"].add(word)
            
            # Détection de mots capitalisés (noms propres potentiels)
            if word and word[0].isupper() and len(word) > 2:
                # Éviter les débuts de phrase
                if i > 0 and not words[i-1].endswith('.'):
                    self.entities["names"].add(word)
    
    def get_context_prompt(self, speaker: Optional[str] = None) -> str:
        """
        Génère un prompt de contexte pour Whisper.
        
        Args:
            speaker: Filtrer par locuteur (optionnel)
        
        Returns:
            Prompt de contexte enrichi
        """
        self._cleanup_old_segments()
        
        if not self.text_buffer:
            return "Transcription en français uniquement. Ne pas traduire."
        
        # Récupérer les derniers segments
        recent_segments = list(self.text_buffer)[-5:]
        
        if speaker:
            recent_segments = [s for s in recent_segments if s.speaker == speaker]
        
        # Construire le contexte
        context_parts = []
        
        # Ajouter les entités détectées
        if self.entities["names"]:
            names = ", ".join(list(self.entities["names"])[-5:])
            context_parts.append(f"Noms: {names}")
        
        if self.entities["prices"]:
            prices = ", ".join(list(self.entities["prices"])[-3:])
            context_parts.append(f"Prix: {prices}")
        
        # Ajouter les dernières phrases
        if recent_segments:
            last_texts = [s.text for s in recent_segments[-3:]]
            context_parts.append(" ".join(last_texts))
        
        base_prompt = "Transcription en français uniquement. Ne pas traduire. Conversation de vente."
        
        if context_parts:
            return f"{base_prompt} Contexte: {' | '.join(context_parts)}"
        
        return base_prompt
    
    def get_audio_context(self, max_duration: float = 30.0) -> Optional[np.ndarray]:
        """
        Récupère le contexte audio pour améliorer la transcription.
        
        Args:
            max_duration: Durée maximale du contexte audio (secondes)
        
        Returns:
            Array numpy avec l'audio de contexte, ou None
        """
        if not self.text_buffer:
            return None
        
        # Collecter les segments audio récents
        audio_segments = []
        total_duration = 0.0
        
        for segment in reversed(self.text_buffer):
            if segment.audio_data is not None and total_duration < max_duration:
                audio_segments.insert(0, segment.audio_data)
                total_duration += segment.duration
        
        if not audio_segments:
            return None
        
        # Concaténer les segments
        return np.concatenate(audio_segments)
    
    def get_speaker_stats(self) -> dict:
        """
        Calcule les statistiques par locuteur.
        
        Returns:
            Dict avec les stats par speaker
        """
        self._cleanup_old_segments()
        
        vous_count = sum(1 for s in self.text_buffer if s.speaker == "VOUS")
        client_count = sum(1 for s in self.text_buffer if s.speaker == "CLIENT")
        
        vous_duration = sum(s.duration for s in self.text_buffer if s.speaker == "VOUS")
        client_duration = sum(s.duration for s in self.text_buffer if s.speaker == "CLIENT")
        
        return {
            "vous_segments": vous_count,
            "client_segments": client_count,
            "vous_duration": vous_duration,
            "client_duration": client_duration,
            "total_segments": len(self.text_buffer)
        }
    
    def clear(self):
        """Vide complètement le contexte."""
        self.text_buffer.clear()
        self.audio_buffer.clear()
        self.entities = {
            "names": set(),
            "prices": set(),
            "brands": set(),
            "numbers": set()
        }
        self.logger.info("Context memory cleared")
    
    def get_entities_summary(self) -> dict:
        """
        Retourne un résumé des entités détectées.
        
        Returns:
            Dict avec les entités par catégorie
        """
        return {
            "names": list(self.entities["names"]),
            "prices": list(self.entities["prices"]),
            "brands": list(self.entities["brands"]),
            "numbers": list(self.entities["numbers"])
        }
