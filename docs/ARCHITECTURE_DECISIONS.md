# ARCHITECTURE_DECISIONS — Lipidence-NIR Modular

Quatro partes: (1) quadro geral da arquitetura-alvo, (2) princípios derivados,
(3) tabela de ativação na V1, (4) decisões herdadas dos ADRs do sistema atual.
A Parte 5 recebe as decisões de engenharia tomadas ao longo do trabalho (ADM-NNN).

Decisões **científicas** não ficam aqui: ver `PENDENCIAS_CIENTIFICAS.md`.

---

## Parte 1 — Quadro geral (arquitetura-alvo)

Licenças como informadas pelo pesquisador; serão conferidas nos metadados dos pacotes
quando `docs/catalog/software.md` for gerado (Fase 7), com as divergências registradas lá.

| Camada do Sistema | Tecnologia Escolhida | Licença | Decisão e Papel no Projeto |
|---|---|---|---|
| Runtime e Containers | Podman + Podman Compose | Apache-2.0 | Runtime primário, execução rootless, compatível com Compose. A aplicação é independente do runtime de containers. |
| Banco Transacional e Metadados | PostgreSQL + pgvector | PostgreSQL License | Banco central para usuários, amostras, análises, modelos, resultados e auditoria. pgvector só com necessidade validada de busca por similaridade. |
| Dados Flexíveis | PostgreSQL JSONB | PostgreSQL License | Metadados variáveis de instrumentos, espectros e análises, sem banco NoSQL separado. |
| Processamento Analítico Local | DuckDB + Apache Parquet | MIT / Apache-2.0 | Camada analítica complementar para datasets espectrais. |
| Arquivos Brutos | Local Filesystem + abstração S3 | Local / dependente do backend futuro | Armazenamento local, sempre pela interface `ArtifactStorage`. |
| Backend e APIs | FastAPI + Pydantic | MIT | Serviços, contratos, validação de entrada e API. |
| Interface Científica | **Dash** | MIT | **Interface principal da versão modular**, três telas: Base Experimental, Predição e Desempenho. |
| Visualização Científica | Plotly | MIT | Espectros, paridade, resíduos, PCA, VIP, XAI e diagnóstico. |
| Frontend legado/completo | React + TypeScript + Vite | MIT | Preservado no sistema atual; não obrigatório para a V1 modular. |
| Fila e Tarefas Assíncronas | Celery | BSD-3-Clause | Treinamentos e tarefas demoradas quando a execução síncrona não for adequada. |
| Broker e Cache | Valkey | BSD-3-Clause | Implementação preferencial para Celery/cache, com configuração desacoplada. |
| Quimiometria e ML Clássico | scikit-learn + SciPy | BSD-3-Clause | SNV, MSC, Savitzky-Golay, PLS1, PLS2, SVR, Random Forest e componentes estatísticos. |
| Boosting | LightGBM / XGBoost | MIT / Apache-2.0 | Modelos adicionais de benchmark para relações não lineares. |
| Deep Learning | PyTorch | BSD-style | 1D-CNN, CPU/GPU, saída única ou múltipla. |
| XAI | SHAP + Captum | MIT / BSD-3-Clause | SHAP para modelos clássicos/árvores; Captum para PyTorch. |
| Tracking / Model Registry | MLflow OSS | Apache-2.0 | Experimentos, hiperparâmetros, métricas, artefatos e versões dos modelos. |
| Versionamento | DVC + Git | Apache-2.0 / GPLv2 | Versões de dados, código e experimentos. |
| Métricas e Monitoramento | Prometheus + Grafana OSS | Apache-2.0 / AGPLv3 | Camada complementar de monitoramento. |

## Parte 2 — Princípios derivados

- **Podman.** O runtime de containers não aparece na lógica da aplicação, que também funciona fora de containers.
- **PostgreSQL.** Fonte transacional central. JSONB atende aos metadados flexíveis; sem MongoDB nesta versão.
- **DuckDB.** Complementar e analítico; não substitui o PostgreSQL como banco da aplicação.
- **pgvector.** Só em funcionalidades em que a representação vetorial e a busca por similaridade tenham justificativa metodológica.
- **MLflow + DVC.** Responsabilidades distintas:

