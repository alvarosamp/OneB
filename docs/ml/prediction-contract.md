# Prediction Contract

Every model, rule engine or meta-model should eventually emit a common
prediction shape.

```text
Prediction
  symbol
  horizon
  direction
  action
  probability
  confidence
  uncertainty
  regime
  model_id
  model_version
  dataset_version
  evidence[]
  generated_at
  data_as_of
  quality_score
```

Evidence should be structured, not counted as votes:

```text
technical bullish strength=0.64 confidence=0.78
macro bearish strength=0.32 confidence=0.73
news neutral strength=0.51 confidence=0.49
risk bearish strength=0.70 confidence=0.88
```

The current logistic regression remains the baseline. Any new model must beat
it out of sample after fees, slippage, turnover and regime splits.

Current implementation:

- `app.predictions.Prediction`
- `app.predictions.Evidence`
- `app.research_registry.ExperimentRecord`
- `scripts/register_experiment.py`
