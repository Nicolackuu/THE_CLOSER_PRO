# THE CLOSER PRO v1.0.0 (Genesis)

**Système de transcription temps réel pour sessions de Closing High-Ticket**

Architecture asynchrone industrielle avec zéro perte de paquets audio et élimination intelligente des hallucinations.

---

## 🎯 OBJECTIF

Transcrire en temps réel vos appels de closing avec une précision maximale, en français, sans hallucinations parasites (type "Amara.org", "Abonnez-vous", etc.).

---

## 🏗️ ARCHITECTURE

```
THE_CLOSER_PRO/
│
├── core/                          # Modules principaux
│   ├── audio_streamer.py         # Capture audio continue (threading + queue)
│   ├── transcriber_new.py        # Faster-Whisper Singleton (inférence GPU)
│   └── processor.py              # Nettoyage anti-hallucination (fuzzy matching)
│
├── config/                        # Configuration centralisée
│   └── manager.py                # Gestionnaire de config (Singleton)
│
├── utils/                         # Utilitaires
│
├── main.py                        # Orchestrateur principal
├── requirements.txt               # Dépendances Python
└── README.md                      # Ce fichier
```

---

## 💻 STACK TECHNIQUE

### Matériel
- **CPU**: AMD Ryzen 7 5800H (8 Cores)
- **GPU**: NVIDIA RTX 3070 Laptop (8GB VRAM)
- **Audio**: VoiceMeeter Virtual B1 (Device ID 33)

### Logiciel
- **Modèle IA**: Faster-Whisper `distil-large-v3`
- **Compute**: `float16` (Tensor Cores RTX)
- **Backend**: CTranslate2 + CUDA 12.1
- **Audio**: SoundDevice (PortAudio)
- **Processing**: RapidFuzz (fuzzy matching)

---

## 🚀 INSTALLATION

### Prérequis
- Python 3.10 ou 3.11
- CUDA 12.1+ installé
- Driver NVIDIA 535.xx ou supérieur
- VoiceMeeter installé et configuré

### Étape 1: Cloner/Télécharger le projet
```bash
cd C:\Users\Nicolak\Desktop\THE_CLOSER_PRO
```

### Étape 2: Créer un environnement virtuel (recommandé)
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Étape 3: Installer PyTorch avec CUDA 12.1
```powershell
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### Étape 4: Installer les autres dépendances
```powershell
pip install -r requirements.txt
```

### Étape 5: Vérifier l'installation CUDA
```powershell
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0)}')"
```

Vous devriez voir:
```
CUDA: True
GPU: NVIDIA GeForce RTX 3070 Laptop GPU
```

---

## ⚙️ CONFIGURATION

### Identifier votre Device Audio

Avant le premier lancement, identifiez l'ID de VoiceMeeter Virtual B1:

```powershell
python -m core.audio_streamer
```

Cherchez dans la liste:
```
[33] VoiceMeeter Virtual B1
    Type: INPUT
    Channels: IN=2, OUT=0
    Sample Rate: 48000.0 Hz
```

Si l'ID n'est **pas 33**, modifiez `config/manager.py`:

```python
@dataclass
class AudioConfig:
    device_id: int = 33  # <-- Changez ici
```

### Personnalisation

Éditez `config/manager.py` pour ajuster:

- **Audio**: `device_id`, `sample_rate`, `silence_threshold`
- **Transcription**: `model_name`, `compute_type`, `beam_size`, `initial_prompt`
- **Processing**: `hallucination_patterns`, `fuzzy_threshold`
- **System**: `log_level`, `output_format`, `output_file`

---

## 🎬 UTILISATION

### Lancement Standard

```powershell
python main.py
```

Vous verrez:
```
╔═══════════════════════════════════════════════════════════════════╗
║                    THE CLOSER PRO - v1.0.0                        ║
║           Transcription Temps Réel pour Closing High-Ticket      ║
╚═══════════════════════════════════════════════════════════════════╝

