"""
THE CLOSER PRO v0.25 - CUDA DLL Auto-Fixer
Résout dynamiquement l'erreur "Could not locate cudnn_ops_infer64_8.dll".
Scanne le venv et injecte les chemins DLL au runtime.

Author: THE CLOSER PRO Team
Version: 0.25 (Elite Edition)
"""

import os
import sys
import logging
from pathlib import Path
from typing import List, Optional


class CUDADLLFixer:
    """
    Fixe automatiquement les erreurs de DLL CUDA manquantes.
    Scanne le venv et ajoute les chemins au PATH système.
    """
    
    # DLLs CUDA critiques
    REQUIRED_DLLS = [
        "cudnn_ops_infer64_8.dll",
        "cudnn_cnn_infer64_8.dll",
        "cudnn64_8.dll",
        "cublas64_11.dll",
        "cublasLt64_11.dll"
    ]
    
    def __init__(self):
        """Initialise le fixer."""
        self.logger = logging.getLogger(__name__)
        self.venv_root = self._find_venv_root()
        self.dll_paths: List[Path] = []
    
    def _find_venv_root(self) -> Optional[Path]:
        """
        Trouve la racine du venv actuel.
        
        Returns:
            Path du venv ou None
        """
        # Vérifier si on est dans un venv
        if hasattr(sys, 'real_prefix') or (
            hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
        ):
            return Path(sys.prefix)
        
        # Chercher le dossier venv dans le répertoire courant
        cwd = Path.cwd()
        venv_path = cwd / 'venv'
        if venv_path.exists():
            return venv_path
        
        return None
    
    def scan_for_dlls(self) -> List[Path]:
        """
        Scanne le venv pour trouver les DLLs CUDA.
        
        Returns:
            Liste des chemins contenant des DLLs CUDA
        """
        if not self.venv_root:
            self.logger.warning("No venv found, cannot scan for DLLs")
            return []
        
        dll_directories = set()
        
        # Chemins typiques dans un venv Windows
        search_paths = [
            self.venv_root / "Lib" / "site-packages",
            self.venv_root / "Scripts",
            self.venv_root / "DLLs"
        ]
        
        # Chemins spécifiques pour torch/nvidia
        torch_paths = [
            self.venv_root / "Lib" / "site-packages" / "torch" / "lib",
            self.venv_root / "Lib" / "site-packages" / "nvidia" / "cudnn" / "lib",
            self.venv_root / "Lib" / "site-packages" / "nvidia" / "cublas" / "lib",
        ]
        search_paths.extend(torch_paths)
        
        for search_path in search_paths:
            if not search_path.exists():
                continue
            
            # Chercher récursivement les DLLs
            for dll_name in self.REQUIRED_DLLS:
                for dll_file in search_path.rglob(dll_name):
                    dll_dir = dll_file.parent
                    dll_directories.add(dll_dir)
                    self.logger.info(f"Found {dll_name} in {dll_dir}")
        
        self.dll_paths = list(dll_directories)
        return self.dll_paths
    
    def inject_dll_paths(self) -> bool:
        """
        Injecte les chemins DLL dans le PATH système.
        
        Returns:
            True si au moins un chemin a été ajouté
        """
        if not self.dll_paths:
            self.scan_for_dlls()
        
        if not self.dll_paths:
            self.logger.warning("No CUDA DLL paths found to inject")
            return False
        
        # Récupérer le PATH actuel
        current_path = os.environ.get('PATH', '')
        path_entries = current_path.split(os.pathsep)
        
        added_count = 0
        for dll_path in self.dll_paths:
            dll_path_str = str(dll_path)
            
            # Vérifier si déjà dans le PATH
            if dll_path_str not in path_entries:
                # Ajouter au début du PATH (priorité)
                path_entries.insert(0, dll_path_str)
                added_count += 1
                self.logger.info(f"Injected DLL path: {dll_path_str}")
        
        if added_count > 0:
            # Mettre à jour le PATH
            os.environ['PATH'] = os.pathsep.join(path_entries)
            self.logger.info(f"Successfully injected {added_count} DLL paths into PATH")
            return True
        else:
            self.logger.info("All DLL paths already in PATH")
            return False
    
    def verify_dlls(self) -> dict:
        """
        Vérifie quelles DLLs sont accessibles.
        
        Returns:
            Dict avec le status de chaque DLL
        """
        status = {}
        
        for dll_name in self.REQUIRED_DLLS:
            found = False
            
            # Chercher dans les chemins DLL connus
            for dll_path in self.dll_paths:
                dll_file = dll_path / dll_name
                if dll_file.exists():
                    status[dll_name] = {
                        'found': True,
                        'path': str(dll_file)
                    }
                    found = True
                    break
            
            if not found:
                status[dll_name] = {
                    'found': False,
                    'path': None
                }
        
        return status
    
    def auto_fix(self) -> bool:
        """
        Applique automatiquement tous les fixes CUDA.
        
        Returns:
            True si le fix a réussi
        """
        self.logger.info("Starting CUDA DLL auto-fix...")
        
        # Scanner les DLLs
        dll_paths = self.scan_for_dlls()
        
        if not dll_paths:
            self.logger.error("No CUDA DLL paths found in venv")
            return False
        
        # Injecter dans le PATH
        injected = self.inject_dll_paths()
        
        # Vérifier le status
        status = self.verify_dlls()
        
        # Compter les DLLs trouvées
        found_count = sum(1 for dll in status.values() if dll['found'])
        total_count = len(self.REQUIRED_DLLS)
        
        self.logger.info(f"CUDA DLL Status: {found_count}/{total_count} found")
        
        # Afficher les DLLs manquantes
        missing = [name for name, info in status.items() if not info['found']]
        if missing:
            self.logger.warning(f"Missing DLLs: {', '.join(missing)}")
        
        return found_count > 0
    
    def print_report(self):
        """Affiche un rapport détaillé."""
        print("\n" + "="*70)
        print("CUDA DLL AUTO-FIXER REPORT")
        print("="*70 + "\n")
        
        if self.venv_root:
            print(f"✅ VEnv Root: {self.venv_root}\n")
        else:
            print("❌ No VEnv detected\n")
        
        if self.dll_paths:
            print(f"📁 DLL Paths Found: {len(self.dll_paths)}")
            for path in self.dll_paths:
                print(f"   - {path}")
            print()
        
        status = self.verify_dlls()
        
        print("🔍 DLL Status:")
        for dll_name, info in status.items():
            if info['found']:
                print(f"   ✅ {dll_name}")
                print(f"      → {info['path']}")
            else:
                print(f"   ❌ {dll_name} (NOT FOUND)")
        
        print("\n" + "="*70 + "\n")


# Singleton instance
_fixer_instance: Optional[CUDADLLFixer] = None

def get_cuda_fixer() -> CUDADLLFixer:
    """Retourne l'instance singleton du fixer."""
    global _fixer_instance
    if _fixer_instance is None:
        _fixer_instance = CUDADLLFixer()
    return _fixer_instance


def apply_cuda_fix():
    """
    Applique le fix CUDA automatiquement.
    À appeler au démarrage de l'application.
    """
    fixer = get_cuda_fixer()
    success = fixer.auto_fix()
    
    if not success:
        logging.warning(
            "CUDA DLL auto-fix did not find all required DLLs. "
            "GPU acceleration may not work properly."
        )
    
    return success


if __name__ == "__main__":
    # Test du fixer
    logging.basicConfig(level=logging.INFO)
    
    fixer = get_cuda_fixer()
    fixer.auto_fix()
    fixer.print_report()
