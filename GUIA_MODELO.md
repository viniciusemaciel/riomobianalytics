# Guia de Treinamento do Modelo — RioMobiAnalytics

Companheiro do notebook `modelo-treinamento.ipynb`. Cada seção corresponde a uma célula do notebook, na mesma ordem.

**Como usar**: leia a seção, entenda o "por quê", olhe a sintaxe recomendada, tente escrever o código. Se travar, releia. Não pule os *checkpoints* — eles pegam erros que só aparecem depois.

**Contexto**: temos um dataset em `data/model_dataset.parquet` com uma linha por (parada, mês). Cada linha tem features estáticas da parada, features dinâmicas de reclamações do 1746 defasadas, features temporais brutas (`mes` como int 1-12 e `ano`), e um target binário `y` que vale 1 se houve ≥1 tiroteio dentro de 500m da parada no mês.

**Nota sobre `mes`**: fica salvo no parquet como inteiro 1-12. A codificação cíclica (`mes_sin`, `mes_cos`) é decisão de modelagem — vive neste notebook, não no pré-processamento. Ver seção 7.

**Meta**: treinar três modelos supervisionados (regressão logística, XGBoost, MLP), comparar via AUC-ROC e Precision@K, escolher um.

**Regras invioláveis**:

1. **Zero leakage temporal**: nenhuma informação do futuro pode influenciar o treino. Isso condiciona split, scaling e cross-validation.
2. **`fit` só no treino**: scalers, imputers e modelos aprendem parâmetros apenas com dados do treino. Val e teste só usam `transform` / `predict`.
3. **Métrica primária é AUC-ROC**, não accuracy. Dataset é desbalanceado (~15% positivo com raio 500m) e accuracy vira "acertar todos os zeros e dizer que o modelo é ótimo".

---

## 1. Leitura do parquet

**Por que**: carregar o dataset. Parquet é ~10× mais rápido que CSV para leitura e preserva tipos automaticamente.

**Como**:
- `pd.read_parquet(caminho)` — retorna DataFrame direto.
- Coluna `ano_mes` foi salva como string (Parquet não aceita `Period` nativamente). Converter de volta para `PeriodIndex` no primeiro uso: `df['ano_mes'] = pd.PeriodIndex(df['ano_mes'], freq='M')`.

**Armadilha**: se esquecer de converter `ano_mes`, comparações tipo `df['ano_mes'] < '2024-01'` funcionam por sorte (compara strings lexicograficamente e coincide com ordem temporal para formato `YYYY-MM`), mas outras operações vão dar tipo estranho.

**Checkpoint**: `df.shape` deve dar aproximadamente **(385 000, 18)**. Se der muito diferente, o dataset foi gerado errado.

---

## 2. Inspeção rápida

**Por que**: antes de treinar qualquer coisa, entender o que tem. Serve para pegar bugs do pré-processamento e ter uma cara do que a banca vai ver.

**Como**:
- `df.head()` — primeiras linhas.
- `df.info()` — tipos e memória.
- `df['y'].value_counts(normalize=True)` — proporção do target. Deve dar ~0.85 / 0.15.
- `df.groupby('ano_mes')['y'].mean()` — proporção de positivos por mês. Deve ser relativamente estável.

**O que procurar**:
- Nulos em qualquer coluna → problema no pré-processamento, voltar e corrigir.
- Distribuição do target muito diferente do esperado → raio ou filtro do Fogo Cruzado errado.
- `describe()` das features de contagem com `max` absurdamente alto → outlier extremo, considerar winsorização.

---

## 3. Análise exploratória (EDA)

**Por que**: antes de qualquer decisão de modelagem, precisa saber com o que você está lidando. EDA pega bugs sutis no pré-processamento, valida hipóteses e informa expectativa de performance. Cinco análises cobrem o essencial.

**Regra geral**: EDA feita **no dataset inteiro**, antes do split. Não é leakage — você não está aprendendo parâmetros, só olhando distribuições.

**Boilerplate para todas as células** (importar no topo do notebook se ainda não estiver):

```python
import matplotlib.pyplot as plt
import seaborn as sns  # opcional, mas ajuda muito nos heatmaps e boxplots
```

---

### EDA 1 — Distribuição temporal do target

**Pergunta**: a taxa de tiroteio por mês é estável ao longo dos 5 anos?

**Por que importa**: se a taxa cai (ou sobe) muito ao longo do tempo, isso é *distribution shift* — o modelo treinado em 2021-2023 vai encontrar um cenário diferente em 2025. Vira insight para o paper e ajusta expectativas de AUC no teste.

**Sintaxe**:

```python
taxa_por_mes = df.groupby('ano_mes')['y'].mean()

fig, ax = plt.subplots(figsize=(12, 4))
taxa_por_mes.plot(ax=ax, marker='o')
ax.set_ylabel('Proporção de paradas com tiroteio')
ax.set_xlabel('Mês')
ax.set_title('Taxa mensal de tiroteios próximos a paradas (2021-2025)')
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()
```

**Bonus — separar por período do split** (pra ver se treino/val/teste têm médias parecidas):

