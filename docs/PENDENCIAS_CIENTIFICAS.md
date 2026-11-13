# PENDENCIAS_CIENTIFICAS — decisões que cabem ao pesquisador

Regra do protocolo: decisão científica nunca é inventada pelo código. O valor provisório
indicado no prompt mestre é usado, marcado `PROVISORIO` na configuração e listado aqui.
Cada item só sai desta lista com a decisão do pesquisador registrada (valor, justificativa, data).

Legenda de estado: `ABERTO` · `DECIDIDO` (com data e justificativa).

## A. Valores provisórios em uso

| # | Item | Valor provisório | Onde é usado | Seção | Estado |
|---|------|------------------|--------------|-------|--------|
| P-01 | Chave de grupo padrão da partição | `genotype_id` quando existir, senão `sample_id` | `validation/` | 9.2 | ABERTO |
| P-02 | Fração de grupos no teste externo | ≈ 25% | `validation/` | 9.3 | ABERTO |
| P-03 | Limiares do domínio (T² e Q) | percentil 95 = limítrofe; 99 = fora | `ood/` | 12 | ABERTO |
| P-04 | Nível do intervalo de predição | 90% | `uncertainty/` | 12 | ABERTO |
| P-05 | Regra de decisão do ICQ | `p_max = 0,05`; `enrichment_min = 1,5` | `config/chem_windows/` | 13.2 | ABERTO |
| P-06 | Largura do bloco na permutação em blocos | a definir na Fase 6 (configurável) | `xai/permutation_blocks/` | 13.3 | ABERTO |
| P-07 | Faixas plausíveis por parâmetro | Só limites físicos em `config/parameters.yaml`: 0 a 100 para percentuais; ≥ 0, sem teto, para TBARS e PV. Nenhum limite empírico foi definido. Fora da faixa gera alerta, não rejeição | `data/ingestion/reference.py` | 8.6 | ABERTO |
| P-08 | Limiares de todas as regras de diagnóstico | a definir na Fase 6 em `config/diagnostics.yaml` | `diagnostics/` | 15.5 | ABERTO |
| P-09 | Critério de ativação do `CeleryJobRunner` | treino acima de "alguns minutos" ou mais de um usuário treinando | `jobs/` | 5.3 | ABERTO |
| P-10 | Tolerância por target para "% de predições dentro da tolerância" | nenhuma cadastrada; a métrica não é exibida | `prediction/` | 14 | ABERTO |
| P-11 | Tolerância numérica de reprodutibilidade (INV-8) | a declarar na Fase 3 | `core/provenance.py` | 4 | ABERTO |
| P-12 | Limiares de qualidade espectral | Herdados do sistema atual em `config/spectral_quality.yaml`: mínimo de 100 pontos; faixa NIR 700–2600 nm; absorbância entre −1 e 5; SNR mínimo 50; amplitude mínima 0,001; até 2% de pontos saturados. Erros rejeitam o espectro; avisos viram alerta | `data/validators/spectral_quality.py` | 8.5 | ABERTO |
| P-13 | Vocabulário de parâmetros: nomes canônicos e unidades | C16:0, C18:0, C18:1, C18:2, C18:3 em `%`; TBARS em `mg MDA/kg`; índice de peróxidos com o nome `PV` em `meq O2/kg`. Definir a base do percentual (% dos ácidos graxos totais ou g/100 g) e se há outros parâmetros | `config/parameters.yaml` | 8.6 | ABERTO |
| P-14 | Medidas repetidas da mesma amostra | Sem declaração, são rejeitadas (no arquivo: "sample_id duplicado"; na base: "já existe"). Só viram replicata com coluna de replicata ou com a declaração explícita no plano | `data/ingestion/`, `application/import_service.py` | 8.7, 9.1 | ABERTO |
| P-15 | Regra de normalização do `sample_id` | Aparar espaços, colapsar espaços internos, maiúsculas. `A001` e `A-001` são amostras diferentes | `data/identity/normalization.py` | 8.2 | ABERTO |
| P-16 | Conversão de reflectância/transmitância | Só quando declarada, com escala declarada (fração ou percentual): `A = log10(1/R)`. Sem declaração, o sinal é guardado como veio | `data/ingestion/spectra.py` | 8.5 | ABERTO |

## B. Janelas químicas herdadas (a conferir na fonte primária)