[INFO] Démarrage du transcriber...
[INFO] Model loaded successfully in VRAM
[INFO] SYSTÈME OPÉRATIONNEL - PRÊT POUR LE CLOSING
[INFO] Parlez maintenant... (Ctrl+C pour arrêter)
```

### Arrêt Propre

Appuyez sur **Ctrl+C** pour arrêter proprement le système.

Les statistiques de session s'afficheront:
```
=== STATISTIQUES DE SESSION ===
Durée: 0:15:32
Segments transcrits: 127
Segments valides: 119
Taux de validité: 93.7%
Perte audio: 0.00%
VRAM utilisée: 2.34 GB
```

---

## 📊 FONCTIONNALITÉS CLÉS

### 1. Capture Audio Sans Perte
- **Threading**: Callback haute priorité pour la capture
- **Queue Thread-Safe**: Buffer FIFO découplant capture/traitement
- **Monitoring**: Statistiques en temps réel (chunks dropped, loss rate)

### 2. Transcription GPU Optimisée
- **Singleton Pattern**: Une seule instance du modèle en VRAM
- **Thread Worker**: Inférence déportée (non-bloquante)
- **VRAM Management**: Nettoyage automatique du cache GPU

### 3. Anti-Hallucination Intelligent
- **Fuzzy Matching**: Détection avec RapidFuzz (seuil 85%)
- **Liste Noire**: Patterns prédéfinis (Amara.org, Abonnez-vous, etc.)
- **Validation**: Filtrage des segments vides ou trop courts

### 4. Prompt de Conditionnement
Le système force le français avec un prompt métier:
```
"Session de Closing High-Ticket. Analyse des besoins et traitement d'objections.
Terminologie : Pipeline, Deal, Setter, Qualif, Go-High-Level, Prospect, Objection,
Close, Upsell, Downsell, Framework, ROI, Investissement."
```

---

## 🔧 TROUBLESHOOTING

### Erreur: "CUDA out of memory"

**Solution 1**: Réduire la précision
```python
# config/manager.py
compute_type: str = "int8"  # Au lieu de "float16"
```

**Solution 2**: Réduire le beam size
```python
beam_size: int = 3  # Au lieu de 5
```

### Erreur: "Device ID 33 not found"

Relancez l'identification:
```powershell
python -m core.audio_streamer
```

Modifiez `device_id` dans `config/manager.py`.

### Transcription en anglais malgré `language="fr"`

**Cause**: Buffer audio trop court, pas assez de contexte.

**Solution**: Augmenter la durée du buffer dans `main.py`:
```python
self._target_buffer_duration = 5.0  # Au lieu de 3.0
```

### Hallucinations non détectées

Ajoutez vos patterns dans `config/manager.py`:
```python
hallucination_patterns: list = [
    "Amara.org",
    "Abonnez-vous",
    "Votre pattern ici",  # <-- Ajoutez ici
]
```

---

## 📈 OPTIMISATIONS FUTURES

- [ ] Diarisation (séparation locuteurs MOI/CLIENT)
- [ ] Détection d'émotions (tonalité, stress)
- [ ] Export JSON structuré (timestamps, confiance)
- [ ] Interface Web (Flask/FastAPI)
- [ ] Intégration CRM (Go-High-Level, HubSpot)

---

## 📝 NOTES TECHNIQUES

### Pourquoi Faster-Whisper ?
- **3-4x plus rapide** que Whisper OpenAI
- **Consommation VRAM réduite** (~2GB vs ~5GB)
- **CTranslate2 backend** optimisé pour production

### Pourquoi distil-large-v3 ?
- **Meilleur compromis** vitesse/qualité
- **Distillation** du modèle large-v3 (performances similaires)
- **Taille réduite** (~1.5GB vs ~3GB)

### Pourquoi float16 ?
- **Tensor Cores RTX** exploités à 100%
- **2x plus rapide** que float32
- **Qualité identique** pour la transcription

---

## 🤝 SUPPORT

Pour toute question ou problème:
1. Vérifiez les logs dans la console
2. Consultez la section Troubleshooting
3. Vérifiez la configuration dans `config/manager.py`

---

## 📜 LICENSE

Propriétaire - THE CLOSER PRO Team

---

**Version**: 1.0.0 (Genesis)  
**Date**: Janvier 2025  
**Auteur**: THE CLOSER PRO Team