```python
for label, color in [('Treino (<2024)', 'C0'), ('Val (2024)', 'C1'), ('Teste (2025)', 'C2')]:
    # filtrar e plotar cada faixa
    pass
```

**O que procurar**: linha razoavelmente estável ou queda contínua. Se aparecer um salto abrupto em algum mês, tem bug no pré-processamento.

---

### EDA 2 — Distribuição espacial do target

**Pergunta**: onde ficam as paradas com maior taxa de meses positivos?

**Por que importa**: se a concentração for muito localizada (uma zona só), o modelo tem "gol de placa" via lat/lon (spatial autocorrelation). Se estiver espalhado, a tarefa é genuinamente difícil.

**Sintaxe**:

```python
# proporção de meses positivos por parada
prop_por_parada = df.groupby('stop_id').agg(
    lat=('lat', 'first'),
    lon=('lon', 'first'),
    prop_positivo=('y', 'mean'),
    n_meses=('y', 'count'),
).reset_index()

fig, ax = plt.subplots(figsize=(10, 10))
sc = ax.scatter(
    prop_por_parada['lon'], prop_por_parada['lat'],
    c=prop_por_parada['prop_positivo'],
    cmap='YlOrRd', s=6, alpha=0.7,
)
plt.colorbar(sc, ax=ax, label='Proporção de meses com tiroteio')
ax.set_xlabel('Longitude')
ax.set_ylabel('Latitude')
ax.set_title('Concentração geográfica de tiroteios por parada')
plt.tight_layout()
plt.show()
```

**O que procurar**: cluster óbvio (Zona Norte, Complexo do Alemão, Maré, etc.) confirma o fenômeno real. Se estiver perfeitamente uniforme, alguma coisa está errada.

---

### EDA 3 — Matriz de correlação (features + y)

**Pergunta**: features estão correlacionadas entre si? Alguma já correlaciona diretamente com o target?

**Por que importa**:
- **Multicolinearidade** entre features (ex: `num_reclamacoes_6m` vs `num_reclamacoes_12m`, obviamente correlacionadas) prejudica a regressão logística — coeficientes ficam instáveis e não-interpretáveis.
- Correlação com `y` dá pista do que o modelo pode aprender. Se **nenhuma** feature correlacionar com `y`, prepare-se para AUC baixa.

**Sintaxe**:

```python
# só numéricas + y (dropa stop_id e ano_mes)
num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
corr = df[num_cols].corr()

fig, ax = plt.subplots(figsize=(12, 10))
sns.heatmap(
    corr, annot=True, fmt='.2f', cmap='RdBu_r',
    center=0, vmin=-1, vmax=1, square=True, ax=ax,
    cbar_kws={'label': 'Correlação de Pearson'},
)
ax.set_title('Correlação entre features numéricas e target')
plt.tight_layout()
plt.show()
```

**O que procurar**:
- Features de reclamação da mesma categoria em janelas próximas devem ter correlação alta entre si (`_3m` vs `_6m` provavelmente > 0.8). Normal.
- Correlação com `y` idealmente entre 0.1 e 0.4 para ser sinal aproveitável. Muito baixa (< 0.05) sinaliza feature sem informação. Muito alta (> 0.7) desconfia — pode ser leakage.

---

### EDA 4 — Distribuição das features de reclamação

**Pergunta**: qual a forma da distribuição das contagens? Cauda longa? Muitos zeros?

**Por que importa**: confirma (ou desafia) a decisão de aplicar `log1p`. Também mostra se algumas features são majoritariamente zero, o que reduz seu poder preditivo.

**Sintaxe**:

```python
count_cols = [c for c in df.columns if c.startswith('num_reclamacoes_') and c.endswith('_12m')]

fig, axes = plt.subplots(1, len(count_cols), figsize=(5 * len(count_cols), 4))
for ax, col in zip(axes, count_cols):
    df[col].hist(bins=50, ax=ax, edgecolor='black', alpha=0.7)
    ax.set_title(col)
    ax.set_yscale('log')  # log no eixo Y é essencial — sem isso só se vê o pico em 0
    ax.set_xlabel('Contagem')
    ax.set_ylabel('Frequência (log)')
plt.tight_layout()
plt.show()

# alternativa: box plot para ver quartis e outliers
fig, ax = plt.subplots(figsize=(10, 4))
df[count_cols].boxplot(ax=ax)
ax.set_yscale('log')  # mesma coisa
ax.set_title('Distribuição das features de contagem (12 meses)')
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()
```

**O que procurar**: distribuição fortemente enviesada à direita (a maioria em zero, cauda longa). Isso **justifica** o `log1p` da §5. Se por acaso a distribuição for razoavelmente simétrica, log1p ainda não atrapalha mas é menos necessário.

---

### EDA 5 — Feature vs target (separação de classes)

**Pergunta**: paradas-mês com `y=1` têm de fato mais reclamações que as com `y=0`?

**Por que importa**: se as distribuições forem indistinguíveis, o modelo não tem sinal para aprender e AUC vai ser próximo do baseline. Se separar bem, o problema é tratável.

