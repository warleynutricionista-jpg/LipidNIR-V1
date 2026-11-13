# PROGRESS — Lipidence-NIR Modular

Reler este arquivo e o `PROMPT_LIPIDENCE_MODULAR_v3.md` no início de cada sessão.

## Estado atual

| Fase | Entrega | Estado |
|------|---------|--------|
| 0 | Inventário e decisões | **Concluída** |
| 1 | Núcleo, banco, autenticação, casca do Dash, containers | **Concluída, com uma ressalva** (Podman não executado; ver limitações) |
| 2 | Importação assistida e Base Experimental | **Concluída** |
| 3 | Dataset, partição, pré-processamento, cinco modelos, domínio, intervalo | Não iniciada |
| 4 | 1D-CNN, LightGBM, XGBoost, versões, ativação | Não iniciada |
| 5 | Predição | Não iniciada |
| 6 | Avaliação, atribuição, ICQ, diagnóstico | Não iniciada |
| 7 | MLflow, DVC, catálogos, documentação final | Não iniciada |
| 8 | IIQL (opcional) | Não iniciada |
| 9 | Infraestrutura-alvo (condicional) | Não iniciada |

## Fase 0 — Inventário e decisões

### Feito
- `docs/REUSE_MAP.md`: as 20 linhas da seção 7 confirmadas pela leitura dos arquivos de origem no commit `e027e41` (classes e números de linha anotados). Quatro das oito classes de erro confirmadas com evidência de arquivo e linha.
- `docs/ARCHITECTURE_DECISIONS.md`: quadro geral, princípios, tabela de ativação, posição sobre os 9 ADRs do sistema atual e sete decisões de engenharia (ADM-001 a ADM-007).
- `docs/PENDENCIAS_CIENTIFICAS.md`: 11 valores provisórios, sobreposições e rótulos das janelas químicas herdadas, referência a conferir.
- Esqueleto do pacote: `__init__.py`, `__main__.py`, `cli/` com o comando `version`.
- Testes (4, verdes): CLI por função e por subprocesso, comando desconhecido gera erro, independência do `backend/` e imports absolutos.
- `ruff` limpo.
- `.github/workflows/lipidence_modular.yml`: lint e testes como passos separados, sem `|| true`.
- Verificado na versão instalada: Dash 4.5.0 aceita a instância FastAPI como servidor (ADM-003).

### Pendente
- Nada na Fase 0.

### Limitações conhecidas
- O resultado do workflow no GitHub Actions precisa ser conferido após cada push; localmente, os mesmos dois comandos passam.
- Quatro classes de erro da seção 7 (`dataset_id` não lido, contrato `spectra/targets` × `X/y`, enum de validação sem implementação, `groups` não repassado) não foram reverificadas linha a linha; não são código a portar.
- Nenhuma referência bibliográfica foi conferida na fonte primária.
- No ambiente de desenvolvimento desta sessão, `download.pytorch.org` não é alcançável: `torch==2.1.2+cpu` não pôde ser instalado desse índice. A variante do PyPI (`torch==2.1.2`, com bibliotecas CUDA embutidas) foi instalada no lugar. Isso afeta só a Fase 4 e o tamanho da instalação; a decisão sobre o índice no CI fica para lá.

## Fase 1 — Núcleo