```
Git        → código
DVC        → versão dos datasets
MLflow     → experimentos e modelos
PostgreSQL → domínio e auditoria
```

- **Dash.** Camada visual. O sistema científico funciona por inteiro sem a interface (INV-13).
- **Modelos.** Isolados e catalogados: PLS1, PLS2, SVR, Random Forest, Gradient Boosting, LightGBM, XGBoost, 1D-CNN. Nenhum algoritmo entra no núcleo sem manifesto, testes, métricas, referência, licença, justificativa e status de validação.

## Parte 3 — Ativação na V1

Cada peça de infraestrutura fica atrás de um contrato em `core/contracts.py`. Trocar de
implementação não pode exigir mudança no núcleo científico.

| Camada | Estado na V1 | Critério para a implementação-alvo |
|--------|--------------|------------------------------------|
| Podman + Compose | **Ativo.** `Containerfile` e `compose.yaml` (aplicação + PostgreSQL), rootless; a aplicação também sobe sem container | — |
| PostgreSQL + JSONB | **Ativo** desde a Fase 1 | — |
| pgvector | Inativo; extensão não é criada | Funcionalidade de similaridade espectral com justificativa metodológica registrada em `PENDENCIAS_CIENTIFICAS.md` |
| Parquet + DuckDB | **Ativo, mínimo.** Retrato de cada dataset em Parquet; DuckDB consulta esses arquivos | — |
| Arquivos brutos | **Ativo:** `ArtifactStorage` local | Adapter S3 quando for preciso armazenar fora da máquina local |
| FastAPI + Pydantic | **Ativo** | — |
| Dash + Plotly | **Ativo** | — |
| React | Não usado; preservado no sistema atual | — |
| Celery + Valkey | Contrato `JobRunner` **ativo** com executor em processo (uma fila, um worker) | `CeleryJobRunner` quando o treino passar de alguns minutos ou houver mais de um usuário treinando ao mesmo tempo (`PROVISORIO`) |
| scikit-learn + SciPy, PyTorch | **Ativos** | — |
| LightGBM / XGBoost | **Ativos** na Fase 4, papel de benchmark | — |
| SHAP + Captum | **Ativos** na Fase 6 | — |
| MLflow | Contrato `Tracker` desde a Fase 3; adapter MLflow na Fase 7 | — |
| DVC + Git | Git ativo; DVC na Fase 7, sem ser dependência de execução | — |
| Prometheus + Grafana | Inativos; dependência opcional, nunca importada de forma incondicional | Implantação contínua com vários usuários |

## Parte 4 — Decisões herdadas dos ADRs do sistema atual

Estado lido no cabeçalho de cada ADR em `docs/adr/` (commit `e027e41`).

| ADR de origem | Estado lá | Posição na versão modular |
|---|---|---|
| `ADR-anti-leakage-split-strategy` | Accepted, implementado | **Mantida.** Partição explícita, `LeakageError`, `verify_no_leakage`, `split_hash` (INV-3, INV-4). |
| `ADR-applicability-domain-ood` | Accepted, implementado | **Mantida.** Política formal de domínio; estados `DENTRO / LIMITROFE / FORA` (seção 12, INV-12). |
| `ADR-mlflow-experiment-tracking` | Accepted, parcialmente implementado | **Mantida com ajuste.** MLflow atrás do contrato `Tracker`; qual versão está ativa vive só no PostgreSQL (`ActiveModel`). Backend em banco, nunca `./mlruns`. |
| `ADR-authentication-session-strategy` | Accepted, implementado | **Mantida e simplificada.** Cookie HttpOnly + Argon2; sessão no servidor; sem JWT de refresh, revogação em Redis ou MFA. |
| `ADR-shap-captum-xai` | Proposed | **Adotada** (Fase 6): SHAP para clássicos/árvores, Captum para a 1D-CNN, ambos atrás do contrato `Attributor` (INV-14). |
| `ADR-artifact-storage` | Proposed | **Adotada** (Fase 1): contrato `ArtifactStorage`, implementação local. |
| `ADR-dvc-data-versioning` | Proposed | **Adotada** (Fase 7), sem ser dependência de execução. |
| `ADR-plotly-scientific-visualization` | Proposed | **Adotada** via Dash + Plotly (a parte sobre Recharts não se aplica: não há React na V1). |
| `ADR-cache-broker-redis-valkey` | Proposed, preliminar "KEEP REDIS" | **Superada.** Valkey é a implementação-alvo; na V1 não há broker (executor em processo). |

