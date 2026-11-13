# REUSE_MAP — aproveitamento do sistema existente

Commit de referência do sistema atual: `e027e41`.
Cada linha foi confirmada pela leitura do arquivo de origem nesse commit (Fase 0).
A coluna **Estado** é atualizada quando o código é efetivamente portado; cada arquivo
portado leva o cabeçalho `# Portado de <caminho>@<commit>`.

Estados: `CONFIRMADO` (origem existe e contém o que a seção 7 descreve; ainda não portado) ·
`PORTADO` (copiado e adaptado, com teste) · `REFERENCIA` (consultado, sem cópia de código) ·
`REESCRITO` (constructo refeito; a origem serviu de ponto de partida).

| Origem (linhas) | Destino | Confirmado na leitura | Estado |
|---|---|---|---|
| `backend/app/ml/preprocessing/transformers.py` (744) | `preprocessing/*/` | `SNVTransformer` (l.22), `MSCTransformer` (l.96, aprende referência no `fit`), `SavGolTransformer` (l.206), todos `BaseEstimator, TransformerMixin`. Presentes e **não portar**: `PolynomialDetrender` (l.314), `RobustScaler` (l.384), `WavelengthSelector` (l.441), `SpectralPreprocessingPipeline` (l.502). O arquivo traz funções `test_*` embutidas em código de produção (l.618–744), que não serão reproduzidas | CONFIRMADO |
| `backend/app/ml/validation/split_strategy.py` (628) | `validation/` | `LeakageError` (l.61), `SplitStrategyName`, `SampleMetadata`, `SplitAssignment` com `split_hash` (l.208) e `to_manifest` (l.226), estratégias agrupada (l.319), temporal (l.362), explícita (l.401), aleatória (l.437), `SplitStrategyResolver`, `verify_no_leakage` (l.554), `hash_group_vector` (l.602) | CONFIRMADO |
| `backend/app/ml/validation/validation_advanced.py` (1356) | `evaluation/`, `validation/` | `MetricsCalculator` (l.94: rmse, bias, rpd, sep, rpiq, slope/intercept, bootstrap), `NestedCrossValidator` (l.487), `LOGOValidator` (l.694), `YRandomizationTest` (l.808), `ExternalSetValidator` (l.1095). Não portar: `OutlierDetector`, `LearningCurveAnalyzer`, `ComprehensiveValidator`, métricas `ccc/mape/sdr/rer/cv` (fora da seção 15.1) | CONFIRMADO |
| `backend/app/ml/preprocessing/augmentation.py` (889; só `OODDetector`, l.471) | `ood/` | `OODDetector` presente; o restante do arquivo é data augmentation (fora de escopo) | CONFIRMADO |
| `backend/app/ml/validation/applicability_domain.py` (195) | `ood/` | `ApplicabilityDecision`, `ApplicabilityDomainPolicy` (l.48), `ApplicabilityDomainResult`, `ApplicabilityDomainService` (l.118) | CONFIRMADO |
| `backend/app/ml/uncertainty.py` (332) | `uncertainty/` | `SplitConformalRegressor` (l.177), `UncertainPrediction.coverage_diagnostics` (l.67). Não portar: `MCDropoutPredictor` (l.81), `LocallyAdaptiveConformal` (l.245) | CONFIRMADO |
| `backend/app/ml/spectral_quality.py` (440) | `data/validators/` | `validate_wavelength_grid` (l.118), `validate_spectrum` (l.246), `fatty_acid_sum_check` (l.397), relatório de problemas (l.31–70) | PORTADO (Fase 2), exceto `fatty_acid_sum_check` |
| `backend/app/services/file_parser.py` (661) | `data/importers/` | `SpectralFileParser.parse_file` (l.95), `parse_file_preview` (l.157), `_parse_tabular` (l.224), `_parse_excel` (l.250). JCAMP-DX (l.415) e SPA (l.530) existem e ficam como adapters futuros | PORTADO (Fase 2): leitura tabular e preview |
| `backend/app/xai/xai_methods.py` (1258) | `xai/`, `coherence/`, `config/chem_windows/` | `LIPID_BANDS` (13 bandas, l.53) e `NON_LIPID_BANDS` (6 bandas, l.80); `VIPCalculator` (l.257); `ExplanationStability` (l.317); `SHAPVIPCorrelator` (l.748); `ChemicalCoherenceIndex` (l.488, sigla antiga ICC em `calculate_icc`, l.1225) será reescrito; `GradCAM1D` (l.113) só se a Captum não atender. Não portar: `LIMEExplainer`, `SpectralCertaintyIndex`, `XAIConsistencyChecker`, `IntegratedXAIAnalyzer` | CONFIRMADO |
| `backend/app/ml/models/deep_learning.py` (475) | `models/cnn1d/` | `CNN1D_PyTorch` (l.34), `DeepLearningTrainer` (l.265: fit/predict/save/load). Não portar: `ResidualBlock1D`, `ResNet1D_PyTorch`, `AttentionSpectralNet`, `DeepModelFactory` | CONFIRMADO |
| `backend/app/ml/automl.py` (526) | `models/lgbm/`, `models/xgb/` | Faixas de hiperparâmetros em `_sample_xgb` (l.154) e `_sample_lgb` (l.179). Usa Optuna: nada de código é portado | CONFIRMADO (REFERENCIA) |
| `backend/app/ml/registry/model_registry.py` (504) | `storage/`, `core/provenance.py` | `compute_data_hash` (l.75), `compute_data_sha256` (l.84), `register` com manifesto (l.204), `get_manifest` (l.352) | CONFIRMADO |
| `backend/app/services/experiment_tracking.py` (166) | `tracking/` | `ExperimentTrackingService.log_training_run` (l.89), `TrackingResult` (l.33) | CONFIRMADO |
| `backend/app/db/models.py` (927) | `data/schemas/`, `repositories/` | `Spectrum` (l.114, FK opcional para `traceability_samples`, l.133), `TraceabilitySample` (l.586, `sample_code` único), `LabReferenceValue` (l.630: amostra × analito × replicata, com `UniqueConstraint`). `ModelVersion` (l.321) existe e é a entidade "definida e nunca gravada" citada na seção 7 | REESCRITO (Fase 2): a forma das tabelas foi aproveitada, sem cópia de código |
| `backend/app/core/security.py` (258) e `docs/adr/ADR-authentication-session-strategy.md` | `auth/` | Argon2 via `passlib.CryptContext` (l.21), `verify_password` (l.141), `get_password_hash` (l.155). Não portar: JWT de acesso/refresh (l.35, l.79), escopos | PORTADO (Fase 1) |
| `docker-compose.yml` (181), `docker/postgres-init/init-mlflow-db.sh` (14), `mlflow/Dockerfile` (31) | `deployment/` | Presentes; servem de referência para `compose.yaml` | CONFIRMADO (REFERENCIA) |
| `backend/app/celery_app.py` (116), `backend/app/tasks/training.py` (1202) | `jobs/celery_runner/` (Fase 9) | Presentes; só referência de configuração | CONFIRMADO (REFERENCIA) |
| `backend/tests/unit/test_preprocessing.py`, `test_split_strategy.py`, `test_applicability_domain.py`, `test_validation_advanced.py`, `test_spectral_quality.py`, `test_prediction_uncertainty.py`, `test_training_grouping_guard.py` | `tests/` | Os sete arquivos existem | CONFIRMADO |
| `test_data/generate_nir_datasets.py` (483) | `tests/fixtures/` | `generate_realistic_nir_spectrum` (l.13), `generate_training_dataset` (l.138) | REESCRITO (Fase 2): `tests/fixtures/synthetic.py` |
| `docs/adr/*.md` (9 arquivos) | `docs/ARCHITECTURE_DECISIONS.md` | Estados lidos nos cabeçalhos; resumo na Parte 4 de `ARCHITECTURE_DECISIONS.md` | REFERENCIA |
| `backend/app/iiql/` (`calculator.py`, `functions.py`, `subscores/`) | `indices/iiql/` (Fase 8) | `IIQLCalculator` (l.36 de `calculator.py`) | CONFIRMADO |