### Feito
- `core/`: contratos de infraestrutura (`ArtifactStorage`, `JobRunner`, `Tracker`, `AnalyticsStore`) e científicos (`Preprocessor`, `BaseRegressor` e capacidades, `Splitter`, `DomainDetector`, `IntervalCalibrator`, `Attributor`); registry por manifestos; configuração por ambiente; erros de domínio.
- `data/identity/`: normalização do `sample_id` e resolução de precedência e conflito (INV-1, INV-7).
- `storage/local.py`: `ArtifactStorage` local, imutável, com SHA-256 e gravação atômica.
- `jobs/in_process.py`: `JobRunner` com uma fila e um worker.
- `repositories/` + `migrations/`: PostgreSQL com SQLAlchemy 2 e Alembic; migração `0001_auth` (usuários e sessões).
- `auth/` + `application/auth_service.py`: Argon2id, sessão guardada no servidor (só o hash do token), expiração, revogação no logout, papéis `ADMIN` e `USER`.
- `api/`: página de login mínima, logout, `/api/auth/me`, `/api/health`; middleware de sessão com negação por padrão (ADM-008) e CSRF (ADM-009).
- `ui/dash/`: Dash sobre a mesma instância FastAPI, três páginas, navegação, gateway.
- CLI: `db upgrade`, `db current`, `user create`, `serve` (com `--no-ui`).
- `deployment/`: `Containerfile` e `compose.yaml` (aplicação + PostgreSQL).
- Testes: 116 verdes contra PostgreSQL 16 (identidade, configuração, registry, senha e tokens, baterias de contrato de `ArtifactStorage` e `JobRunner`, migrações do zero e de volta, fluxo de autenticação, Dash protegido, arquitetura por imports, CLI). `ruff` limpo.
- Verificação manual sem container: `db upgrade`, `user create`, `serve`; num navegador (Chromium), login, as três telas e logout funcionaram, sem erro de console.

### Pendente
- Nada bloqueante. `Tracker` e `AnalyticsStore` têm só o contrato; as implementações e as baterias de teste entram na Fase 3, como previsto na seção 5.3.

### Limitações conhecidas
- **Podman Compose não foi executado.** O ambiente desta sessão não tem Podman nem um daemon de containers em execução. `Containerfile` e `compose.yaml` foram escritos e têm testes de coerência (serviços, caminho do build, senha fora do arquivo, usuário sem privilégios), mas o critério de aceite "a aplicação sobe com Podman Compose" **não está verificado**. Para verificar: `export LIPIDENCE_DB_PASSWORD=...; podman compose -f lipidence_modular/deployment/compose.yaml up --build`.
- As três páginas existem e são protegidas, mas ainda não têm função: cada uma diz isso na tela.
- O estado dos jobs vive na memória do processo; reiniciar a aplicação perde jobs em fila. O registro durável do experimento entra na Fase 3.
- O registry foi testado com componentes de teste; os manifestos reais chegam na Fase 3.
- Sessões expiradas ou revogadas ficam na tabela `sessions`; não há rotina de limpeza.

## Fase 2 — Importação assistida e Base Experimental

### Feito
- `data/importers/`: CSV, TSV, TXT e XLSX; detecção de codificação, delimitador, separador decimal (inclusive `;` com vírgula) e cabeçalho, sempre devolvida para confirmação.
- `data/mapping/`: papéis de coluna e sugestão automática (`Sample → sample_id`, `C18_2 → reference:C18:2`, cabeçalho numérico → coluna espectral, unidade lida do cabeçalho).
- `data/ingestion/`: caminho único de interpretação de espectros (layouts largo, longo e um arquivo por amostra) e de referências (formato longo e largo); tipo de sinal e unidade do eixo obrigatórios e nunca adivinhados; conversão cm⁻¹ → nm e R/T → absorbância só quando declaradas, com registro na proveniência.
- `data/validators/`: grade e espectro (portado do sistema atual).
- `data/reference/` + `config/parameters.yaml`: vocabulário controlado de parâmetros e unidades.
- Banco: migração `0002_experimental_base` (`samples`, `spectra`, `spectral_axes`, `reference_analyses`, `import_batches`, `mapping_templates`), com JSONB para metadados variáveis e origem por campo.
- `application/import_service.py`: upload com arquivo bruto e SHA-256, preview, confirmação, relatório, arquivo duplicado, templates, cadastro manual. `application/experimental_base_service.py`: contagens e consulta com filtros.
- API (`/api/imports`, `/api/templates`, `/api/base/*`, `/api/samples`, `/api/references`) e CLI (`import run`, `base summary`, `base samples`).
- Tela Base Experimental: importar (upload, mapeamento editável, declarações, preview com gráfico, confirmação), consultar (filtros por estudo, genótipo, lote e completude) e cadastro manual.
- Testes: 201 verdes (85 novos). Cobrem os três layouts e o arquivo combinado, paridade de vetor entre layouts e XLSX, contagens e linhas do relatório, identidade (`A001` + `A001` associam; `A001` + `A002` não), conflito de identificação com confirmação explícita, arquivo duplicado por hash, separador decimal com vírgula, preview sem gravação.
- Verificação manual num navegador: upload de arquivo combinado sintético (32 linhas), preview com 30 importados, 1 alerta e 1 rejeitado, gráfico dos espectros, confirmação e consulta; sem erro de console.