## Parte 5 — Decisões de engenharia da versão modular

### ADM-001 — Python 3.11
- **Contexto.** A seção 5.4 pede "Python 3.10 ou a mínima exigida pelas dependências fixadas". O ambiente de desenvolvimento oferece 3.11, 3.12 e 3.13; não há 3.10. `numpy==1.26.3`, `scipy==1.11.4` e `torch==2.1.2` (versões do sistema atual) não têm distribuição para 3.13.
- **Decisão.** Python 3.11 no desenvolvimento e no CI.
- **Alternativa descartada.** 3.13 (obrigaria a subir todas as versões científicas de uma vez, perdendo a comparabilidade com o sistema atual); 3.10 (indisponível no ambiente e sem ganho).

### ADM-002 — Versões: científicas mantidas, camada web atualizada
- **Contexto.** Dash com FastAPI como servidor exige Dash ≥ 4.2. A resolução de dependências com `dash[fastapi]` instala Dash 4.5.0, FastAPI 0.162.5, Pydantic 2.14.3 e Starlette 1.10.0, mais novos que `fastapi==0.109.0` / `pydantic==2.5.3` do `backend/requirements/base.txt`.
- **Decisão.** Manter as versões do sistema atual para numpy 1.26.3, pandas 2.1.4, scipy 1.11.4, scikit-learn 1.4.0, SQLAlchemy 2.0.25, Alembic 1.13.1, psycopg2-binary 2.9.9, PyYAML 6.0.1 e plotly 5.18.0 (a resolução conjunta com Dash 4.5.0 foi verificada). Atualizar FastAPI, Pydantic e Uvicorn para as exigidas pelo Dash. `passlib` é substituído por `argon2-cffi` direto (ver ADM-004).
- **Alternativa descartada.** Manter FastAPI 0.109 e rodar o Dash em processo próprio (plano B da seção 5.4): desnecessário, o plano A funciona.

### ADM-003 — Dash sobre a mesma instância FastAPI (plano A confirmado)
- **Contexto.** Seção 5.4. Verificado na versão instalada (Dash 4.5.0): `Dash(__name__, server=<FastAPI>)` devolve `app.server` idêntico à instância passada e registra as rotas `_dash-layout`, `_dash-dependencies`, `_dash-update-component` sob o prefixo configurado; `GET` nessas rotas via `TestClient` responde 200.
- **Decisão.** Uma única instância FastAPI serve API, login e Dash (mesma origem, mesmo cookie).
- **Alternativa descartada.** Dash em processo próprio consumindo a API por HTTP.

### ADM-004 — Hash de senha com `argon2-cffi`, sem `passlib`
- **Contexto.** O sistema atual usa `passlib[argon2]==1.7.4`. `passlib` não tem lançamento desde 2020 e depende do módulo `crypt`, removido no Python 3.13.
- **Decisão.** Usar `argon2-cffi` (`PasswordHasher`) diretamente. O formato do hash (PHC `$argon2id$`) é o mesmo.
- **Alternativa descartada.** Manter `passlib` como camada intermediária.

### ADM-005 — Configuração de testes e lint dentro de `lipidence_modular/`
- **Contexto.** O protocolo restringe a escrita a `/lipidence_modular/` (mais o workflow próprio). Não é possível criar `pyproject.toml` na raiz.
- **Decisão.** `lipidence_modular/pytest.ini` (com `pythonpath = ..` e `--import-mode=importlib`) e `lipidence_modular/ruff.toml`. Execução da raiz: `python -m pytest -c lipidence_modular/pytest.ini lipidence_modular` e `ruff check --config lipidence_modular/ruff.toml lipidence_modular`.
- **Alternativa descartada.** Transformar `lipidence_modular/` em projeto instalável com `pyproject.toml` próprio e layout `src/`: mudaria o caminho de import pedido (`python -m lipidence_modular` a partir da raiz).

