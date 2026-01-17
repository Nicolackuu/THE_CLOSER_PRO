"""
Processor Module - THE CLOSER PRO.
Nettoyage et post-traitement des transcriptions.
Utilise fuzzy matching pour éliminer les hallucinations de Whisper.
"""

import re
import logging
from typing import List, Optional
from dataclasses import dataclass
from rapidfuzz import fuzz

from config.manager import get_config
from core.transcriber_new import TranscriptionSegment


@dataclass
class ProcessedTranscription:
    """
    Résultat du traitement d'une transcription.
    
    Attributes:
        original_text: Texte original avant nettoyage
        cleaned_text: Texte après nettoyage
        is_valid: True si le texte est valide (pas une hallucination)
        removed_patterns: Liste des patterns détectés et supprimés
        confidence: Score de confiance du segment
    """
    original_text: str
    cleaned_text: str
    is_valid: bool
    removed_patterns: List[str]
    confidence: float


class TranscriptionProcessor:
    """
    Processeur de transcriptions avec détection d'hallucinations.
    
    Fonctionnalités:
        - Détection fuzzy des hallucinations courantes de Whisper
        - Nettoyage des espaces et ponctuation
        - Filtrage des segments trop courts ou invalides
        - Normalisation du texte
    """
    
    def __init__(self):
        """Initialise le processeur avec la configuration."""
        self.config = get_config()
        self.logger = logging.getLogger(__name__)
        
        self._hallucination_cache = {}
        
        self.logger.info(
            f"TranscriptionProcessor initialized\n"
            f"  Fuzzy threshold: {self.config.processing.fuzzy_threshold}\n"
            f"  Min word length: {self.config.processing.min_word_length}\n"
            f"  Hallucination patterns: {len(self.config.processing.hallucination_patterns)}"
        )
    
    def _is_hallucination_fuzzy(self, text: str) -> tuple[bool, Optional[str]]:
        """
        Détecte si le texte est une hallucination en utilisant fuzzy matching.
        
        Args:
            text: Texte à analyser
        
        Returns:
            Tuple (is_hallucination, matched_pattern)
        """
        text_lower = text.lower().strip()
        
        if text_lower in self._hallucination_cache:
            return self._hallucination_cache[text_lower]
        
        for pattern in self.config.processing.hallucination_patterns:
            pattern_lower = pattern.lower()
            
            if pattern_lower in text_lower:
                result = (True, pattern)
                self._hallucination_cache[text_lower] = result
                return result
            
            similarity = fuzz.partial_ratio(text_lower, pattern_lower)
            
            if similarity >= self.config.processing.fuzzy_threshold:
                result = (True, pattern)
                self._hallucination_cache[text_lower] = result
                self.logger.debug(
                    f"Fuzzy match detected: '{text}' ~= '{pattern}' (score: {similarity})"
                )
                return result
        
        result = (False, None)
        self._hallucination_cache[text_lower] = result
        return result
    
    def _clean_text(self, text: str) -> str:
        """
        Nettoie le texte (espaces multiples, ponctuation excessive, etc.).
        
        Args:
            text: Texte à nettoyer
        
        Returns:
            Texte nettoyé
        """
        text = re.sub(r'\s+', ' ', text)
        
        text = re.sub(r'\.{3,}', '...', text)
        text = re.sub(r'!{2,}', '!', text)
        text = re.sub(r'\?{2,}', '?', text)
        
        text = text.strip()
        
        return text
    
    def _is_valid_text(self, text: str) -> bool:
        """
        Vérifie si le texte est valide (pas vide, longueur suffisante, etc.).
        
        Args:
            text: Texte à valider
        
        Returns:
            True si valide, False sinon
        """
        if not text or len(text.strip()) == 0:
            return False
        
        words = text.split()
        if len(words) == 0:
            return False
        
        valid_words = [w for w in words if len(w) >= self.config.processing.min_word_length]
        if len(valid_words) == 0:
            return False
        
        if re.match(r'^[\W_]+$', text):
            return False
        
        return True
    
    def process_segment(self, segment: TranscriptionSegment) -> ProcessedTranscription:
        """
        Traite un segment de transcription.
        
        Args:
            segment: Segment à traiter
        
        Returns:
            Résultat du traitement
        """
        original_text = segment.text
        removed_patterns = []
        
        is_hallucination, matched_pattern = self._is_hallucination_fuzzy(original_text)
        
        if is_hallucination:
            removed_patterns.append(matched_pattern)
            self.logger.debug(f"Hallucination detected and removed: '{original_text}'")
            return ProcessedTranscription(
                original_text=original_text,
                cleaned_text="",
                is_valid=False,
                removed_patterns=removed_patterns,
                confidence=segment.confidence
            )
        
        cleaned_text = self._clean_text(original_text)
        
        is_valid = self._is_valid_text(cleaned_text)
        
        if not is_valid:
            self.logger.debug(f"Invalid text filtered: '{original_text}'")
        
        return ProcessedTranscription(
            original_text=original_text,
            cleaned_text=cleaned_text,
            is_valid=is_valid,
            removed_patterns=removed_patterns,
            confidence=segment.confidence
        )
    
    def process_segments(self, segments: List[TranscriptionSegment]) -> List[ProcessedTranscription]:
        """
        Traite une liste de segments.
        
        Args:
            segments: Liste de segments à traiter
        
        Returns:
            Liste des résultats de traitement
        """
        if not self.config.processing.enable_cleanup:
            return [
                ProcessedTranscription(
                    original_text=seg.text,
                    cleaned_text=seg.text,
                    is_valid=True,
                    removed_patterns=[],
                    confidence=seg.confidence
                )
                for seg in segments
            ]
        
        results = []
        for segment in segments:
            result = self.process_segment(segment)
            results.append(result)
        
        valid_count = sum(1 for r in results if r.is_valid)
        hallucination_count = sum(1 for r in results if r.removed_patterns)
        
        self.logger.debug(
            f"Processed {len(segments)} segments: "
            f"{valid_count} valid, {hallucination_count} hallucinations removed"
        )
        
        return results
    
    def get_valid_texts(self, processed: List[ProcessedTranscription]) -> List[str]:
        """
        Extrait uniquement les textes valides d'une liste de résultats.
        
        Args:
            processed: Liste de résultats de traitement
        
        Returns:
            Liste des textes valides nettoyés
        """
        return [p.cleaned_text for p in processed if p.is_valid and p.cleaned_text]
    
    def clear_cache(self):
        """Vide le cache de détection d'hallucinations."""
        self._hallucination_cache.clear()
        self.logger.debug("Hallucination cache cleared")