**Sintaxe**:

```python
feature_de_interesse = 'num_reclamacoes_seguranca_12m'

fig, axes = plt.subplots(1, 2, figsize=(14, 4))

# boxplot
df.boxplot(column=feature_de_interesse, by='y', ax=axes[0])
axes[0].set_yscale('log')
axes[0].set_title(f'{feature_de_interesse} por y')
axes[0].set_xlabel('y')

# distribuição sobreposta (KDE)
for classe, cor in [(0, 'C0'), (1, 'C3')]:
    sub = df[df['y'] == classe][feature_de_interesse]
    sub.plot(kind='kde', ax=axes[1], label=f'y={classe}', color=cor)
axes[1].set_title(f'Distribuição de {feature_de_interesse}')
axes[1].set_xlabel(feature_de_interesse)
axes[1].legend()

plt.suptitle('')  # remove o "Boxplot grouped by y" que o pandas põe automaticamente
plt.tight_layout()
plt.show()
```

**Bonus — comparar médias formalmente**:

```python
for col in count_cols:
    mean_0 = df[df['y'] == 0][col].mean()
    mean_1 = df[df['y'] == 1][col].mean()
    print(f'{col:35s}  y=0: {mean_0:6.2f}   y=1: {mean_1:6.2f}   razão: {mean_1/max(mean_0, 0.001):5.2f}x')
```

**O que procurar**: mediana e caudas visualmente diferentes entre `y=0` e `y=1`. Razão de médias > 1.5x indica sinal. Se as duas distribuições estão coladas, a feature não vai ajudar sozinha (pode ainda ajudar em interação, mas é sinal fraco).

---

## 4. Split temporal

**Por que**: dados temporais **exigem** split cronológico. Split aleatório vaza o futuro pro passado — o modelo aprende que "em dezembro sempre acontece isso" com dados de dezembro no treino e testa em dezembro. Isso não é generalização, é memorização.

**Como**:
- Treino: `df[df['ano_mes'] < '2024-01']` (2021-01 a 2023-12, ~36 meses)
- Validação: `df[(df['ano_mes'] >= '2024-01') & (df['ano_mes'] < '2025-01')]` (2024 inteiro, 12 meses)
- Teste: `df[df['ano_mes'] >= '2025-01']` (2025 inteiro, 12 meses)

**Regra de ouro**: **teste é intocável até o final**. Só é usado depois que o modelo campeão foi escolhido pela validação. Se você olhar performance no teste antes de escolher o modelo, você contaminou o teste (pesquisador humano fica influenciado pelo número — vira leakage humano).

**Armadilha**: `ano_mes` como `PeriodIndex` permite comparar direto com string, mas `PeriodIndex` compara em ordem — só funciona se a string estiver no formato `YYYY-MM` (ISO). Nunca `01/2024`.

**Checkpoint**: os três splits somados devem dar exatamente `len(df)`. Se sobrar linha, provavelmente há mês fora do intervalo (bug no pré-processamento). Se faltar, filtro está errado.

---

## 5. Separar chaves e target das features

**Por que**: `stop_id` e `ano_mes` são identificadores, não sinais. Passá-los pro modelo como features é péssimo — o modelo pode "aprender" que a parada X é sempre risco alto (spatial autocorrelation) sem generalizar. E `stop_id` categórico com ~6400 valores explode qualquer modelo linear.

Também precisa guardar `stop_id` e `ano_mes` **fora** do X, para depois juntar predições com a identificação.

**Como**:
- Identificar colunas de feature: tudo que não é `stop_id`, `ano_mes` ou `y`.
- `X_train = train_df[feature_cols]`, `y_train = train_df['y']`.
- Guardar `train_df[['stop_id', 'ano_mes']]` separado para análises posteriores.

**Repetir para val e teste**, com os mesmos `feature_cols`.

**Armadilha**: se o pré-processamento incluiu uma coluna auxiliar tipo `y_lag1_500m` (para o baseline), essa também precisa sair das features do modelo. Ela é usada só na célula do baseline.

**Checkpoint**: `X_train.columns.tolist()` deve dar entre 15 e 17 colunas (features numéricas puras). Nada de `object` ou `string`.

---

## 6. `log1p` nas features de contagem

**Por que**: features `num_reclamacoes_*` têm distribuição de cauda longa. A maioria das paradas tem 0-5 reclamações, algumas têm centenas. Sem transformar:

- **Regressão logística**: pesa cada unidade igualmente (a 100ª reclamação vale o mesmo que a 1ª), o que não faz sentido — o efeito marginal cai com o volume.
- **MLP**: as ativações saturam (`sigmoid`/`tanh` viram 0 ou 1) quando entradas são muito grandes.
- **XGBoost**: indiferente (splits em quantis).

`log1p(x) = log(1 + x)` é ideal: comprime valores altos, preserva zeros (log(1)=0), é monotônica (não muda a ordem entre paradas).