### ADM-006 — CLI com `argparse`
- **Contexto.** A CLI precisa existir sem interface, broker ou container (INV-13).
- **Decisão.** `argparse` da biblioteca padrão; cada bloco registra os seus subcomandos.
- **Alternativa descartada.** Typer/Click: dependência extra sem ganho para comandos simples.

### ADM-007 — CI próprio, sem mascarar falhas
- **Contexto.** O `ci.yml` do sistema atual ainda tem `ruff check . || true`.
- **Decisão.** `.github/workflows/lipidence_modular.yml` roda lint e testes como passos separados, sem `|| true` e sem `continue-on-error`; dispara só quando `lipidence_modular/**` ou o próprio workflow mudam. O `ci.yml` existente não é tocado.
- **Alternativa descartada.** Acrescentar um job ao `ci.yml` (proibido pelo protocolo).

### ADM-008 — Sessão com negação por padrão
- **Contexto.** No Dash 4.5.0 com FastAPI, o backend registra uma rota coringa (`{path:path}`) que devolve a página da interface para qualquer caminho desconhecido, inclusive fora do prefixo `/app/`. Um teste da Fase 1 mostrou `GET /register` respondendo 200 sem sessão quando a proteção era uma lista de prefixos.
- **Decisão.** O middleware de sessão protege tudo, exceto a lista explícita `/api/health`, `/login`, `/logout`. Sem sessão: 401 em `/api/`, redirecionamento para `/login` no restante. Isso inclui `/docs` e `/openapi.json`.
- **Alternativa descartada.** Lista de prefixos protegidos (deixa a rota coringa exposta); remover a rota coringa mexendo em API privada do Dash.

### ADM-009 — CSRF: token por sessão, no cabeçalho que o Dash já envia
- **Contexto.** A seção 17 pede proteção CSRF. O renderer do Dash lê o cookie `_csrf_token` e envia o cabeçalho `X-CSRFToken` em todo callback (verificado no `dash_renderer.min.js` da versão instalada).
- **Decisão.** Cada sessão tem um token CSRF guardado no servidor. No login ele vai num cookie legível por script (`_csrf_token`); todo método que altera estado precisa do cabeçalho `X-CSRFToken` igual ao token da sessão (callbacks do Dash e chamadas da API usam o mesmo mecanismo). Os formulários de login e de saída usam campo oculto; o de login, sem sessão ainda, compara com um cookie próprio de curta duração. O cookie de sessão é `HttpOnly`, `SameSite=Lax`, `Secure` em produção.
- **Alternativa descartada.** Biblioteca de CSRF para Starlette (dependência extra para uma comparação de tokens); confiar só em `SameSite`.

### ADM-010 — Tabelas ORM em `repositories/tables/`, uma migração por fase
- **Contexto.** A seção 7 aponta `data/schemas/` e `repositories/` como destino de `backend/app/db/models.py`. O teste de arquitetura exige que o núcleo científico (`data/` incluído) não importe SQLAlchemy.
- **Decisão.** As tabelas ORM ficam em `repositories/tables/` (um módulo por bloco funcional); `data/schemas/` recebe, a partir da Fase 2, os esquemas de domínio sem dependência de banco. Cada fase cria só as tabelas que grava: a Fase 1 tem `users` e `sessions`. Assim nenhuma entidade existe no banco sem caminho real de escrita (classe de erro da seção 7). O diretório das migrações chama-se `migrations/` para não repetir o nome da biblioteca `alembic`.
- **Alternativa descartada.** Criar na Fase 1 todas as entidades da seção 18.

### ADM-011 — Roteamento próprio entre as três telas
- **Contexto.** O Dash Pages (`use_pages`) mantém um registro global de páginas por processo, o que atrapalha criar a aplicação várias vezes nos testes.
- **Decisão.** `dcc.Location` + um callback de roteamento (`callbacks/routing.py`) sobre a tupla fixa `PAGES`. A função `resolve_page` é testada sem servidor.
- **Alternativa descartada.** Dash Pages.