def get_processor() -> TranscriptionProcessor:
    """
    Factory function pour obtenir une instance du processeur.
    
    Returns:
        Instance de TranscriptionProcessor
    
    Usage:
        >>> processor = get_processor()
        >>> result = processor.process_segment(segment)
        >>> if result.is_valid:
        ...     print(result.cleaned_text)
    """
    return TranscriptionProcessor()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("Testing TranscriptionProcessor...")
    
    processor = get_processor()
    
    test_segments = [
        TranscriptionSegment(
            text="Bonjour, je suis intéressé par votre pipeline de closing.",
            start=0.0,
            end=3.0,
            confidence=0.95,
            language="fr"
        ),
        TranscriptionSegment(
            text="Sous-titres réalisés par la communauté d'Amara.org",
            start=3.0,
            end=6.0,
            confidence=0.85,
            language="fr"
        ),
        TranscriptionSegment(
            text="Le ROI sur ce deal est excellent.",
            start=6.0,
            end=9.0,
            confidence=0.92,
            language="fr"
        ),
        TranscriptionSegment(
            text="Abonnez-vous à la chaîne",
            start=9.0,
            end=11.0,
            confidence=0.88,
            language="fr"
        ),
        TranscriptionSegment(
            text="   ",
            start=11.0,
            end=12.0,
            confidence=0.5,
            language="fr"
        ),
    ]
    
    print(f"\nProcessing {len(test_segments)} test segments...\n")
    
    results = processor.process_segments(test_segments)
    
    for i, result in enumerate(results):
        print(f"Segment {i+1}:")
        print(f"  Original: '{result.original_text}'")
        print(f"  Cleaned: '{result.cleaned_text}'")
        print(f"  Valid: {result.is_valid}")
        if result.removed_patterns:
            print(f"  Removed patterns: {result.removed_patterns}")
        print()
    
    valid_texts = processor.get_valid_texts(results)
    print(f"Valid texts ({len(valid_texts)}):")
    for text in valid_texts:
        print(f"  - {text}")
    
    print("\nTest completed!")
