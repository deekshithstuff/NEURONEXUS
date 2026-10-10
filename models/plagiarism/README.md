# Plagiarism model artifacts

This directory stores serialized model weights and metadata produced by the training workflow.

Expected files include:

- plagiarism_classifier.joblib or pickle-based replacement
- model_metadata.json
- dataset version or evaluation summaries when generated

Do not load untrusted model artifacts without validating the dataset and environment first.
