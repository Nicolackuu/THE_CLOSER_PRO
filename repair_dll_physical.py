"""
THE CLOSER PRO v0.25 - Physical DLL Repair Script
Copie physiquement les DLLs CUDA manquantes à la racine du projet.
Solution de contournement pour l'échec de l'injection PATH.

Author: THE CLOSER PRO Team
Version: 0.25 (Elite Edition)
"""

import os
import sys
import shutil
from pathlib import Path


def find_dll_files():
    """
    Localise les fichiers DLL CUDA dans le venv.
    
    Returns:
        Dict avec les chemins des DLLs trouvées
    """
    print("="*70)
    print("CUDA DLL PHYSICAL REPAIR - THE CLOSER PRO v0.25")
    print("="*70)
    print()
    
    # DLLs critiques à trouver (version 8 de cuDNN - compatible faster-whisper)
    required_dlls = [
        "cudnn_ops_infer64_8.dll",
        "cudnn_cnn_infer64_8.dll",
        "cudnn64_8.dll",
        "cublas64_11.dll",
        "cublasLt64_11.dll"
    ]
    
    # Chemins de recherche dans le venv
    venv_root = Path("venv")
    
    if not venv_root.exists():
        print("❌ ERREUR: Dossier venv non trouvé!")
        return {}
    
    search_paths = [
        venv_root / "Lib" / "site-packages" / "nvidia" / "cudnn" / "bin",
        venv_root / "Lib" / "site-packages" / "nvidia" / "cublas" / "bin",
        venv_root / "Lib" / "site-packages" / "nvidia",
        venv_root / "Lib" / "site-packages" / "torch" / "lib",
    ]
    
    found_dlls = {}
    
    print("🔍 Recherche des DLLs CUDA dans le venv...\n")
    
    for dll_name in required_dlls:
        found = False
        
        for search_path in search_paths:
            if not search_path.exists():
                continue
            
            # Recherche récursive
            for dll_file in search_path.rglob(dll_name):
                found_dlls[dll_name] = dll_file
                print(f"✅ Trouvé: {dll_name}")
                print(f"   → {dll_file}")
                found = True
                break
            
            if found:
                break
        
        if not found:
            print(f"⚠️  Non trouvé: {dll_name}")
    
    print()
    return found_dlls


def copy_dlls_to_root(dll_paths):
    """
    Copie les DLLs à la racine du projet.
    
    Args:
        dll_paths: Dict avec les chemins des DLLs
    
    Returns:
        Nombre de DLLs copiées
    """
    if not dll_paths:
        print("❌ Aucune DLL à copier!")
        return 0
    
    project_root = Path.cwd()
    copied_count = 0
    
    print("📋 Copie des DLLs à la racine du projet...\n")
    
    for dll_name, dll_path in dll_paths.items():
        try:
            destination = project_root / dll_name
            
            # Copier le fichier
            shutil.copy2(dll_path, destination)
            
            # Vérifier que la copie a réussi
            if destination.exists():
                size_mb = destination.stat().st_size / (1024 * 1024)
                print(f"✅ Copié: {dll_name} ({size_mb:.2f} MB)")
                print(f"   → {destination}")
                copied_count += 1
            else:
                print(f"❌ Échec de copie: {dll_name}")
        
        except Exception as e:
            print(f"❌ Erreur lors de la copie de {dll_name}: {e}")
    
    print()
    return copied_count


def verify_dlls_in_root():
    """
    Vérifie que les DLLs sont bien présentes à la racine.
    
    Returns:
        True si toutes les DLLs critiques sont présentes
    """
    critical_dlls = [
        "cudnn_ops_infer64_8.dll",
        "cudnn_cnn_infer64_8.dll",
        "cudnn64_8.dll"
    ]
    
    project_root = Path.cwd()
    
    print("🔍 Vérification des DLLs à la racine...\n")
    
    all_present = True
    for dll_name in critical_dlls:
        dll_path = project_root / dll_name
        
        if dll_path.exists():
            size_mb = dll_path.stat().st_size / (1024 * 1024)
            print(f"✅ {dll_name} présent ({size_mb:.2f} MB)")
        else:
            print(f"❌ {dll_name} MANQUANT")
            all_present = False
    
    print()
    return all_present


def main():
    """Point d'entrée principal."""
    try:
        # Étape 1: Trouver les DLLs
        dll_paths = find_dll_files()
        
        if not dll_paths:
            print("="*70)
            print("❌ ÉCHEC: Aucune DLL CUDA trouvée dans le venv")
            print("="*70)
            print()
            print("SOLUTIONS POSSIBLES:")
            print("1. Réinstallez torch avec CUDA:")
            print("   pip uninstall torch")
            print("   pip install torch --index-url https://download.pytorch.org/whl/cu121")
            print()
            print("2. Installez les packages NVIDIA:")
            print("   pip install nvidia-cudnn-cu11")
            print("   pip install nvidia-cublas-cu11")
            print()
            return False
        
        # Étape 2: Copier les DLLs
        copied_count = copy_dlls_to_root(dll_paths)
        
        if copied_count == 0:
            print("="*70)
            print("❌ ÉCHEC: Aucune DLL n'a pu être copiée")
            print("="*70)
            return False
        
        # Étape 3: Vérifier
        success = verify_dlls_in_root()
        
        # Résumé final
        print("="*70)
        if success:
            print("✅ SUCCÈS: Réparation DLL terminée!")
            print("="*70)
            print()
            print(f"📁 {copied_count} DLL(s) copiée(s) à la racine du projet")
            print()
            print("🚀 PROCHAINE ÉTAPE:")
            print("   Relancez: python main_v25.py")
            print()
            print("💡 NOTE:")
            print("   Les DLLs sont maintenant dans le répertoire courant.")
            print("   Windows les chargera automatiquement au démarrage.")
            print()
        else:
            print("⚠️  ATTENTION: Réparation partielle")
            print("="*70)
            print()
            print(f"📁 {copied_count} DLL(s) copiée(s), mais certaines manquent")
            print()
        
        return success
        
    except Exception as e:
        print()
        print("="*70)
        print(f"❌ ERREUR FATALE: {e}")
        print("="*70)
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    
    if success:
        print("✅ Script terminé avec succès")
        sys.exit(0)
    else:
        print("❌ Script terminé avec des erreurs")
        sys.exit(1)
