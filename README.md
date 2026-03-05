# PokeRando Wiki

Interface locale pour visualiser les modifications d'une ROM Pokémon randomisée via **Universal Pokémon Randomizer (UPR)**.

## Prérequis

- [Docker](https://www.docker.com/get-started) + Docker Compose
- [Task](https://taskfile.dev/installation/) (optionnel mais recommandé)

## Lancement

```bash
task up
# ou sans Task :
docker compose up --build -d
```

Ouvre ensuite **http://localhost:8000** dans ton navigateur.

## Utilisation

1. Dans **Universal Pokémon Randomizer**, avant de randomiser : coche **"Generate Log File"** dans les options
2. Lance la randomisation → UPR génère un fichier `.log` ou `.txt`
3. Dans l'interface, glisse ce fichier ou clique "Choisir un fichier"
4. Le wiki se peuple automatiquement !

## Commandes disponibles

| Commande | Description |
|---|---|
| `task up` | Lance le wiki (build + start) |
| `task down` | Arrête le wiki |
| `task logs` | Voir les logs du container |
| `task reset` | Supprime la base (repart de zéro) |
| `task dev` | Mode dev sans Docker (hot reload) |

## Ce qui est tracké

- **Movesets** : les capacités de chaque Pokémon
- **Équipes dresseurs** : les Pokémon de chaque dresseur
- **Objets** : les objets trouvables par lieu

## Structure

```
pokerando/
├── app/
│   ├── main.py        # API FastAPI
│   ├── parser.py      # Parsing du log UPR
│   ├── database.py    # SQLite
│   └── templates/
│       └── index.html # Interface web
├── data/              # Base SQLite (persistante)
├── Dockerfile
├── docker-compose.yml
├── Taskfile.yml
└── requirements.txt
```

## Notes sur le parser

Le parser est conçu pour gérer les différents formats de log d'UPR (Gen 1 à 5). Si certaines données n'apparaissent pas, vérifie que les options correspondantes étaient bien cochées dans UPR au moment de la randomisation.
