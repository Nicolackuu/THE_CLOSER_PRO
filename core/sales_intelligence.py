"""
THE CLOSER PRO v0.25 - Sales Intelligence Engine
Extraction en temps réel des entités de vente : Budget, Objections, Noms.
Smart Summary pour garder le dernier point d'accord.

Author: THE CLOSER PRO Team
Version: 0.25 (Elite Edition)
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from datetime import datetime
import logging


@dataclass
class Budget:
    """Représente un budget ou prix mentionné."""
    amount: float
    currency: str
    context: str
    timestamp: datetime
    speaker: str  # "VOUS" ou "CLIENT"


@dataclass
class Objection:
    """Représente une objection détectée."""
    type: str  # "prix", "temps", "concurrence", "autorité", "besoin"
    text: str
    timestamp: datetime
    severity: int  # 1-5 (5 = objection forte)
    resolved: bool = False


@dataclass
class Entity:
    """Entité extraite (nom, entreprise, etc.)."""
    type: str  # "nom", "entreprise", "produit", "concurrent"
    value: str
    timestamp: datetime
    speaker: str


@dataclass
class AgreementPoint:
    """Point d'accord trouvé dans la conversation."""
    description: str
    timestamp: datetime
    confidence: float  # 0-1


class SalesIntelligence:
    """
    Moteur d'intelligence de vente.
    Extrait et analyse les informations critiques en temps réel.
    """
    
    # Patterns d'objections
    OBJECTION_PATTERNS = {
        "prix": [
            r"(?:c'est |trop |très )?cher",
            r"(?:le )?prix (?:est )?(?:trop )?(?:élevé|haut)",
            r"(?:pas|n'ai pas) (?:le |les )?(?:moyens|budget)",
            r"(?:coûte|coûtent) trop",
            r"(?:je )?(?:peux|peut) pas (?:me )?payer",
            r"(?:au-dessus|dépasse) (?:de |mon )?budget"
        ],
        "temps": [
            r"(?:je )?(?:dois|vais) (?:y )?réfléchir",
            r"(?:je )?(?:vais|dois) (?:en )?(?:parler|discuter)",
            r"(?:rappelle|recontacte)(?:z)?-moi",
            r"(?:je )?(?:vous|te) (?:rappelle|recontacte)",
            r"(?:pas |n'ai pas )(?:le )?temps",
            r"(?:trop|très) (?:occupé|chargé)"
        ],
        "concurrence": [
            r"(?:je )?(?:vais|dois) (?:comparer|voir) (?:avec |d'autres )?(?:offres|concurrents)",
            r"(?:d')?autres (?:propositions|offres|solutions)",
            r"(?:la )?concurrence (?:propose|offre)",
            r"(?:moins )?cher (?:ailleurs|chez)"
        ],
        "autorité": [
            r"(?:je )?(?:dois|vais) (?:en )?parler (?:à|avec) (?:mon |ma )?(?:femme|mari|conjoint|patron|associé)",
            r"(?:c'est )?pas moi (?:qui |le )?décide",
            r"(?:je )?(?:peux|peut) pas (?:décider|signer) (?:seul|tout seul)"
        ],
        "besoin": [
            r"(?:je )?(?:suis|ne suis) pas (?:sûr|certain|convaincu)",
            r"(?:j')?(?:ai|hésite|doute)",
            r"(?:pas|ne vois pas) (?:l')?(?:intérêt|utilité)",
            r"(?:ça )?(?:me|nous) (?:sert|servira) (?:à )?(?:quoi|rien)"
        ]
    }
    
    # Patterns de prix/budget
    PRICE_PATTERNS = [
        r'(\d+(?:\s?\d{3})*(?:[.,]\d+)?)\s*(?:€|euros?|EUR)',
        r'(?:€|euros?|EUR)\s*(\d+(?:\s?\d{3})*(?:[.,]\d+)?)',
        r'(\d+(?:\s?\d{3})*(?:[.,]\d+)?)\s*(?:\$|dollars?|USD)',
        r'(?:\$|dollars?|USD)\s*(\d+(?:\s?\d{3})*(?:[.,]\d+)?)',
        r'(\d+)\s*(?:k|K|mille)',
        r'(\d+(?:[.,]\d+)?)\s*(?:millions?|M)'
    ]
    
    # Patterns d'accord
    AGREEMENT_PATTERNS = [
        r"(?:d')?accord",
        r"(?:c'est )?parfait",
        r"(?:très )?bien",
        r"(?:ça )?(?:me|nous) (?:va|convient|plaît)",
        r"(?:je )?(?:suis|sommes) (?:d'accord|partant)",
        r"(?:allons-)?y",
        r"(?:on )?(?:fait|fais) (?:comme )?ça",
        r"(?:je )?(?:valide|accepte|confirme)"
    ]
    
    def __init__(self):
        """Initialise le moteur d'intelligence."""
        self.logger = logging.getLogger(__name__)
        
        # Stockage des entités
        self.budgets: List[Budget] = []
        self.objections: List[Objection] = []
        self.entities: List[Entity] = []
        self.agreement_points: List[AgreementPoint] = []
        
        # Smart Summary
        self.last_agreement: Optional[AgreementPoint] = None
        self.active_objections: List[Objection] = []
        
        # Cache pour éviter les doublons
        self._processed_texts: Set[str] = set()
    
    def analyze_text(
        self,
        text: str,
        speaker: str,
        timestamp: Optional[datetime] = None
    ):
        """
        Analyse un texte et extrait toutes les informations.
        
        Args:
            text: Texte à analyser
            speaker: "VOUS" ou "CLIENT"
            timestamp: Timestamp du texte
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        # Éviter les doublons
        text_key = f"{speaker}:{text}"
        if text_key in self._processed_texts:
            return
        self._processed_texts.add(text_key)
        
        text_lower = text.lower()
        
        # Extraction des budgets/prix
        self._extract_budgets(text, text_lower, speaker, timestamp)
        
        # Détection des objections (seulement pour CLIENT)
        if speaker == "CLIENT":
            self._detect_objections(text, text_lower, timestamp)
        
        # Extraction des entités
        self._extract_entities(text, speaker, timestamp)
        
        # Détection des points d'accord
        self._detect_agreements(text, text_lower, timestamp)
    
    def _extract_budgets(
        self,
        text: str,
        text_lower: str,
        speaker: str,
        timestamp: datetime
    ):
        """Extrait les montants et budgets."""
        for pattern in self.PRICE_PATTERNS:
            matches = re.finditer(pattern, text_lower, re.IGNORECASE)
            
            for match in matches:
                amount_str = match.group(1).replace(' ', '').replace(',', '.')
                
                try:
                    # Convertir en float
                    amount = float(amount_str)
                    
                    # Gérer les multiplicateurs (k, M)
                    if 'k' in text_lower[match.start():match.end()].lower():
                        amount *= 1000
                    elif 'million' in text_lower[match.start():match.end()].lower():
                        amount *= 1000000
                    
                    # Déterminer la devise
                    currency = "EUR"
                    if '$' in match.group(0) or 'dollar' in match.group(0).lower():
                        currency = "USD"
                    
                    # Créer l'objet Budget
                    budget = Budget(
                        amount=amount,
                        currency=currency,
                        context=text,
                        timestamp=timestamp,
                        speaker=speaker
                    )
                    
                    self.budgets.append(budget)
                    self.logger.info(f"Budget detected: {amount} {currency} by {speaker}")
                    
                except ValueError:
                    continue
    
    def _detect_objections(
        self,
        text: str,
        text_lower: str,
        timestamp: datetime
    ):
        """Détecte les objections dans le texte."""
        for obj_type, patterns in self.OBJECTION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    # Calculer la sévérité
                    severity = self._calculate_objection_severity(text_lower, obj_type)
                    
                    objection = Objection(
                        type=obj_type,
                        text=text,
                        timestamp=timestamp,
                        severity=severity,
                        resolved=False
                    )
                    
                    self.objections.append(objection)
                    self.active_objections.append(objection)
                    
                    self.logger.warning(
                        f"Objection detected: {obj_type} (severity {severity}/5) - \"{text}\""
                    )
                    break
    
    def _calculate_objection_severity(self, text: str, obj_type: str) -> int:
        """
        Calcule la sévérité d'une objection (1-5).
        
        Args:
            text: Texte de l'objection
            obj_type: Type d'objection
        
        Returns:
            Sévérité de 1 à 5
        """
        severity = 3  # Base
        
        # Mots qui augmentent la sévérité
        strong_words = ["jamais", "impossible", "absolument", "vraiment", "très"]
        for word in strong_words:
            if word in text:
                severity += 1
        
        # Mots qui diminuent la sévérité
        soft_words = ["peut-être", "probablement", "un peu"]
        for word in soft_words:
            if word in text:
                severity -= 1
        
        # Type d'objection influence la sévérité
        if obj_type == "besoin":
            severity += 1  # Objection de besoin = plus grave
        
        return max(1, min(5, severity))
    
    def _extract_entities(
        self,
        text: str,
        speaker: str,
        timestamp: datetime
    ):
        """Extrait les entités (noms, entreprises)."""
        words = text.split()
        
        for i, word in enumerate(words):
            # Noms propres (capitalisés)
            if word and word[0].isupper() and len(word) > 2:
                # Éviter les débuts de phrase
                if i > 0 and not words[i-1].endswith('.'):
                    # Vérifier si c'est potentiellement un nom
                    if not word.lower() in ['le', 'la', 'les', 'un', 'une', 'des']:
                        entity = Entity(
                            type="nom",
                            value=word,
                            timestamp=timestamp,
                            speaker=speaker
                        )
                        self.entities.append(entity)
    
    def _detect_agreements(
        self,
        text: str,
        text_lower: str,
        timestamp: datetime
    ):
        """Détecte les points d'accord."""
        for pattern in self.AGREEMENT_PATTERNS:
            if re.search(pattern, text_lower):
                # Calculer la confiance
                confidence = 0.7
                
                # Augmenter si plusieurs mots d'accord
                agreement_count = sum(
                    1 for p in self.AGREEMENT_PATTERNS 
                    if re.search(p, text_lower)
                )
                confidence = min(1.0, 0.5 + (agreement_count * 0.2))
                
                agreement = AgreementPoint(
                    description=text,
                    timestamp=timestamp,
                    confidence=confidence
                )
                
                self.agreement_points.append(agreement)
                self.last_agreement = agreement
                
                self.logger.info(f"Agreement detected (confidence {confidence:.0%}): \"{text}\"")
                break
    
    def get_smart_summary(self) -> Dict:
        """
        Génère un résumé intelligent de la session.
        
        Returns:
            Dict avec les informations clés
        """
        # Budget moyen/max
        client_budgets = [b for b in self.budgets if b.speaker == "CLIENT"]
        your_prices = [b for b in self.budgets if b.speaker == "VOUS"]
        
        avg_client_budget = 0.0
        if client_budgets:
            avg_client_budget = sum(b.amount for b in client_budgets) / len(client_budgets)
        
        avg_your_price = 0.0
        if your_prices:
            avg_your_price = sum(b.amount for b in your_prices) / len(your_prices)
        
        # Objections actives (non résolues)
        active_objs = [o for o in self.objections if not o.resolved]
        
        # Dernier accord
        last_agreement_text = None
        if self.last_agreement:
            last_agreement_text = self.last_agreement.description
        
        return {
            "budgets": {
                "client_budget_avg": avg_client_budget,
                "your_price_avg": avg_your_price,
                "total_mentions": len(self.budgets)
            },
            "objections": {
                "total": len(self.objections),
                "active": len(active_objs),
                "by_type": self._count_objections_by_type(),
                "most_severe": self._get_most_severe_objection()
            },
            "entities": {
                "names": list(set(e.value for e in self.entities if e.type == "nom")),
                "total": len(self.entities)
            },
            "last_agreement": last_agreement_text,
            "agreement_count": len(self.agreement_points)
        }
    
    def _count_objections_by_type(self) -> Dict[str, int]:
        """Compte les objections par type."""
        counts = {}
        for obj in self.objections:
            counts[obj.type] = counts.get(obj.type, 0) + 1
        return counts
    
    def _get_most_severe_objection(self) -> Optional[Dict]:
        """Retourne l'objection la plus sévère."""
        active = [o for o in self.objections if not o.resolved]
        if not active:
            return None
        
        most_severe = max(active, key=lambda o: o.severity)
        return {
            "type": most_severe.type,
            "text": most_severe.text,
            "severity": most_severe.severity
        }
    
    def generate_ai_recommendation(self) -> str:
        """
        Génère une recommandation IA pour le follow-up.
        
        Returns:
            Texte de recommandation
        """
        summary = self.get_smart_summary()
        
        recommendations = []
        
        # Recommandation budget
        if summary["budgets"]["client_budget_avg"] > 0:
            if summary["budgets"]["your_price_avg"] > summary["budgets"]["client_budget_avg"]:
                recommendations.append(
                    f"💰 Votre prix ({summary['budgets']['your_price_avg']:.0f}€) "
                    f"dépasse le budget client ({summary['budgets']['client_budget_avg']:.0f}€). "
                    "Proposez un plan de paiement ou une version allégée."
                )
        
        # Recommandation objections
        if summary["objections"]["active"] > 0:
            obj_types = summary["objections"]["by_type"]
            main_objection = max(obj_types.items(), key=lambda x: x[1])[0]
            
            objection_tips = {
                "prix": "Recentrez sur la VALEUR, pas le prix. Montrez le ROI.",
                "temps": "Créez l'urgence. Montrez ce qu'ils perdent en attendant.",
                "concurrence": "Différenciez-vous. Qu'avez-vous d'UNIQUE ?",
                "autorité": "Proposez un appel à 3 avec le décideur.",
                "besoin": "Requalifiez le besoin. Posez des questions SPIN."
            }
            
            recommendations.append(
                f"⚠️ Objection principale : {main_objection.upper()}. "
                f"{objection_tips.get(main_objection, 'Traitez cette objection.')}"
            )
        
        # Recommandation accord
        if summary["last_agreement"]:
            recommendations.append(
                f"✅ Dernier accord : \"{summary['last_agreement']}\". "
                "Rappelez ce point dans le follow-up."
            )
        
        if not recommendations:
            recommendations.append(
                "📞 Aucune objection majeure détectée. "
                "Envoyez un follow-up de confirmation dans 24h."
            )
        
        return "\n".join(recommendations)
    
    def mark_objection_resolved(self, objection_text: str):
        """Marque une objection comme résolue."""
        for obj in self.objections:
            if obj.text == objection_text:
                obj.resolved = True
                if obj in self.active_objections:
                    self.active_objections.remove(obj)
                self.logger.info(f"Objection marked as resolved: {objection_text}")


# Singleton
_intelligence_instance: Optional[SalesIntelligence] = None

def get_sales_intelligence() -> SalesIntelligence:
    """Retourne l'instance singleton."""
    global _intelligence_instance
    if _intelligence_instance is None:
        _intelligence_instance = SalesIntelligence()
    return _intelligence_instance
