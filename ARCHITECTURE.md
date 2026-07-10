# Architecture

## Principe général

Le moteur métier (*Core*) doit être indépendant de toute interface. Les interfaces (CLI, application desktop, plugins SIG) consomment le Core comme une bibliothèque.

```
        GeoData Engine Core
                │
     ┌──────────┼──────────┐
    CLI     Desktop GUI   Plugins SIG
                │
             PySide6
```

## Arborescence technique

```
GeoDataEngine/
├── core/                 # cycle de vie du projet, configuration, orchestration du workflow
│   ├── project.py
│   ├── config.py
│   └── workflow.py
│
├── download/             # connecteurs de téléchargement par source de données
│   ├── ign.py
│   ├── osm.py
│   └── copernicus.py
│
├── processing/           # traitements géospatiaux
│   ├── reprojection.py
│   ├── clipping.py
│   └── validation.py
│
├── database/             # construction de la base géographique et des métadonnées
│   ├── geopackage.py
│   └── metadata.py
│
├── interface/
│   └── desktop/          # interface utilisateur PySide6
│
├── tests/
│
└── documentation/
```

## Chaîne de traitement (workflow)

```
Emprise utilisateur
        ↓
Identification des données nécessaires
        ↓
Téléchargement automatique
        ↓
Décompression
        ↓
Contrôle qualité
        ↓
Reprojection
        ↓
Découpage
        ↓
Organisation
        ↓
Création GeoDatabase
        ↓
Projet SIG final
```

## Structure de sortie d'un projet généré

Un projet produit par GeoData Engine respecte l'organisation standardisée suivante (répertoire `data/` généré à côté du dépôt, non versionné) :

```
Projet_GeoDataEngine/
├── database/
│   └── projet.gpkg
├── raster/
│   ├── orthophoto/
│   ├── mnt/
│   └── lidar/
├── vector/
│   ├── topographie/
│   ├── hydrographie/
│   └── infrastructures/
├── metadata/
├── logs/
└── configuration/
```

## Base de données géographique

Format principal : **GeoPackage** (standard OGC, ouvert, compatible QGIS et ArcGIS Pro, facilement distribuable).

Évolutions possibles : PostGIS, File Geodatabase.
