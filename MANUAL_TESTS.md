# Checklist de tests manuels

Cochez au fur et à mesure (lancer avec `python main.py --debug` pour des logs détaillés).

- [ ] Lancement
- [ ] Création de configuration (fichiers `categories.json` / `settings.json` apparus)
- [ ] Ajout de catégorie
- [ ] Suppression de catégorie
- [ ] Renommage
- [ ] Changement de raccourci
- [ ] Détection de doublon de raccourci
- [ ] Refus des raccourcis réservés (Échap, Espace, ←, →, Entrée, Tab, Ctrl+Z)
- [ ] Sélection du dossier
- [ ] Affichage d'une photo
- [ ] Photo suivante
- [ ] Photo précédente
- [ ] Passer une photo
- [ ] Tri avec bouton
- [ ] Tri avec clavier
- [ ] Création des dossiers
- [ ] Doublons (`photo_1.jpg`, …)
- [ ] Ctrl+Z (plusieurs fois de suite)
- [ ] Photo corrompue (bandeau d'erreur, l'app continue)
- [ ] Dossier vide
- [ ] Gros dossier (milliers de photos, interface fluide)
- [ ] Redimensionnement de la fenêtre (bords et coins)
- [ ] Photos portrait
- [ ] Photos paysage
- [ ] Fermeture de l'application
- [ ] Les touches de tri ne déclenchent rien quand « Gérer les catégories » est ouvert
- [ ] Les 4 thèmes

## GUI v1.3 (HyperOS) — à vérifier
- [ ] Thème HyperOS sombre par défaut ; bascule clair / hacker / verre dans Réglages
- [ ] Couleur d'accent personnalisée et « Par défaut »
- [ ] Accueil : dossier source, destination, dossiers récents, dernières sessions
- [ ] Bibliothèque : grille fluide sur un gros dossier, liste, tailles S/M/L/XL, tri nom/date/taille
- [ ] Recherche dans la barre du haut (filtre la bibliothèque)
- [ ] Sélection multiple (Ctrl / Maj + clic), double-clic → espace de tri
- [ ] Touche G : bascule bibliothèque ⇄ tri ; F11 : mode focus ; Échap : retour
- [ ] Panneau d'informations (dimensions, taille, date, appareil) — masquable dans Réglages
- [ ] Barre de statut : progression et compteur
- [ ] Animations désactivables ; l'interface reste utilisable sans effets

## Boost 2 — grille, filtres, historique
- [ ] Grille 4 colonnes par défaut ; passer à 3 / 5 / 6 / Auto ; redimensionner la fenêtre
- [ ] Clic, Ctrl+clic, Maj+clic, Ctrl+A, Échap (désélectionne avant de quitter la vue)
- [ ] Touche de catégorie avec 15 photos sélectionnées → confirmation « 15 photos triées vers … »
- [ ] Touche de catégorie sans sélection → la photo active est triée
- [ ] Sélection > limite (Réglages) → avertissement, rien n'est déplacé
- [ ] Ctrl+Z après un tri par lot → toutes les photos reviennent d'un coup ; Ctrl+Maj+Z les remet
- [ ] Fermer puis relancer l'application → Ctrl+Z annule encore le dernier tri
- [ ] Ctrl+H : liste de l'historique (annuler, rétablir, vider)
- [ ] Déplacer à la main une photo triée, puis Ctrl+Z → message d'avertissement, pas de plantage
- [ ] Filtre `:portrait`, `:date 2026-08`, `:camera canon`, `:portrait | :carre`, `-:grand`, `:toutes`
- [ ] Tab complète la commande ; filtre invalide → message rouge, la file ne change pas
- [ ] Filtre actif → « Photo 3 / 47 » dans l'espace de tri + indicateur
- [ ] Filtres récents dans la liste déroulante
- [ ] Désactiver la touche G / le tri par lot dans Réglages → plus d'effet
- [ ] « Vider le cache » ; taille max du cache

## Boost 3 — tri par date et renommage
- [ ] Ctrl+R (ou bouton « Trier par date ») : l'aperçu s'affiche, « Trier » est grisé pendant le calcul
- [ ] Changer la source de la date / la structure / la destination → l'aperçu se recalcule, « Trier » se regrise le temps du calcul
- [ ] Aperçu sans clic sur « Trier » : aucun fichier déplacé ; « Annuler » ferme sans rien faire
- [ ] Tri par date réel → dossiers `AAAA/MM - Mois/AAAA-MM-JJ` créés ; Ctrl+Z remet UNE photo à la fois
- [ ] Photo déjà au bon endroit : marquée « inchangé » ; nom déjà pris : suffixe _1, _2…
- [ ] Ctrl+B (ou « Renommer en lot ») : exemples du menu déroulant, aperçu `IMG_4821.jpg → 2026-08-15_0001.jpg`
- [ ] Modèle invalide (`{nimporte}`, `{date`) → message rouge, bouton « Renommer » grisé
- [ ] Renommage réel → un seul Ctrl+Z défait tout le lot ; Ctrl+Maj+Z le refait
- [ ] Avec une sélection dans la grille : seules les photos sélectionnées sont concernées
- [ ] Outils désactivés dans Réglages → message « désactivé dans Réglages »
