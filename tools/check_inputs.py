"""
Script pour lister tous les périphériques audio d'entrée disponibles
Utile pour trouver l'ID d'un périphérique spécifique (ex: VoiceMeeter Output)
"""

import pyaudio


def list_audio_devices():
    """Liste tous les périphériques audio d'entrée disponibles"""
    print("=" * 70)
    print("LISTE DES PERIPHERIQUES AUDIO D'ENTREE")
    print("=" * 70)
    print()
    
    # Initialiser PyAudio
    audio = pyaudio.PyAudio()
    
    try:
        device_count = audio.get_device_count()
        print(f"Nombre total de peripheriques: {device_count}\n")
        
        input_devices = []
        
        # Parcourir tous les périphériques
        for i in range(device_count):
            try:
                device_info = audio.get_device_info_by_index(i)
                
                # Vérifier si le périphérique supporte l'entrée
                if device_info['maxInputChannels'] > 0:
                    input_devices.append({
                        'index': i,
                        'name': device_info['name'],
                        'channels': device_info['maxInputChannels'],
                        'sample_rate': int(device_info['defaultSampleRate'])
                    })
            except Exception as e:
                print(f"[ERREUR] Impossible de lire le peripherique {i}: {e}")
        
        # Afficher les périphériques d'entrée
        if input_devices:
            print("PERIPHERIQUES D'ENTREE DISPONIBLES:\n")
            for device in input_devices:
                print(f"  Index: {device['index']:3d} | "
                      f"Nom: {device['name']:<50} | "
                      f"Canaux: {device['channels']} | "
                      f"Sample Rate: {device['sample_rate']} Hz")
            
            print()
            print("=" * 70)
            print("PERIPHERIQUES CONTENANT 'VoiceMeeter':")
            print("=" * 70)
            
            # Rechercher spécifiquement VoiceMeeter
            voicemeeter_devices = [
                d for d in input_devices 
                if 'voicemeeter' in d['name'].lower()
            ]
            
            if voicemeeter_devices:
                for device in voicemeeter_devices:
                    print(f"\n  >>> Index: {device['index']} <<<")
                    print(f"  Nom: {device['name']}")
                    print(f"  Canaux: {device['channels']}")
                    print(f"  Sample Rate: {device['sample_rate']} Hz")
            else:
                print("\n  Aucun peripherique VoiceMeeter trouve.")
                print("  Verifiez que VoiceMeeter est installe et actif.")
        else:
            print("Aucun peripherique d'entree trouve.")
        
        print()
        print("=" * 70)
        print("Pour utiliser un peripherique specifique, utilisez son index")
        print("dans la configuration PyAudio: stream = audio.open(..., input_device_index=X)")
        print("=" * 70)
        
    finally:
        # Nettoyer les ressources
        audio.terminate()


if __name__ == "__main__":
    list_audio_devices()
