"""
THE CLOSER PRO v0.25 - Real-Time UI Engine
Affichage en temps réel du Talk-Ratio avec warnings visuels.
Barre de progression discrète et alertes intelligentes.

Author: THE CLOSER PRO Team
Version: 0.25 (Elite Edition)
"""

import sys
from datetime import datetime
from typing import Optional
from colorama import Fore, Style
import logging


class RealtimeUI:
    """
    Moteur d'interface temps réel.
    Affiche le Talk-Ratio et les warnings sans polluer le terminal.
    """
    
    # Seuils d'alerte
    WARNING_THRESHOLD = 60.0  # Si VOUS parlez > 60%, warning
    CRITICAL_THRESHOLD = 70.0  # Si VOUS parlez > 70%, alerte critique
    
    def __init__(self):
        """Initialise l'UI temps réel."""
        self.logger = logging.getLogger(__name__)
        self._last_ratio_display = None
        self._warning_shown = False
        self._critical_shown = False
    
    def display_ratio_bar(
        self,
        vous_percentage: float,
        client_percentage: float,
        compact: bool = True
    ):
        """
        Affiche une barre de progression du Talk-Ratio.
        
        Args:
            vous_percentage: Pourcentage VOUS
            client_percentage: Pourcentage CLIENT
            compact: Mode compact (une ligne)
        """
        # Éviter les mises à jour trop fréquentes
        if self._last_ratio_display:
            time_since_last = (datetime.now() - self._last_ratio_display).total_seconds()
            if time_since_last < 5.0:  # Mise à jour max toutes les 5s
                return
        
        self._last_ratio_display = datetime.now()
        
        # Créer la barre de progression
        bar_width = 40
        vous_width = int((vous_percentage / 100) * bar_width)
        client_width = bar_width - vous_width
        
        # Couleurs selon le ratio
        if vous_percentage > self.CRITICAL_THRESHOLD:
            vous_color = Fore.RED
            status_icon = "🔴"
        elif vous_percentage > self.WARNING_THRESHOLD:
            vous_color = Fore.YELLOW
            status_icon = "⚠️"
        else:
            vous_color = Fore.GREEN
            status_icon = "✅"
        
        # Construire la barre
        bar = (
            f"{vous_color}{'█' * vous_width}{Style.RESET_ALL}"
            f"{Fore.CYAN}{'░' * client_width}{Style.RESET_ALL}"
        )
        
        if compact:
            # Mode compact : une ligne
            ratio_line = (
                f"\r{status_icon} [{bar}] "
                f"{vous_color}YOU: {vous_percentage:.0f}%{Style.RESET_ALL} | "
                f"{Fore.CYAN}CLIENT: {client_percentage:.0f}%{Style.RESET_ALL}"
            )
            
            # Écrire sans newline
            sys.stdout.write(ratio_line)
            sys.stdout.flush()
        else:
            # Mode étendu : plusieurs lignes
            print(f"\n{status_icon} TALK-TO-LISTEN RATIO:")
            print(f"[{bar}]")
            print(
                f"{vous_color}VOUS: {vous_percentage:.0f}%{Style.RESET_ALL} | "
                f"{Fore.CYAN}CLIENT: {client_percentage:.0f}%{Style.RESET_ALL}\n"
            )
    
    def check_and_display_warnings(
        self,
        vous_percentage: float
    ) -> Optional[str]:
        """
        Vérifie et affiche les warnings si nécessaire.
        
        Args:
            vous_percentage: Pourcentage de parole VOUS
        
        Returns:
            Message de warning ou None
        """
        warning_msg = None
        
        # Warning critique (>70%)
        if vous_percentage > self.CRITICAL_THRESHOLD:
            if not self._critical_shown:
                warning_msg = (
                    f"\n{Fore.RED}{'='*70}\n"
                    f"🔴 ALERTE CRITIQUE : VOUS PARLEZ TROP ! ({vous_percentage:.0f}%)\n"
                    f"⚠️  ÉCOUTEZ PLUS ! Le client doit parler 70% du temps.\n"
                    f"{'='*70}{Style.RESET_ALL}\n"
                )
                self._critical_shown = True
                self._warning_shown = True
        
        # Warning normal (>60%)
        elif vous_percentage > self.WARNING_THRESHOLD:
            if not self._warning_shown:
                warning_msg = (
                    f"\n{Fore.YELLOW}{'─'*70}\n"
                    f"⚠️  ATTENTION : Vous parlez un peu trop ({vous_percentage:.0f}%)\n"
                    f"💡 Posez plus de questions et écoutez les réponses.\n"
                    f"{'─'*70}{Style.RESET_ALL}\n"
                )
                self._warning_shown = True
        
        # Réinitialiser les flags si le ratio s'améliore
        else:
            if self._warning_shown or self._critical_shown:
                # Afficher un message de félicitations
                warning_msg = (
                    f"\n{Fore.GREEN}{'─'*70}\n"
                    f"✅ EXCELLENT ! Ratio optimal ({vous_percentage:.0f}%)\n"
                    f"{'─'*70}{Style.RESET_ALL}\n"
                )
            self._warning_shown = False
            self._critical_shown = False
        
        if warning_msg:
            print(warning_msg, flush=True)
        
        return warning_msg
    
    def display_live_stats(
        self,
        vous_pct: float,
        client_pct: float,
        session_duration: float,
        objections_count: int = 0,
        last_agreement: Optional[str] = None
    ):
        """
        Affiche les stats live de manière compacte.
        
        Args:
            vous_pct: Pourcentage VOUS
            client_pct: Pourcentage CLIENT
            session_duration: Durée de session (secondes)
            objections_count: Nombre d'objections détectées
            last_agreement: Dernier point d'accord
        """
        # Formater la durée
        minutes = int(session_duration // 60)
        seconds = int(session_duration % 60)
        duration_str = f"{minutes:02d}:{seconds:02d}"
        
        # Couleur du ratio
        if vous_pct > self.CRITICAL_THRESHOLD:
            ratio_color = Fore.RED
        elif vous_pct > self.WARNING_THRESHOLD:
            ratio_color = Fore.YELLOW
        else:
            ratio_color = Fore.GREEN
        
        # Ligne de stats compacte
        stats_line = (
            f"\r⏱️  {duration_str} | "
            f"{ratio_color}YOU: {vous_pct:.0f}%{Style.RESET_ALL} | "
            f"{Fore.CYAN}CLIENT: {client_pct:.0f}%{Style.RESET_ALL}"
        )
        
        if objections_count > 0:
            stats_line += f" | ⚠️  {objections_count} objections"
        
        if last_agreement:
            # Tronquer si trop long
            agreement_short = last_agreement[:30] + "..." if len(last_agreement) > 30 else last_agreement
            stats_line += f" | ✅ \"{agreement_short}\""
        
        # Afficher
        sys.stdout.write(stats_line + " " * 10)  # Padding pour effacer l'ancien texte
        sys.stdout.flush()
    
    def clear_line(self):
        """Efface la ligne courante."""
        sys.stdout.write("\r" + " " * 100 + "\r")
        sys.stdout.flush()
    
    def display_objection_alert(
        self,
        objection_type: str,
        objection_text: str,
        severity: int
    ):
        """
        Affiche une alerte pour une nouvelle objection.
        
        Args:
            objection_type: Type d'objection
            objection_text: Texte de l'objection
            severity: Sévérité (1-5)
        """
        # Couleur selon sévérité
        if severity >= 4:
            color = Fore.RED
            icon = "🔴"
        elif severity >= 3:
            color = Fore.YELLOW
            icon = "⚠️"
        else:
            color = Fore.WHITE
            icon = "ℹ️"
        
        # Afficher l'alerte
        alert = (
            f"\n{color}{'─'*70}\n"
            f"{icon} OBJECTION DÉTECTÉE : {objection_type.upper()} (sévérité {severity}/5)\n"
            f"💬 \"{objection_text}\"\n"
            f"{'─'*70}{Style.RESET_ALL}\n"
        )
        
        print(alert, flush=True)
    
    def display_budget_alert(
        self,
        amount: float,
        currency: str,
        speaker: str
    ):
        """
        Affiche une alerte pour un budget mentionné.
        
        Args:
            amount: Montant
            currency: Devise
            speaker: Locuteur
        """
        color = Fore.GREEN if speaker == "CLIENT" else Fore.CYAN
        
        alert = (
            f"\n{color}💰 BUDGET DÉTECTÉ : {amount:,.0f} {currency} ({speaker}){Style.RESET_ALL}\n"
        )
        
        print(alert, flush=True)
    
    def display_agreement_alert(self, agreement_text: str):
        """
        Affiche une alerte pour un point d'accord.
        
        Args:
            agreement_text: Texte de l'accord
        """
        alert = (
            f"\n{Fore.GREEN}{'─'*70}\n"
            f"✅ POINT D'ACCORD DÉTECTÉ !\n"
            f"💬 \"{agreement_text}\"\n"
            f"{'─'*70}{Style.RESET_ALL}\n"
        )
        
        print(alert, flush=True)
    
    def display_session_header(self):
        """Affiche l'en-tête de session."""
        print(f"\n{Fore.CYAN}{'─'*70}")
        print("📊 LIVE SESSION MONITORING")
        print(f"{'─'*70}{Style.RESET_ALL}\n")
    
    def display_tip(self, tip: str):
        """
        Affiche un conseil en temps réel.
        
        Args:
            tip: Texte du conseil
        """
        print(f"\n{Fore.YELLOW}💡 TIP: {tip}{Style.RESET_ALL}\n", flush=True)


# Singleton
_ui_instance: Optional[RealtimeUI] = None

def get_realtime_ui() -> RealtimeUI:
    """Retourne l'instance singleton."""
    global _ui_instance
    if _ui_instance is None:
        _ui_instance = RealtimeUI()
    return _ui_instance