### Pendente
- Seção "Treinar modelos" da tela: pertence à Fase 3 (a tela diz isso).
- A paridade de ingestão entre base experimental e predição (INV-2) tem hoje um teste de paridade entre layouts; o teste do INV-2 propriamente dito (mesmo arquivo pelos dois caminhos) só pode existir quando a predição existir (Fase 5).

### Limitações conhecidas
- Formatos instrumentais (JCAMP-DX, SPA) não são lidos.
- O mapeamento é editado como texto na tabela; papel inválido é recusado pelo serviço com mensagem, mas não há lista suspensa de papéis.
- Templates podem ser salvos e listados pela API e usados na CLI (como arquivo de plano); a tela ainda não tem seletor de template.
- Upload pela tela passa pelo `dcc.Upload` (arquivo inteiro em base64 na memória do navegador): adequado a arquivos de laboratório, não a arquivos muito grandes. A API aceita até 200 MB.
- Lotes enviados e nunca confirmados (`STAGED`) e os seus arquivos brutos ficam guardados; não há rotina de limpeza.
- Metadado divergente em amostra já cadastrada gera alerta e mantém o valor existente; não há tela para editar metadados depois da importação.
- Não há exclusão de amostra, espectro ou referência pela aplicação.
- `fatty_acid_sum_check` do sistema atual não foi portado (depende da pendência P-13).
- `dash_table.DataTable` está marcado para sair dos componentes embutidos em versão principal futura do Dash (ADM-017).
- Todos os dados usados em testes e na verificação manual são sintéticos.

## Como rodar

```bash
python -m pip install -r lipidence_modular/requirements-dev.txt
python -m ruff check --config lipidence_modular/ruff.toml lipidence_modular
python -m pytest -c lipidence_modular/pytest.ini lipidence_modular
python -m lipidence_modular version
```

Com banco (testes de integração e aplicação):

```bash
export LIPIDENCE_TEST_DATABASE_URL=postgresql+psycopg2://<usuario>:<senha>@localhost:5432/lipidence_test
python -m pytest -c lipidence_modular/pytest.ini lipidence_modular

export LIPIDENCE_DATABASE_URL=postgresql+psycopg2://<usuario>:<senha>@localhost:5432/lipidence_modular
export LIPIDENCE_STORAGE_DIR=/caminho/para/artefatos
python -m lipidence_modular db upgrade
python -m lipidence_modular user create --username <nome> --role ADMIN
python -m lipidence_modular serve            # http://127.0.0.1:8000

# Importação pela CLI: sem --confirm mostra só o preview
python -m lipidence_modular import run --file dados.csv --kind combined --study ENSAIO-1 \
    --as-user <nome> --plan plano.yaml [--confirm]
python -m lipidence_modular base summary
```

Exemplo de `plano.yaml`:

```yaml
signal_type: absorbance        # absorbance | reflectance | transmittance
wavelength_unit: nm            # nm | cm-1
reference_units: {"C18:2": "%"}   # só para colunas sem unidade no cabeçalho
```
