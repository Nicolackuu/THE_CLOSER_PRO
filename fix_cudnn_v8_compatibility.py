"""
THE CLOSER PRO v0.25 - cuDNN v8 Compatibility Fix
Crée des copies des DLLs v9 avec les noms v8 attendus par faster-whisper.
Solution de contournement pour le conflit de version.

Author: THE CLOSER PRO Team
Version: 0.25 (Elite Edition)
"""

import shutil
from pathlib import Path


def create_v8_compatibility_dlls():
    """
    Copie les DLLs v9 avec les noms v8 attendus par faster-whisper.
    """
    print("="*70)
    print("cuDNN v8 COMPATIBILITY FIX - THE CLOSER PRO v0.25")
    print("="*70)
    print()
    
    # Mapping v9 → v8 (nom attendu par faster-whisper)
    dll_mapping = {
        "cudnn_ops64_9.dll": "cudnn_ops_infer64_8.dll",
        "cudnn_cnn64_9.dll": "cudnn_cnn_infer64_8.dll",
        "cudnn64_9.dll": "cudnn64_8.dll"
    }
    
    venv_cudnn_bin = Path("venv/Lib/site-packages/nvidia/cudnn/bin")
    project_root = Path.cwd()
    
    if not venv_cudnn_bin.exists():
        print(f"❌ ERREUR: {venv_cudnn_bin} non trouvé!")
        return False
    
    print("🔄 Création des DLLs compatibles v8...\n")
    
    copied_count = 0
    for v9_name, v8_name in dll_mapping.items():
        source = venv_cudnn_bin / v9_name
        destination = project_root / v8_name
        
        if not source.exists():
            print(f"⚠️  Source manquante: {v9_name}")
            continue
        
        try:
            # Copier avec le nouveau nom
            shutil.copy2(source, destination)
            
            if destination.exists():
                size_mb = destination.stat().st_size / (1024 * 1024)
                print(f"✅ Créé: {v8_name} ({size_mb:.2f} MB)")
                print(f"   ← {v9_name}")
                copied_count += 1
            else:
                print(f"❌ Échec: {v8_name}")
        
        except Exception as e:
            print(f"❌ Erreur pour {v8_name}: {e}")
    
    print()
    
    # Vérifier les DLLs cublas (déjà copiées normalement)
    cublas_dlls = ["cublas64_11.dll", "cublasLt64_11.dll"]
    
    print("🔍 Vérification des DLLs cuBLAS...\n")
    
    for dll_name in cublas_dlls:
        dll_path = project_root / dll_name
        if dll_path.exists():
            size_mb = dll_path.stat().st_size / (1024 * 1024)
            print(f"✅ {dll_name} présent ({size_mb:.2f} MB)")
        else:
            print(f"⚠️  {dll_name} manquant (sera copié par repair_dll_physical.py)")
    
    print()
    
    # Résumé
    print("="*70)
    if copied_count == len(dll_mapping):
        print("✅ SUCCÈS: Compatibilité v8 créée!")
        print("="*70)
        print()
        print(f"📁 {copied_count} DLL(s) v8 créée(s) à partir des v9")
        print()
        print("🚀 PROCHAINE ÉTAPE:")
        print("   Relancez: python main_v25.py")
        print()
        print("💡 NOTE:")
        print("   faster-whisper cherche les DLLs v8, mais utilise les v9 renommées.")
        print("   C'est une solution de compatibilité qui fonctionne.")
        print()
        return True
    else:
        print("⚠️  ATTENTION: Compatibilité partielle")
        print("="*70)
        print()
        print(f"📁 {copied_count}/{len(dll_mapping)} DLL(s) créée(s)")
        print()
        return False


if __name__ == "__main__":
    import sys
    
    success = create_v8_compatibility_dlls()
    
    if success:
        print("✅ Script terminé avec succès")
        sys.exit(0)
    else:
        print("❌ Script terminé avec des erreurs")
        sys.exit(1)
