# Spotify Million Playlist Dataset Challenge

A comprehensive recommender system project exploring different approaches to music recommendation using the Spotify Million Playlist Dataset.

## Project Overview

This project implements and compares multiple recommendation algorithms for music playlist completion, progressing from simple baselines to advanced graph-based approaches.

### Challenge Description

The goal is to recommend tracks for 10,000 incomplete playlists across 10 different challenge categories:
- Title-only predictions
- Predictions with varying numbers of seed tracks (1, 5, 10, 25, 100)
- Random vs sequential track sampling

## Technology Stack

- **Databases**: PostgreSQL → Snowflake → Neo4j
- **Languages**: Python, SQL, Cypher
- **ML Libraries**: scikit-learn, pandas, numpy
- **Development**: Jupyter notebooks, pytest

## Project Structure

```
├── src/                    # Source code
├── notebooks/              # Jupyter notebooks for exploration
├── data/                   # Data files (raw, processed)
├── configs/                # Configuration files
├── tests/                  # Unit tests
└── scripts/                # Utility scripts
```

## Development Status

🚧 **Work in Progress** 🚧

- [x] Project structure setup
- [ ] Data loading and EDA (PostgreSQL)
- [ ] Baseline recommendation models
- [ ] Snowflake migration and scaling
- [ ] Graph-based models (Neo4j)
- [ ] Model evaluation and comparison
- [ ] Final submission generation

## Approaches to Implement

### Phase 1: Baseline Models

- Popularity-based recommendations
- Co-occurrence analysis
- Simple collaborative filtering

### Phase 2: Advanced Models

- Matrix factorization
- Content-based filtering
- Deep learning embeddings

### Phase 3: Graph-Based Models

- Neo4j graph algorithms
- Node2Vec embeddings
- Community detection

## Dataset

This project uses the [Spotify Million Playlist Dataset Challenge](https://www.aicrowd.com/challenges/spotify-million-playlist-dataset-challenge) data. Please refer to the original dataset terms of use.

## Contributing

This is a learning project, but suggestions and feedback are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
