# Phone Dashboard — backend de données

## Test local (Windows 11, PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scripts\run_all.py
```
Les JSON apparaissent dans `docs\data\`.

## Changer de ville
```powershell
python scripts\set_city.py "Perros-Guirec"
python scripts\set_city.py "Saint-Brieuc" --pick 1 --radius 20
python scripts\run_all.py
```
Puis `git commit` + `git push` : le workflow régénère tout.

## Mise en ligne
1. Crée un dépôt GitHub **public** (nécessaire pour Pages gratuit) et pousse ce dossier.
2. Settings > Pages > Source : *Deploy from a branch*, branche `main`, dossier `/docs`.
3. Settings > Actions > General > Workflow permissions : *Read and write*.
4. Onglet Actions > « Collecte des données » > *Run workflow* pour le premier remplissage.

Aucune donnée personnelle dans ce dépôt (il est public). L'agenda Google passera par un
Apps Script dont l'URL ne sera saisie que sur le téléphone.
