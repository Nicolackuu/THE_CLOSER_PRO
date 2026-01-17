"""
THE CLOSER PRO V25 - Elite Processor
Nettoyage avancé des transcriptions avec filtrage intelligent des hallucinations.
Détection contextuelle et patterns multi-niveaux.

Author: THE CLOSER PRO Team
Version: 2.5.0 (Elite)
"""

import re
from typing import List, Set
from rapidfuzz import fuzz
import logging


class EliteProcessor:
    """
    Processeur Elite pour nettoyage avancé des transcriptions.
    Filtrage multi-niveaux des hallucinations et normalisation.
    """
    
    # Patterns d'hallucinations étendus
    HALLUCINATION_PATTERNS = {
        # Patterns Amara/Sous-titres
        "amara", "sous-titres", "sous-titre", "communauté", "réalisés para",
        
        # Patterns YouTube/Social
        "abonnez-vous", "abonne-toi", "liker", "like", "pouce bleu", "cloche",
        "notification", "partager", "partagez", "commentaire", "commentez",
        
        # Patterns anglais communs
        "thank you", "thanks", "yes", "no", "okay", "ok", "yeah", "yep",
        "i'm not", "i don't", "i can't", "you know", "like and subscribe",
        "please subscribe", "click the bell", "turn on notifications",
        
        # Patterns techniques
        "www.", "http", ".com", ".fr", ".org", "://",
        
        # Patterns de bruit
        "merci d'avoir regardé", "merci de vous abonner", "n'oubliez pas",
        "mettez un pouce", "activez la cloche", "partagez cette vidéo",
        
        # Patterns répétitifs (perroquet)
        "sous-titrage", "transcription automatique", "généré automatiquement"
    }
    
    # Patterns de répétition (détection de boucles)
    REPETITION_THRESHOLD = 3  # Nombre de répétitions avant filtrage
    
    # Mots vides français (à ignorer dans certains contextes)
    STOP_WORDS = {
        "le", "la", "les", "un", "une", "des", "de", "du", "et", "ou",
        "mais", "donc", "car", "ni", "que", "qui", "quoi", "dont"
    }
    
    def __init__(self, fuzzy_threshold: int = 85):
        """
        Initialise le processeur Elite.
        
        Args:
            fuzzy_threshold: Seuil de similarité fuzzy (0-100)
        """
        self.fuzzy_threshold = fuzzy_threshold
        self.logger = logging.getLogger(__name__)
        
        # Historique pour détection de répétitions
        self.recent_texts: List[str] = []
        self.max_history = 20
        
        # Statistiques
        self.total_processed = 0
        self.total_filtered = 0
        self.total_cleaned = 0
    
    def clean_text(self, text: str) -> str:
        """
        Nettoie un texte transcrit.
        
        Args:
            text: Texte brut
        
        Returns:
            Texte nettoyé
        """
        if not text:
            return ""
        
        self.total_processed += 1
        original = text
        
        # 1. Normalisation de base
        text = text.strip()
        
        # 2. Suppression des espaces multiples
        text = re.sub(r'\s+', ' ', text)
        
        # 3. Suppression des caractères spéciaux parasites
        text = re.sub(r'[♪♫🎵🎶]', '', text)  # Notes de musique
        text = re.sub(r'\[.*?\]', '', text)  # Balises entre crochets
        text = re.sub(r'\(.*?\)', '', text)  # Parenthèses (souvent du bruit)
        
        # 4. Normalisation de la ponctuation
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)  # Espace avant ponctuation
        text = re.sub(r'([.,!?;:])\s*', r'\1 ', text)  # Espace après ponctuation
        
        # 5. Capitalisation intelligente
        if text and not text[0].isupper():
            text = text[0].upper() + text[1:]
        
        # 6. Suppression des URLs
        text = re.sub(r'http\S+|www\.\S+', '', text)
        
        # 7. Nettoyage final
        text = text.strip()
        
        if text != original:
            self.total_cleaned += 1
        
        return text
    
    def is_hallucination(self, text: str) -> bool:
        """
        Détermine si un texte est une hallucination.
        
        Args:
            text: Texte à vérifier
        
        Returns:
            True si hallucination détectée
        """
        if not text or len(text) < 2:
            return True
        
        text_lower = text.lower()
        
        # 1. Vérification des patterns exacts
        for pattern in self.HALLUCINATION_PATTERNS:
            if pattern in text_lower:
                self.logger.debug(f"Hallucination detected (pattern): {pattern} in {text}")
                self.total_filtered += 1
                return True
        
        # 2. Vérification fuzzy contre les patterns connus
        for pattern in self.HALLUCINATION_PATTERNS:
            similarity = fuzz.partial_ratio(pattern, text_lower)
            if similarity > self.fuzzy_threshold:
                self.logger.debug(f"Hallucination detected (fuzzy {similarity}%): {text}")
                self.total_filtered += 1
                return True
        
        # 3. Détection de répétitions (perroquet)
        if self._is_repetitive(text):
            self.logger.debug(f"Repetition detected: {text}")
            self.total_filtered += 1
            return True
        
        # 4. Texte trop court (probable bruit)
        words = text.split()
        if len(words) == 1 and len(text) < 3:
            return True
        
        # 5. Texte entièrement en majuscules (souvent du spam)
        if text.isupper() and len(text) > 10:
            return True
        
        # 6. Ratio de caractères spéciaux trop élevé
        special_chars = sum(1 for c in text if not c.isalnum() and not c.isspace())
        if len(text) > 0 and (special_chars / len(text)) > 0.3:
            return True
        
        return False
    
    def _is_repetitive(self, text: str) -> bool:
        """
        Détecte si un texte est une répétition récente.
        
        Args:
            text: Texte à vérifier
        
        Returns:
            True si répétition détectée
        """
        # Normaliser pour la comparaison
        normalized = text.lower().strip()
        
        # Compter les occurrences similaires récentes
        similar_count = 0
        for recent in self.recent_texts:
            similarity = fuzz.ratio(normalized, recent.lower())
            if similarity > 90:  # Très similaire
                similar_count += 1
        
        # Ajouter à l'historique
        self.recent_texts.append(text)
        if len(self.recent_texts) > self.max_history:
            self.recent_texts.pop(0)
        
        return similar_count >= self.REPETITION_THRESHOLD
    
    def is_meaningful(self, text: str, min_words: int = 2) -> bool:
        """
        Vérifie si un texte a du sens (pas juste des mots vides).
        
        Args:
            text: Texte à vérifier
            min_words: Nombre minimum de mots significatifs
        
        Returns:
            True si le texte est significatif
        """
        if not text:
            return False
        
        words = text.lower().split()
        meaningful_words = [w for w in words if w not in self.STOP_WORDS and len(w) > 2]
        
        return len(meaningful_words) >= min_words
    
    def extract_entities(self, text: str) -> dict:
        """
        Extrait les entités importantes du texte.
        
        Args:
            text: Texte à analyser
        
        Returns:
            Dict avec les entités détectées
        """
        entities = {
            "prices": [],
            "numbers": [],
            "names": [],
            "emails": [],
            "phones": []
        }
        
        # Prix (€, $, euros, dollars)
        price_patterns = [
            r'(\d+(?:[.,]\d+)?)\s*(?:€|euros?|EUR)',
            r'(?:\$|dollars?|USD)\s*(\d+(?:[.,]\d+)?)',
            r'(\d+)\s*(?:mille|millions?|milliards?)'
        ]
        for pattern in price_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            entities["prices"].extend(matches)
        
        # Nombres importants (3+ chiffres)
        numbers = re.findall(r'\b\d{3,}\b', text)
        entities["numbers"].extend(numbers)
        
        # Emails
        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        entities["emails"].extend(emails)
        
        # Téléphones (formats français)
        phones = re.findall(r'\b(?:0[1-9](?:\s?\d{2}){4})\b', text)
        entities["phones"].extend(phones)
        
        # Noms propres (mots capitalisés)
        words = text.split()
        for i, word in enumerate(words):
            if word and word[0].isupper() and len(word) > 2:
                # Éviter les débuts de phrase
                if i > 0 and not words[i-1].endswith('.'):
                    entities["names"].append(word)
        
        return entities
    
    def normalize_french(self, text: str) -> str:
        """
        Normalise le texte français (accents, cédilles, etc.).
        
        Args:
            text: Texte à normaliser
        
        Returns:
            Texte normalisé
        """
        # Corrections courantes
        replacements = {
            "œ": "oe",
            "æ": "ae",
            "Œ": "Oe",
            "Æ": "Ae"
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        return text
    
    def get_stats(self) -> dict:
        """
        Retourne les statistiques du processeur.
        
        Returns:
            Dict avec les métriques
        """
        filter_rate = 0.0
        clean_rate = 0.0
        
        if self.total_processed > 0:
            filter_rate = (self.total_filtered / self.total_processed) * 100
            clean_rate = (self.total_cleaned / self.total_processed) * 100
        
        return {
            "total_processed": self.total_processed,
            "total_filtered": self.total_filtered,
            "total_cleaned": self.total_cleaned,
            "filter_rate_percent": filter_rate,
            "clean_rate_percent": clean_rate
        }
    
    def reset_history(self):
        """Réinitialise l'historique de répétitions."""
        self.recent_texts.clear()


# Singleton
_processor_instance: EliteProcessor = None

def get_elite_processor() -> EliteProcessor:
    """Retourne l'instance singleton du processeur Elite."""
    global _processor_instance
    if _processor_instance is None:
        _processor_instance = EliteProcessor(fuzzy_threshold=85)
    return _processor_instance
