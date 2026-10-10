# Plagiarism model artifacts

`backend.training.train_classifier` writes:

- `plagiarism_classifier.joblib`: fitted scikit-learn Logistic Regression and fitted training-only
  TF-IDF vectorizer
- `model_metadata.json`: feature schema, dataset hash, split sizes/distributions, selected validation
  threshold, and independent test metrics

The API loads an artifact lazily from this directory or from the path set in
`PAPERPILOT_PLAGIARISM_CLASSIFIER_PATH`. No rule-based or random-prediction fallback is used when
the artifact is absent.

Joblib artifacts are executable serialization formats. Only load artifacts produced from trusted
datasets and by a trusted training environment.