**Como**:
- Identificar colunas: `count_cols = [c for c in X_train.columns if c.startswith('num_reclamacoes_')]`.
- Aplicar em cada split: `X_train[count_cols] = np.log1p(X_train[count_cols])`.
- **É segura antes do split** porque não tem parâmetro aprendido — mesma função aplicada em cada linha.

**Armadilha**: aplicar `log1p` em features que **não são contagens** (lat, pagerank, mes, ano) vai corromper. Filtre estritamente pelo prefixo `num_reclamacoes_`.

**Checkpoint**: `X_train[count_cols].max()` deve cair de centenas para valores de ordem 5-7 (`log(500) ≈ 6.2`).

---

## 7. Codificação cíclica do mês (`mes_sin`, `mes_cos`)

**Por que**: o mês é uma variável **cíclica** — dezembro (12) e janeiro (1) são vizinhos no calendário, mas se você joga `mes = 1, 2, ..., 12` cru no modelo, ele enxerga uma distância enorme (12 - 1 = 11) entre eles. Isso quebra em dois lugares:

1. **Descontinuidade artificial dez→jan**. O modelo perde a conexão entre meses vizinhos no fim do ano.
2. **Monotonia forçada**. Coeficiente positivo pra `mes` implica "risco aumenta linearmente de jan a dez", o que não é como sazonalidade funciona.

Solução: mapear cada mês num ponto num círculo unitário.

```
mes_sin = sin(2π × mes / 12)
mes_cos = cos(2π × mes / 12)
```

Aí janeiro fica em `(0.5, 0.87)` e dezembro em `(0.0, 1.0)` — próximos no espaço, como deveriam ser. Precisa dos **dois** (sin e cos) para identificar cada mês unicamente (seno de janeiro = seno de maio, então sozinho não basta).

**Como**:
- Após o `log1p`, antes do `StandardScaler`, aplicar em X_train, X_val e X_test:
  - `X['mes_sin'] = np.sin(2 * np.pi * X['mes'] / 12)`
  - `X['mes_cos'] = np.cos(2 * np.pi * X['mes'] / 12)`
  - `X = X.drop(columns=['mes'])` — a coluna original deixa de ser feature.
- Transformação é pontual (sem parâmetro aprendido), então pode aplicar em cada split independentemente.

**Impacto por modelo**:
- **Logística e MLP**: essencial. Sem cíclico, sazonalidade não é aprendida direito.
- **XGBoost**: pouco importa. Árvores conseguem partir `mes < 4 OR mes > 10` sozinhas. Ainda assim, aplicar não atrapalha e mantém pipeline único.

**Armadilha**: não esquecer de dropar a coluna `mes` depois de criar sin/cos. Se deixar as três (`mes`, `mes_sin`, `mes_cos`), a `mes` cria ambiguidade — o modelo pode até se distrair aprendendo do inteiro em vez do cíclico.

**Checkpoint**: `X_train['mes_sin'].min()` ≈ -1, `X_train['mes_sin'].max()` ≈ 1. Idem para `mes_cos`. Coluna `mes` não deve mais existir em `X_train.columns`.

---

## 8. `StandardScaler`

**Por que**: features estão em escalas absurdamente diferentes:

- `lat` ≈ -22, `lon` ≈ -43
- `pagerank` ≈ 10⁻⁴
- `num_reclamacoes_12m` ≈ 0-6 (após log1p)
- `ano` ≈ 2021-2025

**Regressão logística**: o solver (L-BFGS por padrão) converge com dificuldade se features têm escalas muito diferentes. Coeficientes viram incomparáveis (o coef de `ano` seria minúsculo porque o valor é enorme; o de `pagerank` seria gigante).

**MLP**: obrigatório. Sem scaling, gradientes explodem/somem na primeira camada.

**XGBoost**: não precisa, mas **não atrapalha**. Splits são invariantes a transformação monotônica.

**Como**:
- `from sklearn.preprocessing import StandardScaler`
- `scaler = StandardScaler()`
- `X_train_scaled = scaler.fit_transform(X_train)` — **`fit_transform` só no treino**.
- `X_val_scaled = scaler.transform(X_val)` — **`transform` no val**.
- `X_test_scaled = scaler.transform(X_test)` — **`transform` no teste**.

**Armadilha capital**: se você fizer `scaler.fit_transform(X)` no dataset inteiro **antes** do split, a média/desvio do teste vaza pro treino. Erro clássico, infla AUC 1-3%, banca pega se cavar.

**Outra armadilha**: `fit_transform` devolve um `numpy.ndarray`, não `DataFrame`. Você perde nomes de coluna. Duas opções:
- Aceitar array (mais rápido, funciona pra sklearn).
- Reembrulhar: `pd.DataFrame(scaled, columns=X_train.columns, index=X_train.index)` — útil se quiser inspecionar depois.

**Salvar o scaler** com `joblib.dump(scaler, 'scaler.joblib')`. Vai precisar dele para predições futuras.

**Checkpoint**: `X_train_scaled.mean(axis=0)` deve dar valores muito próximos de 0 (10⁻¹⁶ é normal, ponto flutuante). `X_train_scaled.std(axis=0)` deve dar aproximadamente 1. Isso confirma que o fit funcionou.

