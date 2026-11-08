# Photo Sorter Studio

Triez des milliers de photos en quelques touches. Catégories 100 % personnalisables, annulation (Ctrl+Z),
profils, interface HyperOS-inspired (surfaces sombres, cartes arrondies, accents bleu/violet).

*Conçu par Bienvenu K.K · © 2026*

## Lancer

```bash
python -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Tests auto : `pip install -r requirements-dev.txt && pytest` (tests Qt via pytest-qt) · Tests manuels : `MANUAL_TESTS.md`
Qualité : `black .` et `ruff check .` (config dans `pyproject.toml`)
Logs : `photo_sorter.log` dans le dossier de config (5 Mo × 3). DEBUG : `python main.py --debug` ou `PHOTO_SORTER_DEBUG=1`.

## Utilisation
Navigation : *Accueil · Bibliothèque · Trier · Catégories · Réglages*. Cinq zones : barre supérieure (recherche), navigation, zone principale, panneau d'informations, barre de statut.

1. **Choisir un dossier** (et idéalement un dossier destination distinct).
2. **Gérer les catégories** : ajoutez les vôtres (nom, raccourci, couleur), réordonnez, créez des profils.
3. **Commencer** : appuyez sur le raccourci d'une catégorie, la photo est déplacée/copiée et la suivante s'affiche.

| Touche | Action |
|---|---|
| raccourcis définis par vous | trier |
| ← / → ou Espace | précédente / passer |
| Ctrl+Z | annuler (plusieurs niveaux) |
| Échap | retour à l'accueil (puis quitter) |

## Thèmes
HyperOS sombre (référence), HyperOS clair, Hacker, et palettes « verre » (Aurore, Or, Océan). Couleur d'accent modifiable. Palettes dans `theme.py`.

## Configuration
Stockée dans le dossier standard de l'OS (`QStandardPaths.AppConfigLocation`) : `categories.json`,
`settings.json`, sauvegardes `.bak` automatiques. Aucune catégorie n'est codée en dur.

## Fenêtre
Sans cadre, déplacement natif (`startSystemMove`), poignée de redimensionnement en bas à droite.
Si les coins apparaissent noirs (pas de compositeur) : `python main.py --native-frame`.

## Empaquetage
`pip install pyinstaller && python build.py` → exécutable dans `dist/`

## Limites V1
GIF : première image seulement · historique d'annulation non persistant · HEIC via `pillow-heif`.


## Boost 1 (v1.2) — services hors interface
Tout est hors ligne : PySide6 + Pillow + sqlite3 (stdlib). Aucun de ces services ne modifie le workflow de base
(1 photo / 1 touche) ; ils seront branchés à l'interface dans le Boost 2.

| Service | Rôle |
|---|---|
| `services/thumbnail_cache.py` | Miniatures 128/192/256/384 px en cache disque (`~/.cache/PhotoSorterStudio/thumbs/`), régénérées si la source change, éviction LRU (500 Mo par défaut). |
| `services/history_db.py` | Historique SQLite (`history.db`) : annuler / rétablir, lots annulables d'un seul coup, limite de 500 opérations, blocage si un fichier a été déplacé à la main. |
| `services/date_extractor.py` | Date de prise de vue (EXIF original > numérisation > modification > mtime > ctime, ou nom du fichier), orientation, appareil photo, dossiers `AAAA/MM - Mois/AAAA-MM-JJ`. |
| `services/filter_parser.py` | Filtres `:date 2026-08 :portrait -:grand`, OU avec `|`, autocomplétion, ajout d'un filtre par un simple décorateur `@command`. |

Exemples de filtres : `:date >2026-08-15 :paysage` · `:portrait | :carre` · `:camera "canon eos" -:petit` · `:toutes`.
Note : `:nouveau` / `:recent` s'appuient sur la date `ctime` du fichier (approximation de « ajouté »).


## GUI v1.3 — HyperOS
| Touche | Action |
|---|---|
| G | bascule bibliothèque ⇄ espace de tri |
| F11 | mode focus (masque navigation, infos, statut) |
| Ctrl+, | réglages |

`G`, `F11` et `Ctrl+,` sont réservées : elles ne peuvent pas être attribuées à une catégorie.
La bibliothèque utilise un modèle virtuel (`views/library.py`) : seules les miniatures visibles sont chargées, en arrière-plan,
via le cache disque du Boost 1. Le tri par lot depuis la bibliothèque et l'historique persistant dans l'interface arrivent au Boost 2.

## Boost 2 — grille, filtres, historique persistant
**Grille** (`widgets/grid_view.py`) : 4 colonnes par défaut (3 à 6 ou « Auto » dans la bibliothèque ou les réglages), miniatures
128/192/256/384 px chargées à la demande. Clic, Ctrl+clic, Maj+clic, **Ctrl+A** (tout), **Échap** (désélectionner), flèches,
double-clic pour ouvrir en vue unique.

**Tri par lot** : dans la grille, une touche de catégorie trie *toute la sélection* (ou la photo active s'il n'y a pas de
sélection), avec confirmation visuelle (« 15 photos triées vers Famille »). Limite configurable (100 par défaut) avec avertissement.
Un lot = **une seule** entrée d'historique, annulable d'un seul Ctrl+Z.

**Filtres** (`widgets/filter_bar.py`) : barre de commande au-dessus de la grille (`:date 2026-08 :portrait -:grand`, `|` pour OU).
Tab complète la commande, le compteur se met à jour en temps réel, les filtres récents sont mémorisés. Un filtre actif réduit aussi
la file de tri (« Photo 3 / 47 ») et un indicateur le signale. Les métadonnées sont lues en arrière-plan.

**Historique persistant** (`widgets/history_dialog.py`) : toutes les opérations sont dans SQLite ; **Ctrl+Z** annule, **Ctrl+Maj+Z**
rétablit, **Ctrl+H** ouvre la liste (annuler, rétablir, vider) — y compris pour des tris faits lors d'une session précédente.
Si un fichier a été déplacé à la main, l'annulation est bloquée avec un message, sans rien casser.

Touches réservées (non attribuables aux catégories) : Échap, Espace, ←, →, Entrée, Tab, Ctrl+Z, **G, F11, Ctrl+, Ctrl+A, Ctrl+H, Ctrl+Maj+Z**.
Tout est désactivable dans Réglages : touche G, tri par lot, limite, taille du cache (et bouton « Vider le cache »).

## Boost 3 — tri par date et renommage en lot
Principe commun : **aperçu (dry-run) obligatoire**. Le bouton d'action reste grisé tant qu'un aperçu valide n'est pas affiché,
et aucun fichier n'est touché avant le clic de confirmation. Les conflits de noms sont résolus automatiquement (`photo_1.jpg`, `photo_2.jpg`…).
Les deux outils portent sur la sélection de la grille, ou sinon sur toutes les photos restantes de la file (filtre compris).

**Tri par date — Ctrl+R** (`widgets/date_sorter_dialog.py`) : source de la date (EXIF, date de modification, nom du fichier),
structure `AAAA/MM - Mois/AAAA-MM-JJ` ou `AAAA-MM`, rangement dans le dossier source ou destination (noms de mois en français, indépendants de la locale).
Chaque photo est une entrée d'historique **individuelle** (un Ctrl+Z par photo).

**Renommer en lot — Ctrl+B** (`widgets/batch_rename_dialog.py`) : modèle avec `{date} {annee} {mois} {jour} {heure} {camera} {modele} {counter} {original} {ext}`
(`{counter:3}` pour 3 chiffres). Sans extension dans le modèle, celle de l'original est conservée. Tout le renommage forme **un seul lot** : un Ctrl+Z le défait entièrement.

Planification et exécution sont dans `services/batch_ops.py` (aucune dépendance Qt, entièrement testé). Les deux outils sont désactivables dans Réglages.
`Ctrl+R` et `Ctrl+B` sont réservées (non attribuables aux catégories).
