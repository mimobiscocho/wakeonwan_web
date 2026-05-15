# Machine Control

Interface web pour allumer, éteindre, mettre en veille et redémarrer des machines à distance, avec gestion des utilisateurs et des rôles.

## Fonctionnalités

- Wake-on-LAN pour allumer les machines
- Commandes à distance : veille, arrêt, redémarrage (via agent HTTP local)
- Authentification par session avec Flask-Login
- Rôles : `admin`, `manager`, `viewer`
- Accès par machine configurable par utilisateur

## Stack

- Backend : Python / Flask
- Frontend : HTML/JS (dans `web/`)

## Installation

```bash
cd api
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Copier `.env.example` en `.env` et renseigner les variables :

```bash
cp .env.example .env
```

## Lancement

```bash
SECRET_KEY=changeme python api/main.py
# ou avec .env
python api/main.py
```

L'interface est disponible sur `http://localhost:5000`.

## Compte par défaut

Au premier démarrage, un compte `admin` / `admin` est créé automatiquement — **changer le mot de passe immédiatement**.

## Structure

```
api/        # Serveur Flask (API + auth)
shared/     # Utilitaires partagés (ping, WoL)
web/        # Frontend statique
logs/       # Logs des actions
```
