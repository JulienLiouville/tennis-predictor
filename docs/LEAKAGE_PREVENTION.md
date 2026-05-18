# Leakage Prevention

## Règles

| Feature | Règle |
|---|---|
| Rankings | `ranking_date <= match_date` |
| H2H | uniquement les matchs AVANT le match courant |
| Momentum | pas de matchs futurs |
| Train/Test | split temporel uniquement — **INTERDIT : `random_state=42`** |
| Cotes | pas de closing odds après le début du match |
| Features | jamais d'information post-match |

---

## Status actuel

| Règle | Status |
|---|---|
| Rankings temporels | ✅ implémenté dans `match_collector.py` |
| H2H temporel | ✅ implémenté dans `precompute_features.py` |
| Momentum temporel | ✅ implémenté dans `precompute_features.py` |
| Split temporel train/test | ❌ `random_state=42` encore utilisé dans `predictor.py` |
| Features post-match | ✅ aucune feature post-match détectée |

---

## Leakage Checklist

Avant de valider un modèle :

- [ ] Le split train/test est-il **temporel** (pas random) ?
- [ ] Les rankings utilisés ont-ils une date ≤ date du match ?
- [ ] Le H2H exclut-il le match courant et les matchs futurs ?
- [ ] Le momentum est-il calculé sur les matchs **avant** la date du match ?
- [ ] Aucune feature ne contient le résultat du match (score, sets, winner) ?
- [ ] Les cotes utilisées sont-elles des opening odds (pas closing) ?
- [ ] `precompute_features.py` a-t-il été relancé après ajout de nouvelles données ?

---

## Problème connu

`train_test_split(X, y, test_size=0.2, random_state=42)` dans `predictor.train()` — split aléatoire qui mélange les dates. Le modèle peut s'entraîner sur des matchs de 2024 et être testé sur des matchs de 2020.

**Fix :**
```python
df_sorted = df.sort_values('date')
split_idx = int(len(df_sorted) * 0.8)
train_df = df_sorted.iloc[:split_idx]
test_df  = df_sorted.iloc[split_idx:]
```