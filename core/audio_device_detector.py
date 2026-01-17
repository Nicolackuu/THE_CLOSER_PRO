"""
THE CLOSER PRO V25 - Audio Device Auto-Detector
Détection intelligente des périphériques VoiceMeeter avec support stéréo.
Résout le bug PaErrorCode -9998 (Invalid number of channels).

Author: THE CLOSER PRO Team
Version: 2.5.0 (Core Engine)
"""

import sounddevice as sd
import logging
from typing import Optional, Dict, List
from dataclasses import dataclass


@dataclass
class AudioDeviceInfo:
    """Informations sur un périphérique audio."""
    id: int
    name: str
    max_input_channels: int
    max_output_channels: int
    default_samplerate: float
    is_voicemeeter: bool = False
    supports_stereo_input: bool = False


class AudioDeviceDetector:
    """
    Détecteur intelligent de périphériques audio.
    Trouve automatiquement VoiceMeeter avec support stéréo.
    """
    
    VOICEMEETER_KEYWORDS = [
        "voicemeeter",
        "vb-audio",
        "vb audio",
        "cable"
    ]
    
    def __init__(self):
        """Initialise le détecteur."""
        self.logger = logging.getLogger(__name__)
        self._devices_cache: Optional[List[AudioDeviceInfo]] = None
    
    def scan_devices(self) -> List[AudioDeviceInfo]:
        """
        Scanne tous les périphériques audio disponibles.
        
        Returns:
            Liste des périphériques détectés
        """
        devices = []
        
        try:
            raw_devices = sd.query_devices()
            
            for idx, device in enumerate(raw_devices):
                name = device['name'].lower()
                
                # Vérifier si c'est un périphérique VoiceMeeter
                is_vm = any(keyword in name for keyword in self.VOICEMEETER_KEYWORDS)
                
                # Vérifier le support stéréo en entrée
                supports_stereo = device['max_input_channels'] >= 2
                
                device_info = AudioDeviceInfo(
                    id=idx,
                    name=device['name'],
                    max_input_channels=device['max_input_channels'],
                    max_output_channels=device['max_output_channels'],
                    default_samplerate=device['default_samplerate'],
                    is_voicemeeter=is_vm,
                    supports_stereo_input=supports_stereo
                )
                
                devices.append(device_info)
            
            self._devices_cache = devices
            return devices
            
        except Exception as e:
            self.logger.error(f"Error scanning audio devices: {e}", exc_info=True)
            return []
    
    def find_voicemeeter_device(
        self,
        require_stereo: bool = True,
        preferred_name: Optional[str] = None
    ) -> Optional[AudioDeviceInfo]:
        """
        Trouve le périphérique VoiceMeeter optimal.
        
        Args:
            require_stereo: Exiger le support stéréo (2 canaux)
            preferred_name: Nom préféré (ex: "B1", "Aux")
        
        Returns:
            AudioDeviceInfo du meilleur périphérique trouvé, ou None
        """
        if self._devices_cache is None:
            self.scan_devices()
        
        # Filtrer les périphériques VoiceMeeter
        vm_devices = [d for d in self._devices_cache if d.is_voicemeeter]
        
        if not vm_devices:
            self.logger.warning("No VoiceMeeter devices found")
            return None
        
        # Filtrer par support stéréo si requis
        if require_stereo:
            vm_devices = [d for d in vm_devices if d.supports_stereo_input]
        
        if not vm_devices:
            self.logger.warning("No VoiceMeeter devices with stereo input support found")
            return None
        
        # Si un nom préféré est spécifié, le chercher
        if preferred_name:
            preferred_name_lower = preferred_name.lower()
            for device in vm_devices:
                if preferred_name_lower in device.name.lower():
                    self.logger.info(f"Found preferred VoiceMeeter device: {device.name} (ID: {device.id})")
                    return device
        
        # Sinon, prendre le premier avec le plus de canaux
        best_device = max(vm_devices, key=lambda d: d.max_input_channels)
        
        self.logger.info(
            f"Auto-selected VoiceMeeter device: {best_device.name} "
            f"(ID: {best_device.id}, Channels: {best_device.max_input_channels})"
        )
        
        return best_device
    
    def validate_device_config(
        self,
        device_id: int,
        required_channels: int,
        required_samplerate: int
    ) -> Dict[str, any]:
        """
        Valide qu'un périphérique supporte la configuration demandée.
        
        Args:
            device_id: ID du périphérique
            required_channels: Nombre de canaux requis
            required_samplerate: Fréquence d'échantillonnage requise
        
        Returns:
            Dict avec 'valid' (bool) et 'message' (str)
        """
        try:
            device = sd.query_devices(device_id)
            
            # Vérifier les canaux
            if device['max_input_channels'] < required_channels:
                return {
                    'valid': False,
                    'message': (
                        f"Device {device['name']} only supports "
                        f"{device['max_input_channels']} input channels, "
                        f"but {required_channels} required"
                    ),
                    'max_channels': device['max_input_channels'],
                    'suggested_channels': min(device['max_input_channels'], required_channels)
                }
            
            # Vérifier le sample rate (avec tolérance)
            default_sr = device['default_samplerate']
            if abs(default_sr - required_samplerate) > 1000:
                self.logger.warning(
                    f"Device default sample rate ({default_sr} Hz) differs from "
                    f"required ({required_samplerate} Hz). May cause issues."
                )
            
            return {
                'valid': True,
                'message': f"Device {device['name']} is compatible",
                'max_channels': device['max_input_channels'],
                'default_samplerate': default_sr
            }
            
        except Exception as e:
            return {
                'valid': False,
                'message': f"Error validating device: {e}",
                'max_channels': 0
            }
    
    def get_optimal_config(self, device_id: int) -> Dict[str, any]:
        """
        Retourne la configuration optimale pour un périphérique.
        
        Args:
            device_id: ID du périphérique
        
        Returns:
            Dict avec les paramètres optimaux
        """
        try:
            device = sd.query_devices(device_id)
            
            # Déterminer le nombre de canaux optimal
            max_channels = device['max_input_channels']
            optimal_channels = min(2, max_channels)  # Préférer stéréo si possible
            
            return {
                'device_id': device_id,
                'device_name': device['name'],
                'channels': optimal_channels,
                'sample_rate': int(device['default_samplerate']),
                'max_channels': max_channels,
                'is_stereo': optimal_channels >= 2
            }
            
        except Exception as e:
            self.logger.error(f"Error getting optimal config: {e}")
            return {
                'device_id': device_id,
                'channels': 1,
                'sample_rate': 48000,
                'max_channels': 1,
                'is_stereo': False
            }
    
    def print_device_report(self):
        """Affiche un rapport détaillé des périphériques."""
        if self._devices_cache is None:
            self.scan_devices()
        
        print("\n" + "="*70)
        print("AUDIO DEVICES REPORT - THE CLOSER PRO v0.25")
        print("="*70 + "\n")
        
        vm_devices = [d for d in self._devices_cache if d.is_voicemeeter]
        other_devices = [d for d in self._devices_cache if not d.is_voicemeeter]
        
        if vm_devices:
            print("🎙️  VOICEMEETER DEVICES:")
            print("-" * 70)
            for device in vm_devices:
                stereo_icon = "✅" if device.supports_stereo_input else "❌"
                print(f"  [{device.id:2d}] {device.name}")
                print(f"       Stereo Input: {stereo_icon} ({device.max_input_channels} channels)")
                print(f"       Sample Rate: {device.default_samplerate:.0f} Hz")
                print()
        else:
            print("⚠️  NO VOICEMEETER DEVICES FOUND")
            print()
        
        if other_devices:
            print("🔊 OTHER INPUT DEVICES:")
            print("-" * 70)
            for device in other_devices:
                if device.max_input_channels > 0:
                    print(f"  [{device.id:2d}] {device.name}")
                    print(f"       Input Channels: {device.max_input_channels}")
                    print()
        
        print("="*70 + "\n")


# Singleton instance
_detector_instance: Optional[AudioDeviceDetector] = None

def get_audio_detector() -> AudioDeviceDetector:
    """Retourne l'instance singleton du détecteur."""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = AudioDeviceDetector()
    return _detector_instance


if __name__ == "__main__":
    # Test du détecteur
    logging.basicConfig(level=logging.INFO)
    
    detector = get_audio_detector()
    detector.print_device_report()
    
    # Chercher VoiceMeeter
    vm_device = detector.find_voicemeeter_device(require_stereo=True, preferred_name="B1")
    
    if vm_device:
        print(f"\n✅ VoiceMeeter device found: {vm_device.name} (ID: {vm_device.id})")
        
        # Valider la config
        validation = detector.validate_device_config(vm_device.id, 2, 48000)
        print(f"\nValidation: {validation['message']}")
        
        # Config optimale
        optimal = detector.get_optimal_config(vm_device.id)
        print(f"\nOptimal config:")
        print(f"  Channels: {optimal['channels']}")
        print(f"  Sample Rate: {optimal['sample_rate']} Hz")
    else:
        print("\n❌ No suitable VoiceMeeter device found")