## Classes de erro confirmadas no sistema atual (seção 7)

| Classe de erro | Evidência lida em `e027e41` |
|---|---|
| CI que mascara falha | `.github/workflows/ci.yml` l.91: `ruff check . \|\| true` |
| Explicação com rótulo de método que não a calculou | `backend/app/api/v1/endpoints/xai.py` l.345–355: valores "SHAP" derivados de `(vip - 1.0) * 1.5`; l.127: `_synthetic_vip_profile` como fallback de demonstração |
| SHAP/Captum nunca importados | `grep -rE "import shap\|from shap\|import captum\|from captum" backend/app` não retorna nada |
| Dependência opcional importada incondicionalmente | `backend/app/core/metrics.py` l.5: `from prometheus_client import ...` |

As demais classes da lista (parâmetro `dataset_id` não lido, contrato `spectra/targets` × `X/y`,
enum de validação sem implementação, `ModelVersion` não gravada, `groups` não repassado) estão
registradas na seção 7 do prompt mestre e em `docs/audits/CLEANUP_REPORT.md`; não foram
reverificadas linha a linha na Fase 0 porque nenhuma delas é código a portar. Ficam como
lista de verificação para os testes das Fases 3 a 5.

## Registro de portes

| Data | Origem@commit | Destino | Adaptações |
|---|---|---|---|
| Fase 1 | `backend/app/core/security.py@e027e41` (`verify_password`, `get_password_hash`) | `auth/passwords.py` | `passlib` trocado por `argon2-cffi` (ADM-004); tamanho mínimo de senha; hash fictício para tempo constante. JWT, refresh e escopos não portados |
| Fase 2 | `backend/app/ml/spectral_quality.py@e027e41` (`validate_wavelength_grid`, `validate_spectrum`, `_estimate_snr`) | `data/validators/spectral_quality.py` | Limiares em `config/spectral_quality.yaml` (PROVISORIO); mensagens em português; faixa de absorbância só para sinal de absorbância. `fatty_acid_sum_check` **não portado**: exige definir quais parâmetros compõem o perfil completo (P-13); sem isso, a soma dos cinco ácidos cadastrados não tem valor esperado |
| Fase 2 | `backend/app/services/file_parser.py@e027e41` (`_parse_tabular`, `_parse_excel`, `parse_file_preview`) | `data/importers/` | Detecção explícita de codificação, delimitador, separador decimal e cabeçalho, devolvida para confirmação; JCAMP-DX e SPA não portados |
| Fase 2 | `test_data/generate_nir_datasets.py@e027e41` (ideia de linha de base + bandas gaussianas + ruído) | `tests/fixtures/synthetic.py` | Reescrito: determinístico por seed, bandas em posições declaradas, estrutura de genótipos, exportação nos layouts largo, longo, arquivo único, combinado e XLSX |
