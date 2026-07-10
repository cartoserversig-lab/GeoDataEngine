# GeoData Engine

> De l'emprise géographique au projet SIG opérationnel en quelques clics.

## Présentation

GeoData Engine est un moteur logiciel géospatial qui automatise la constitution d'un environnement SIG complet à partir d'une simple emprise géographique : recherche, téléchargement, préparation, harmonisation et organisation des données dans une base de données géographique structurée.

Ce projet constitue le socle technique d'une future suite d'outils dédiés aux collectivités, bureaux d'études et gestionnaires de territoire, et sert de brique fondatrice à la constitution d'un jumeau numérique de commune.

## Objectif principal

Développer un moteur Python capable de transformer une emprise géographique en un espace de travail SIG structuré.

## Fonctionnalités visées (V1)

1. **Acquisition automatique des données** — interrogation des sources disponibles et téléchargement des ressources intersectant l'emprise (données IGN : orthophotos, Lidar HD, MNT, MNS, BD TOPO, bâtiments, hydrographie, réseaux routiers).
2. **Harmonisation géographique** — contrôle des systèmes de coordonnées, reprojection automatique, homogénéisation des unités, normalisation des données.
3. **Création d'un environnement SIG** — génération automatique d'une base de données géographique, d'une arborescence projet, d'un catalogue de données et d'un fichier de métadonnées.

## Utilisateurs cibles

Collectivités territoriales, EPCI, syndicats mixtes, bureaux d'études environnement, services SIG, gestionnaires d'infrastructures, organismes publics.

## Architecture

Le moteur métier (*Core*) est indépendant de toute interface (CLI, application desktop, plugins SIG). Le détail est décrit dans [ARCHITECTURE.md](ARCHITECTURE.md).

## Technologies

- Python 3.12+
- **Vecteur** : GeoPandas, Shapely, Pyogrio, Fiona
- **Raster** : Rasterio, GDAL, rioxarray
- **Projections** : PyProj
- **Interface** : PySide6
- **Qualité** : pytest, logging

## Base de données géographique

Format principal : **GeoPackage** (standard OGC, ouvert, compatible QGIS et ArcGIS Pro, facilement distribuable). Évolutions envisagées : PostGIS, File Geodatabase.

## Roadmap

Le détail des versions (V1 à V4) est disponible dans [ROADMAP.md](ROADMAP.md).

## Statut

🚧 En développement — initialisation de la V1.

## Licence

Distribué sous licence MIT — voir [LICENSE](LICENSE).