Origem: `backend/app/xai/xai_methods.py@e027e41`, listas `LIPID_BANDS` e `NON_LIPID_BANDS`.
O código de origem cita "Workman & Weyer (2012)" em um comentário, sem página nem DOI:
essa referência é `TODO_VERIFY` e nenhuma atribuição foi conferida. As janelas serão
migradas para `config/chem_windows/v1.yaml` na Fase 6, todas com `status: TODO_VERIFY` e
`frozen: false`; até a conferência, todo ICQ sai rotulado **EXPLORATÓRIO**.

Nenhuma atribuição foi corrigida. O que precisa de decisão:

### B.1 Sobreposições analito × confundidor

| Janela de analito | Janela de confundidor | Trecho comum (nm) |
|---|---|---|
| `CH2_combination` 1390–1430 | `water_1st_overtone` 1400–1450 | 1400–1430 |
| `peroxide` 2080–2120 | `cellulose` 2100–2150 | 2100–2120 |
| `cis_double_bond` 2120–2180 | `cellulose` 2100–2150 | 2120–2150 |
| `aldehyde` 2220–2280 | `starch_combination` 2270–2290 | 2270–2280 |

A terceira linha não consta da lista do prompt mestre (seção 13.1); foi encontrada na leitura
do código. Pela definição da seção 13.4, pontos em analito ∩ confundidor saem de `A(t)` e são
reportados à parte como ambíguos. Decidir se os limites devem ser redesenhados.

### B.2 Sobreposições analito × analito

| Janelas | Trecho comum (nm) | Observação |
|---|---|---|
| `CH_olefinic` 1160–1180 × `CH2_1st_overtone` 1170–1200 | 1170–1180 | |
| `CH2_1st_overtone` 1170–1200 × `CH3_1st_overtone` 1190–1220 | 1190–1200 | |
| `carbonyl_combination` 2050–2100 × `peroxide` 2080–2120 | 2080–2100 | |
| `polyunsaturated` 2200–2250 × `aldehyde` 2220–2280 | 2220–2250 | |
| `palmitic_CH2` 1725–1745 dentro de `CH_1st_overtone` 1680–1760 | 1725–1745 | janela contida em outra |

Importam quando as janelas forem especializadas por target: o mesmo ponto pode contar para
targets diferentes.

### B.3 Rótulos a conferir

| Janela | Rótulo no código de origem | O que conferir |
|---|---|---|
| `CH3_1st_overtone` 1190–1220, `CH2_1st_overtone` 1170–1200, `CH_olefinic` 1160–1180 | "1st overtone C-H" | A região de ~1200 nm está descrita como 1º sobretom de C-H, na mesma lista em que 1680–1760 nm também é "1st overtone". Conferir a ordem do sobretom na fonte primária |
| `polyunsaturated` 2200–2250 | "Bis-alílico", C18:2 e C18:3 | Atribuição e limites |
| `peroxide` 2080–2120 | "O-O-H", hidroperóxidos | Atribuição e limites |
| `aldehyde` 2220–2280 | "CHO", oxidação secundária, TBARS | Atribuição; relação com TBARS |
| `cellulose` 2100–2150 | grupo "C-O", categoria carboidrato | Atribuição |
| `starch_combination` 2270–2290 | "C-O-C" | Atribuição |
| `lipid_total` 2440–2480 | "C-H combinação" | Atribuição; muitos instrumentos não cobrem essa faixa |

### B.4 Especificidade por target

O código de origem usa a mesma máscara lipídica para todos os targets. A seção 13 pede
`targets` por janela. Não há, no código atual, mapeamento janela → target além do texto livre
`relevance_fatty_acids` ("C18:1 oleico", "C18:2, C18:3", "C16:0 palmítico", "Oxidação
primária", "Oxidação secundária"). O pesquisador precisa definir, para cada target (C16:0,
C18:0, C18:1, C18:2, C18:3, TBARS, índice de peróxidos), quais janelas são de analito.

## C. Referências bibliográficas a conferir (`TODO_VERIFY`)

Nenhuma referência foi conferida na fonte primária até aqui. A lista cresce a cada manifesto.

| # | Onde será citada | O que buscar |
|---|---|---|
| R-01 | `config/chem_windows/` | Fonte primária das atribuições de banda NIR (o código atual menciona "Workman & Weyer (2012)" sem página): título completo, edição, páginas das tabelas de atribuição |