---

## 9. Baseline heurístico

**Por que**: é o **teto trivial**. A pergunta que ele responde: "o modelo ML aprende algo além do óbvio?" O óbvio aqui é *persistência espacial*: se houve tiroteio no mês anterior no raio, provavelmente vai ter no próximo. Se seu modelo sofisticado não bate esse baseline, ele não aprendeu nada útil.

**Sem baseline no paper**, a banca pergunta: "quão bom é 0.82 de AUC? Um bebê consegue?". Com baseline, você mostra "modelo tem 0.82 vs baseline 0.74 — extraímos 8 pontos de sinal via features indiretas".

**Como**:
- Precisa da coluna `y_lag1_500m` (target defasado 1 mês). Se ela foi salva no pré-processamento, ótimo. Se não, calcular:
  - Ordenar por (stop_id, ano_mes).
  - Para cada parada, `y_lag1 = grupo['y'].shift(1)`.
  - Primeiro mês de cada parada fica NaN → preencher com 0 (ou remover, mas remover perde dado).
- **Predição do baseline**: `y_pred_baseline = y_lag1`.
- Avaliar com as mesmas métricas do modelo (AUC-ROC, Precision@K, matriz de confusão).

**Armadilha**: `y_lag1_500m` é **feature proibida** para o modelo ML (você quis explicitamente que o modelo não use histórico de tiroteio). Ela vive só para o baseline. Não passe para o `X_train` das seções seguintes.

**Sintaxe**:
- `from sklearn.metrics import roc_auc_score, confusion_matrix, precision_score, recall_score`
- `roc_auc_score(y_true, y_pred_prob)` — o baseline é binário, então `y_pred_prob = y_pred_baseline`.

**Checkpoint**: AUC do baseline deve dar entre 0.65 e 0.80 — não é baixo, mas também não é o teto. Se der acima de 0.85, revisar leakage (algo está errado).

---

## 10. Grid search da logística

**Por que**: hiperparâmetros importam. `C` (inverso da regularização) e `penalty` (L1 vs L2) mudam radicalmente o modelo. Grid search testa combinações e escolhe pela métrica no validation.

**Regra crítica**: `cv` **precisa ser temporal** (`TimeSeriesSplit`) ou usar o próprio val set como split fixo. Nunca `KFold` aleatório.

**Como (opção A — CV temporal dentro do treino)**:
- `from sklearn.model_selection import GridSearchCV, TimeSeriesSplit`
- `tscv = TimeSeriesSplit(n_splits=5)` — 5 folds sequenciais dentro do X_train.
- **Requer** que X_train esteja ordenado por `ano_mes`. Ordenar antes.
- `param_grid = {'C': [0.01, 0.1, 1, 10], 'penalty': ['l1', 'l2']}`.
- Para `penalty='l1'` funcionar precisa `solver='liblinear'` ou `solver='saga'` — default `lbfgs` não aceita L1.
- `gs = GridSearchCV(LogisticRegression(class_weight='balanced', max_iter=1000), param_grid, cv=tscv, scoring='roc_auc', n_jobs=-1)`
- `gs.fit(X_train_scaled, y_train_ordenado)`
- Melhores params: `gs.best_params_`. Melhor score: `gs.best_score_`. Melhor modelo: `gs.best_estimator_`.

**Como (opção B — validação fixa mais simples)**:
- Concatenar X_train + X_val em um só X.
- Criar índices: treino = primeiros N (do X_train), val = os N seguintes (do X_val).
- `cv = [(idx_train, idx_val)]`.
- `GridSearchCV(..., cv=cv, ...)`.

Opção B é mais rápida e reflete melhor o setup real (você tem um val definido); opção A é mais robusta estatisticamente. Escolha uma e documente.

**Grid sugerido para começar**:
```
C: [0.01, 0.1, 1, 10, 100]
penalty: ['l2']  # começar simples; adicionar l1 depois se quiser
```

**Armadilha**: se o grid demorar mais de 10 minutos, reduza. Logística treina em segundos, grid de 5×1 = 5 fits × 5 folds = 25 fits ≈ 1 minuto. Se estourar isso, algo está errado.

**Checkpoint**: `gs.best_score_` deve ser próximo da AUC que a logística sozinha vai dar depois. Se for muito diferente (>0.05), o grid está avaliando errado.

---

## 11. Treino da logística

**Por que**: com os melhores hiperparâmetros já achados, retreinar no X_train inteiro (agora sem o CV interno cortando pedaços).

**Como**:
- `from sklearn.linear_model import LogisticRegression`
- `model = LogisticRegression(**gs.best_params_, class_weight='balanced', max_iter=1000)` — expande dict de best_params.
- `model.fit(X_train_scaled, y_train)`.

**Sobre `class_weight='balanced'`**: dataset é desbalanceado (~85/15). Sem esse parâmetro, a logística prevê majoritariamente 0 porque isso já dá 85% de accuracy. `'balanced'` ajusta o loss para dar peso maior à classe minoritária.

