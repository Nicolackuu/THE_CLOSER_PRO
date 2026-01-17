"""
THE CLOSER PRO v0.25 - Complete GPU Dependencies Fix
Copie TOUTES les DLLs nécessaires : cuDNN v9→v8 + zlib + cuBLAS
Résolution finale du problème "Unknown dll missing".

Author: THE CLOSER PRO Team
Version: 0.25 (Elite Edition)
"""

import shutil
from pathlib import Path


def find_and_copy_all_dlls():
    """
    Trouve et copie toutes les DLLs GPU nécessaires à la racine.
    """
    print("="*70)
    print("COMPLETE GPU DEPENDENCIES FIX - THE CLOSER PRO v0.25")
    print("="*70)
    print()
    
    venv_root = Path("venv")
    project_root = Path.cwd()
    
    if not venv_root.exists():
        print("❌ ERREUR: Dossier venv non trouvé!")
        return False
    
    # 1. cuDNN DLLs (v9 → v8 renaming)
    print("🔍 Recherche des DLLs cuDNN...\n")
    
    cudnn_bin = venv_root / "Lib" / "site-packages" / "nvidia" / "cudnn" / "bin"
    cudnn_mapping = {
        "cudnn_ops64_9.dll": "cudnn_ops_infer64_8.dll",
        "cudnn_cnn64_9.dll": "cudnn_cnn_infer64_8.dll",
        "cudnn64_9.dll": "cudnn64_8.dll"
    }
    
    cudnn_copied = 0
    for v9_name, v8_name in cudnn_mapping.items():
        source = cudnn_bin / v9_name
        destination = project_root / v8_name
        
        if source.exists():
            try:
                shutil.copy2(source, destination)
                size_mb = destination.stat().st_size / (1024 * 1024)
                print(f"✅ {v8_name} ({size_mb:.2f} MB)")
                print(f"   ← {v9_name}")
                cudnn_copied += 1
            except Exception as e:
                print(f"❌ Erreur: {v8_name} - {e}")
        else:
            print(f"⚠️  Source manquante: {v9_name}")
    
    print()
    
    # 2. cuBLAS DLLs
    print("🔍 Recherche des DLLs cuBLAS...\n")
    
    cublas_bin = venv_root / "Lib" / "site-packages" / "nvidia" / "cublas" / "bin"
    cublas_dlls = ["cublas64_11.dll", "cublasLt64_11.dll"]
    
    cublas_copied = 0
    for dll_name in cublas_dlls:
        source = cublas_bin / dll_name
        destination = project_root / dll_name
        
        if source.exists():
            try:
                shutil.copy2(source, destination)
                size_mb = destination.stat().st_size / (1024 * 1024)
                print(f"✅ {dll_name} ({size_mb:.2f} MB)")
                cublas_copied += 1
            except Exception as e:
                print(f"❌ Erreur: {dll_name} - {e}")
        else:
            print(f"⚠️  Source manquante: {dll_name}")
    
    print()
    
    # 3. zlib DLL (zlibwapi.dll ou zlib1.dll)
    print("🔍 Recherche de zlib...\n")
    
    # Chercher zlib dans plusieurs emplacements
    zlib_search_paths = [
        venv_root / "Lib" / "site-packages" / "nvidia" / "cudnn" / "bin",
        venv_root / "Lib" / "site-packages" / "av.libs",
        venv_root / "DLLs",
    ]
    
    zlib_found = False
    zlib_source = None
    
    # Chercher zlibwapi.dll ou zlib1.dll
    for search_path in zlib_search_paths:
        if not search_path.exists():
            continue
        
        # Chercher zlibwapi.dll
        zlibwapi = search_path / "zlibwapi.dll"
        if zlibwapi.exists():
            zlib_source = zlibwapi
            zlib_found = True
            break
        
        # Chercher zlib1.dll ou zlib avec pattern
        for dll_file in search_path.glob("zlib*.dll"):
            zlib_source = dll_file
            zlib_found = True
            break
        
        if zlib_found:
            break
    
    zlib_copied = 0
    if zlib_found and zlib_source:
        # Copier comme zlibwapi.dll (nom attendu par cuDNN)
        destination = project_root / "zlibwapi.dll"
        try:
            shutil.copy2(zlib_source, destination)
            size_mb = destination.stat().st_size / (1024 * 1024)
            print(f"✅ zlibwapi.dll ({size_mb:.2f} MB)")
            print(f"   ← {zlib_source.name}")
            zlib_copied = 1
        except Exception as e:
            print(f"❌ Erreur: zlibwapi.dll - {e}")
    else:
        print("⚠️  zlib non trouvé dans le venv")
        print("💡 Tentative de téléchargement depuis torch...")
        
        # Chercher dans torch
        torch_lib = venv_root / "Lib" / "site-packages" / "torch" / "lib"
        if torch_lib.exists():
            for dll_file in torch_lib.glob("*zlib*.dll"):
                destination = project_root / "zlibwapi.dll"
                try:
                    shutil.copy2(dll_file, destination)
                    size_mb = destination.stat().st_size / (1024 * 1024)
                    print(f"✅ zlibwapi.dll ({size_mb:.2f} MB)")
                    print(f"   ← {dll_file.name} (from torch)")
                    zlib_copied = 1
                    break
                except Exception as e:
                    print(f"❌ Erreur: {e}")
    
    print()
    
    # 4. Vérification finale
    print("🔍 Vérification finale...\n")
    
    required_dlls = [
        "cudnn_ops_infer64_8.dll",
        "cudnn_cnn_infer64_8.dll",
        "cudnn64_8.dll",
        "cublas64_11.dll",
        "cublasLt64_11.dll",
        "zlibwapi.dll"
    ]
    
    all_present = True
    total_size = 0
    
    for dll_name in required_dlls:
        dll_path = project_root / dll_name
        if dll_path.exists():
            size_mb = dll_path.stat().st_size / (1024 * 1024)
            total_size += size_mb
            print(f"✅ {dll_name} ({size_mb:.2f} MB)")
        else:
            print(f"❌ {dll_name} MANQUANT")
            all_present = False
    
    print()
    print(f"📊 Taille totale: {total_size:.2f} MB")
    print()
    
    # Résumé
    print("="*70)
    if all_present:
        print("✅ SUCCÈS: Toutes les dépendances GPU sont présentes!")
        print("="*70)
        print()
        print(f"📁 {len(required_dlls)} DLL(s) copiée(s) à la racine")
        print()
        print("🚀 PROCHAINE ÉTAPE:")
        print("   Relancez: python main_v25.py")
        print()
        print("💡 NOTE:")
        print("   - cuDNN v9 renommée en v8 pour compatibilité faster-whisper")
        print("   - zlibwapi.dll ajoutée pour résoudre 'Unknown dll missing'")
        print("   - Toutes les DLLs chargées depuis le répertoire courant")
        print()
        return True
    else:
        print("⚠️  ATTENTION: Certaines DLLs manquent encore")
        print("="*70)
        print()
        print("SOLUTIONS POSSIBLES:")
        print()
        print("1. Pour zlib manquant:")
        print("   - Téléchargez zlibwapi.dll depuis:")
        print("     https://www.winimage.com/zLibDll/zlib123dllx64.zip")
        print("   - Extrayez zlibwapi.dll à la racine du projet")
        print()
        print("2. Pour cuDNN manquant:")
        print("   - Réinstallez: pip install nvidia-cudnn-cu11==8.9.4.25")
        print("   - Relancez ce script")
        print()
        return False


if __name__ == "__main__":
    import sys
    
    success = find_and_copy_all_dlls()
    
    if success:
        print("✅ Script terminé avec succès")
        sys.exit(0)
    else:
        print("❌ Script terminé avec des avertissements")
        sys.exit(1)