### ADM-012 — Testes com banco: pulados localmente, obrigatórios no CI
- **Contexto.** Os testes de integração precisam de PostgreSQL (seção 5.4). Pular em silêncio permitiria um CI verde sem exercitar o banco.
- **Decisão.** Testes marcados `db` usam `LIPIDENCE_TEST_DATABASE_URL`. Sem a variável, são pulados com o motivo escrito; com `LIPIDENCE_REQUIRE_DB=1` (definido no workflow), a ausência do banco é falha.
- **Alternativa descartada.** SQLite nos testes (não tem JSONB nem o mesmo comportamento de tipos).

### ADM-013 — `.gitignore` próprio para reincluir `models/`
- **Contexto.** O `.gitignore` da raiz ignora `models/` (artefatos treinados do sistema atual). Na versão modular, `lipidence_modular/models/` é código-fonte. O arquivo da raiz não pode ser alterado (protocolo, regra 1).
- **Decisão.** `lipidence_modular/.gitignore` com `!models/` e `!models/**`. Artefatos treinados (`*.joblib`, `*.pt`, `*.pkl`) continuam ignorados pela raiz; eles vivem no `ArtifactStorage`, fora do repositório.
- **Alternativa descartada.** Renomear o diretório de modelos (contraria a seção 6).

### ADM-014 — O preview executa a rotina de importação e desfaz a transação
- **Contexto.** A seção 8.7 proíbe importação silenciosa e exige preview antes da confirmação. Duas rotinas (uma para simular, outra para gravar) poderiam divergir.
- **Decisão.** `ImportService.preview` e `ImportService.confirm` chamam a mesma rotina `_execute`; o preview roda dentro de uma transação que termina em `rollback`. O relatório do preview inclui as verificações contra o banco (amostra existente, replicata já gravada). O upload cria um `ImportBatch` com estado `STAGED` e guarda o arquivo bruto com SHA-256; a interface guarda só o `import_batch_id`.
- **Alternativa descartada.** Validador separado para o preview.

### ADM-015 — Unidade de contagem do relatório e regra "rejeitado = nada entrou"
- **Contexto.** O relatório da seção 8.7 soma `recebidos = importados + alertas + rejeitados`.
- **Decisão.** O item é uma unidade do arquivo: uma linha (layout largo, arquivo combinado, referências) ou uma amostra (layout longo, arquivo único). As três situações são mutuamente exclusivas: "alerta" é item importado com ressalva. Um item rejeitado não entra pela metade: no arquivo combinado, se o espectro da linha é rejeitado, as referências da mesma linha também não são gravadas.
- **Alternativa descartada.** Contar medidas individuais (o total deixaria de bater com as linhas do arquivo).

### ADM-016 — Tradução única de erros de domínio
- **Contexto.** API, CLI e interface precisam responder do mesmo modo a erro de plano, conflito de identidade, arquivo duplicado.
- **Decisão.** `application/errors.py::describe_error` mapeia cada exceção de domínio para código HTTP e mensagem. A API usa em um handler; a CLI imprime e sai com código 2; o gateway do Dash converte em `UserFacingError`, e os callbacks mostram a mensagem. Exceção não reconhecida não é capturada.
- **Alternativa descartada.** `except Exception` nos callbacks (classe de erro da seção 7).

### ADM-017 — `dash_table.DataTable` na tela Base Experimental
- **Contexto.** O mapeamento de colunas precisa de uma tabela editável. O Dash 4.5.0 avisa que `dash_table.DataTable` sairá dos componentes embutidos em uma versão principal futura e recomenda `dash-ag-grid`.
- **Decisão.** Usar `DataTable` agora (já incluído, sem dependência nova) em dois pontos isolados (`pages/base_experimental.py` e `callbacks/base_experimental.py`). A troca fica registrada como dívida para quando o Dash for atualizado de versão principal.
- **Alternativa descartada.** Acrescentar `dash-ag-grid` já nesta fase.