**Armadilha**: `max_iter=1000` (default é 100) evita warnings de "não convergiu". Se ver `ConvergenceWarning`, aumenta mais.

**Checkpoint**: `model.coef_.shape` deve ser `(1, n_features)`.

---

## 12. Avaliação da logística no val

**Por que**: comparar contra baseline. É aqui que a decisão "logística vale a pena?" é feita.

**Como**:
- `y_pred_prob = model.predict_proba(X_val_scaled)[:, 1]` — probabilidades da classe positiva.
- `y_pred_class = model.predict(X_val_scaled)` — classes 0/1 (threshold 0.5).
- **Métricas**:
  - `roc_auc_score(y_val, y_pred_prob)` — AUC-ROC.
  - Precision@100: pegar as 100 predições com maior probabilidade e ver qual fração é realmente positiva. Código: ordenar y_pred_prob decrescente, pegar top 100, computar `y_val[top100].mean()`.
  - `confusion_matrix(y_val, y_pred_class)` — matriz 2×2.
  - `classification_report(y_val, y_pred_class)` — precision/recall/f1 por classe.

**Por que Precision@K, não só accuracy**: cenário de uso é "as 100 paradas com maior risco previsto vão receber patrulhamento extra — quantas de fato tiveram tiroteio?". Isso é Precision@100. Accuracy é irrelevante aqui (você não vai ter recurso para investir em 90% das paradas).

**Armadilha**: `predict_proba` retorna matriz `(n, 2)` — colunas 0 e 1 são para classes 0 e 1. Precisa `[:, 1]` para pegar probabilidade da positiva. Se pegar `[:, 0]`, o AUC vai dar `1 - AUC_real` (invertido).

**Checkpoint**: AUC da logística deve ficar entre 0.75 e 0.85. Se for muito próxima do baseline, o modelo linear não está extraindo sinal — talvez log1p ajude mais, ou features precisem revisão.

---

## 13. Análise dos coeficientes da logística

**Por que**: única virtude real da logística é interpretabilidade. Os coeficientes dizem, para cada feature, quanto ela aumenta ou diminui o log-odds do target.

**Como**:
- `coef_df = pd.DataFrame({'feature': feature_cols, 'coef': model.coef_[0]}).sort_values('coef', ascending=False)`
- Como features foram scaled (média 0, std 1), os coeficientes são **diretamente comparáveis**. O maior em módulo é o mais influente.
- Sinal positivo: aumenta a probabilidade de tiroteio. Sinal negativo: diminui.

**Interpretação para o paper**: um coef 0.3 em `num_reclamacoes_seguranca_12m` (após log1p e scaling) significa que "um aumento de 1 desvio padrão nessa feature aumenta o log-odds em 0.3". Não é interpretável em unidades naturais, mas o **ranking relativo** é a informação útil.

**Se `penalty='l1'` foi escolhido**: alguns coeficientes vão dar exatamente 0 — L1 faz seleção de feature. Vale reportar quais foram zeradas.

---

## 14. Grid search do XGBoost

**Por que**: XGBoost tem muitos hiperparâmetros e é sensível a eles. Deixar no default é subestimar o modelo.

**Espaço de busca sugerido** (comece pequeno, expanda se der tempo):
```
n_estimators: [100, 300, 500]
max_depth: [3, 5, 7]
learning_rate: [0.05, 0.1]
subsample: [0.8, 1.0]
```

São 3×3×2×2 = 36 combinações. Com CV temporal de 5 folds, isso é 180 fits. XGBoost treina rápido, mas ainda pode levar 10-30 minutos. Se apertar o tempo, reduzir para `n_estimators: [300]` e `subsample: [1.0]`.

**Como**:
- `from xgboost import XGBClassifier`
- Instalar via `pip install xgboost` se ainda não tiver.
- Similar à logística: `GridSearchCV(XGBClassifier(...), param_grid, cv=tscv, scoring='roc_auc', n_jobs=-1)`.
- **Importante**: passar `scale_pos_weight = (n_negativos / n_positivos)` calculado do treino — equivalente ao `class_weight='balanced'` da logística.
- `use_label_encoder=False, eval_metric='auc'` para evitar warnings.

**Armadilha**: XGBoost não precisa de scaling, mas usá-lo com dataset já scaled **não atrapalha**. Não desfaça o scaling só para o XGBoost — mantenha consistência.

**Sobre early stopping**: pode ser usado dentro do fit do best_estimator (não do grid). Dentro do grid é complicado porque não tem val fixo.

---

## 15. Treino do XGBoost

Igual à logística: expandir `gs.best_params_`, criar modelo, treinar em `X_train_scaled`.

**Extra opcional**: `eval_set=[(X_val_scaled, y_val)]` + `early_stopping_rounds=20` — para se o modelo não melhorar em 20 rounds no val, parar. Salva tempo se `n_estimators` estiver alto.

---

## 16. Avaliação do XGBoost no val

Idêntica à da logística. Mesmas métricas, mesmo formato.

**Expectativa**: XGBoost deve superar a logística (talvez 3-5 pontos de AUC). Se não superar, algo está errado — provavelmente hiperparâmetros ruins ou dataset tem estrutura muito linear (o que seria informação importante para o paper).

---

## 17. Feature importance do XGBoost

**Por que**: XGBoost dá importância de feature nativamente. É a resposta para "quais features o modelo mais usou?".

**Como**:
- `model.feature_importances_` — array com importância por feature (soma = 1).
- `pd.DataFrame({'feature': feature_cols, 'importance': model.feature_importances_}).sort_values('importance', ascending=False)`.

**Diferença crítica entre logística e XGBoost**: coeficiente da logística tem **sinal e magnitude**; importância do XGBoost tem só magnitude (mas mede uso real do modelo, não linearidade assumida).

**Opcional — SHAP**: `pip install shap` → `shap.TreeExplainer(model).shap_values(X_val_scaled)`. Dá contribuição por feature por observação — pode mostrar interações não-lineares que o feature importance nativo esconde. Se der tempo, incluir; é bonito no paper.

**Armadilha**: `feature_importances_` de XGBoost tem três formas (`gain`, `weight`, `cover`) — o default é `gain`, que é a mais interpretável. Documente qual usou.

---

## 18. Grid search do MLP

**Por que**: MLP tem hiperparâmetros de arquitetura (número/tamanho de camadas) e otimização (learning rate, regularização). Grid search é essencial porque erros aqui são caros.

**Espaço de busca sugerido**:
```
hidden_layer_sizes: [(32,), (64,), (32, 16), (64, 32)]
alpha: [0.0001, 0.001, 0.01]   # regularização L2
learning_rate_init: [0.001, 0.01]
```

São 4×3×2 = 24 combinações. MLP treina mais lento que XGBoost — pode levar 30-60 minutos. Se apertar, reduzir hidden_layer_sizes para 2 opções.

**Como**:
- `from sklearn.neural_network import MLPClassifier`
- `MLPClassifier(early_stopping=True, validation_fraction=0.1, random_state=42, max_iter=200)`.
- **early_stopping=True** é crítico — MLP overfitta rápido; sem isso pode treinar 200 épocas sem melhorar.
- `class_weight` não existe no MLPClassifier (limitação do sklearn). Duas alternativas:
  - **Sampling**: oversampling da classe minoritária no treino (via `imblearn.RandomOverSampler`). Complica o pipeline.
  - **Aceitar viés**: rodar sem balanceamento e ver o resultado. Provável que MLP puxe para prever 0. Se performance ficar ruim, tentar sampling.
- Para o guia, comece **sem sampling**. Se AUC ficar muito baixa, aí sim adicionar.

**Armadilha da reprodutibilidade**: `random_state` inicializa pesos aleatoriamente. Sem fixar, cada rodada dá resultado diferente. Sempre passar `random_state=42` (ou qualquer número fixo).

---

## 19. Treino do MLP

Idêntico à logística e XGBoost.

**Extra**: monitorar `model.loss_curve_` — plotar em gráfico ajuda a ver se o modelo convergiu ou ficou instável.

**Se aparecer `ConvergenceWarning`**: aumentar `max_iter` (ex: 500) e treinar de novo.

---

## 20. Avaliação do MLP no val

Idêntica.

**Expectativa**: MLP tipicamente **empata com XGBoost** ou fica ligeiramente atrás em dados tabulares. Este é o achado esperado do paper (Shwartz-Ziv & Armon, 2022: *Tabular Data: Deep Learning is Not All You Need*). Se der isso, é vitória interpretativa, não fracasso.

**Se MLP ficar muito abaixo**: provavelmente falta scaling (voltar e conferir) ou dataset é pequeno demais para redes neurais (MLP é sensível a tamanho de dataset).

---

## 21. Tabela comparativa no val

**Por que**: o paper precisa dessa tabela. É a evidência quantitativa da comparação.

**Formato sugerido**:

| Modelo | AUC-ROC | Precision@100 | Recall@100 | Tempo de treino |
|---|---|---|---|---|
| Baseline (persistência) | 0.7X | 0.XX | 0.XX | <1s |
| Logística | 0.7X | 0.XX | 0.XX | Xs |
| XGBoost | 0.8X | 0.XX | 0.XX | Xs |
| MLP | 0.8X | 0.XX | 0.XX | Xs |

**Como**:
- Guardar métricas de cada modelo em um dict conforme avaliação. Consolidar no final em DataFrame.
- Tempo: usar `time.time()` antes e depois do fit.

**Interpretação para o paper**:
- Se XGBoost >> baseline: modelo aprende sinal não-trivial das features indiretas.
- Se XGBoost ≈ baseline: features indiretas não trazem sinal significativo (isso é honestidade, não fracasso).
- Se MLP ≈ XGBoost: literatura confirmada.
- Escolher **campeão pela AUC do val** (ou Precision@100 se for mais alinhado com o uso pretendido).

---

## 22. Avaliação final no teste

**Por que**: até aqui, tudo foi decidido olhando o val. O teste é o "veredicto imparcial" — mede quão bem o modelo generaliza para dados que ele nunca viu (nem indireto via seleção de hiperparâmetros).

**Como**:
- Só o modelo campeão é avaliado. **Não avalie os três no teste** — isso vira múltipla comparação e infla o risco de escolher o campeão por sorte.
- Métricas iguais às do val, aplicadas em `X_test_scaled` e `y_test`.

**Regra**: se AUC do teste for muito diferente do val (>0.05 de diferença), reportar isso no paper. Pode ser mudança de distribuição em 2025 (política nova, pandemia rebound, etc.). Não retreine ajustando o teste — isso invalida a métrica final.

**Esta é a métrica que vai no abstract do paper**.

---

## 23. Análise de erros

**Por que**: um número (AUC=0.82) não conta a história. A análise de erros diz "o modelo erra mais em bairros X, em meses Y, em paradas com característica Z" — isso vira uma seção inteira boa no paper.

**O que analisar**:
- **Falsos positivos**: parada previu tiroteio mas não teve. Onde ficam essas paradas? Costumam ser paradas em bairros com muitas reclamações mas sem violência real (limitação da metodologia — reclamação não é violência).
- **Falsos negativos**: teve tiroteio mas modelo não previu. Estes são os *casos que importam*. Onde ficam?
- **Erros por mês**: performance cai em algum mês específico? Pode ser sazonalidade não modelada.
- **Erros por região**: modelo é bom em bairros centrais e ruim nos periféricos? Ou o contrário?

**Como**:
- Juntar `y_test`, `y_pred_prob`, `stop_id`, `ano_mes` num DataFrame.
- Marcar `erro_tipo`: TP, TN, FP, FN.
- Groupby por `ano_mes` ou pela geografia (via merge com `stops`) e agregar contagens de erro.

**Isso vira gráfico no paper**.

---

## 24. Persistência

**Por que**: se você não salvar, precisa retreinar tudo toda vez. Também é necessário se quiser fazer uma página no Streamlit para predições novas.

**O que salvar**:
- Scaler: `joblib.dump(scaler, 'artifacts/scaler.joblib')`.
- Modelo campeão: `joblib.dump(model, 'artifacts/model.joblib')`.
- Predições no teste: DataFrame com `stop_id, ano_mes, y_true, y_pred_prob` → salvar como parquet.
- Notebook — commitar no git.

**Como carregar depois** (para predição em produção):
- `scaler = joblib.load(...)`
- `model = joblib.load(...)`
- `X_novo_scaled = scaler.transform(X_novo)` — não `fit_transform`, o scaler já foi treinado.
- `pred = model.predict_proba(X_novo_scaled)[:, 1]`.

**Armadilha**: XGBoost tem serialização própria (`.save_model('model.json')`). `joblib` funciona, mas para portabilidade extra usar o método nativo.

---

## Checklist final antes de fechar

- [ ] Split temporal em três partes, sem sobreposição.
- [ ] Scaler `fit` só no treino.
- [ ] `log1p` só nas features de contagem.
- [ ] Baseline heurístico avaliado com as mesmas métricas.
- [ ] Cada modelo passou por grid search com CV **temporal** ou val fixo — nunca `KFold` aleatório.
- [ ] `class_weight='balanced'` na logística, `scale_pos_weight` no XGBoost.
- [ ] Tabela comparativa no val (não no teste).
- [ ] Teste avaliado uma única vez, só com o campeão.
- [ ] Análise de erros feita.
- [ ] Scaler e modelo salvos.

Se todas as caixas marcadas, você tem um paper defensável.

---

## Erros mais frequentes (para conferir se algo deu errado)

**AUC do modelo idêntica ao baseline** → o modelo não está aprendendo. Verificar: features foram scaled? `log1p` foi aplicado? Modelo tem `class_weight`?

**AUC do modelo pior que o baseline** → tem coisa embolada. Provavelmente `fit_transform` do scaler foi no dataset inteiro (leakage do teste para treino corrompeu o treino) ou `y` inverteu em algum lugar.

**AUC no teste muito diferente do val** → mudança de distribuição. Documentar, não corrigir.

**MLP treinando por horas** → `early_stopping=False` (default). Ativar.

**"ConvergenceWarning" na logística** → `max_iter=100` (default). Subir para 1000.

**Predições todas zeradas** → sem `class_weight` / `scale_pos_weight`, modelo prevê majoritária. Ativar.

---

## Referências para a pessoa que vai fazer

- sklearn `LogisticRegression`: https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html
- sklearn `MLPClassifier`: https://scikit-learn.org/stable/modules/generated/sklearn.neural_network.MLPClassifier.html
- sklearn `GridSearchCV`: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GridSearchCV.html
- sklearn `TimeSeriesSplit`: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html
- XGBoost Python API: https://xgboost.readthedocs.io/en/stable/python/python_api.html
- Shwartz-Ziv & Armon (2022) *Tabular Data: Deep Learning is Not All You Need* — https://arxiv.org/abs/2106.03253
