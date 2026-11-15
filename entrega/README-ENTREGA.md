# Entrega — Consolidador de reservas de hotel

Repositório: https://github.com/arthur-lima-camargos/onfly-desafio

O CLI foi corrigido sem alterar o comando, os argumentos, o schema do relatório, os testes fornecidos nem os
arquivos `data/reservas_hoteis.csv` e `data/taxas_cambio.csv` (conferido com `git diff` contra o commit inicial
e contra o zip original do desafio).

## Defeitos corrigidos

| # | Onde | Causa raiz | Commit |
|-|-|-|-|
| D1 | `repositories/csv_reservation_repository.py` | A leitura parava em 200 linhas (`break`), descartando o resto do arquivo (o dataset tem 300). | `fix(repository)` |
| D2 | `services/stay_calculator.py` | As noites eram `checkout.day - checkin.day` (dia do mês), que fica negativo na virada de mês/ano, em vez de `(checkout - checkin).days`. | `fix(stay)` |
| D3 | `services/currency_converter.py` | O valor era **dividido** pela taxa (em vez de multiplicado) e a conta passava por `float`. | `fix(currency)` |
| D4 | `services/status_policy.py` | A regra era `status != "CANCELLED"`, então `NO_SHOW` era faturado; só `CONFIRMED` deve ser. | `fix(status)` |
| D5 | `services/report_builder.py` | O ranking ordenava por valor **crescente**; o correto é decrescente com desempate por `hotel_id` crescente. | `fix(ranking)` |

Efeito no dataset real (`data/reservas_hoteis.csv`):

| | Antes | Depois |
|-|-|-|
| `total_reservations` | 200 | 300 |
| `confirmed` / `cancelled` / `no_show` | 153 / 22 / 25 | 235 / 31 / 34 |
| `total_room_nights` | -1393 | 1347 |
| `total_amount_brl` | 193218.53 | 396170.00 |
| `average_nightly_rate_brl` | 0.00 | 294.11 |
| `top_hotels` | H04, H05, H02, H08, H12 (os menores) | H06, H10, H12, H07, H11 |

A amostra `data/exemplo-validacao.csv` reproduz exatamente as tabelas do README.

## Como o problema foi investigado

1. **Linha de base.** `pytest` no código original: 5 falhas, como o README avisa. Cada falha foi lida como sintoma:
   `-28 == 3` (noites), `'118.45' == '642.00'` (câmbio), `'120.00' == '100.00'` (status),
   `['H04','H03','H02']` (ranking).
2. **Leitura guiada pelo pipeline do README** (`ler → converter tipos → contar status → filtrar CONFIRMED →
   agregar`), comparando cada módulo com a regra correspondente. Assim apareceu o D1, que nenhum teste fornecido
   pega: os testes usam CSVs pequenos e o corte só acontece a partir de 200 linhas.
3. **Perfil dos dados reais** com `csv` puro: 300 linhas, sem BOM, 3 status, 3 moedas, IDs únicos, nomes de hotel
   consistentes e estadias que cruzam a virada de ano (2024-12 → 2025-01). Isso confirmou que os defeitos estão no
   CLI, não nos dados.
4. **Um defeito por commit, com teste junto.** Cada correção veio com testes unitários e uma contraprova: rodar os
   testes novos contra o código antigo (ou contra um mutante com o bug plantado) e ver que falham.
5. **Revisão do resultado.** Com os cinco defeitos corrigidos, o código foi revisado atrás de pontos frágeis.
   Cada ponto foi reproduzido no CLI antes de qualquer mudança: `rooms` de `1_0` virava 10 quartos com exit 0,
   `amount` de `1E+40` saía com traceback e exit 1, `--output` igual a `--input` trocava o CSV pelo JSON. A
   mesma reprodução mostrou que dois pontos (as 15 colunas obrigatórias e o exit 1 na falha de escrita) vinham
   do código fornecido, e eles foram mantidos (ver abaixo).

## Decisões tomadas

O README não cobre todos os casos; estas decisões estão documentadas no código e travadas por teste.

- **Ranking por valor exato.** A ordem usa o total `Decimal` exato, não o valor serializado ("arredonde só na
  serialização"). Dois hotéis que diferem em fração de centavo podem aparecer com o mesmo `total_brl` fora da
  ordem de `hotel_id`.
- **Entrada impossível é erro (exit 2), com o número da linha:**
  - status fora de `CONFIRMED`/`CANCELLED`/`NO_SHOW` (caixa diferente também);
  - moeda sem taxa em reserva `CONFIRMED`;
  - `amount`, `rooms` ou taxa fora do formato numérico simples: só dígitos ASCII e ponto decimal, em tamanho
    limitado. Sinal, expoente (`1E+3`), sublinhado (`1_000`), dígito Unicode (`２`), `NaN` e `Infinity` são
    recusados; `Decimal()` e `int()` sozinhos aceitariam vários deles;
  - `rooms < 1` e check-out antes do check-in;
  - data fora de `YYYY-MM-DD` (o `date.fromisoformat` do 3.11 aceitaria `20250110`);
  - campo usado no relatório vazio, linha com número de colunas diferente do cabeçalho, arquivo fora de UTF-8
    e moeda repetida na tabela de câmbio.

  Antes, parte desses casos gerava relatório errado com exit 0 (ex.: noites negativas) e parte saía com
  traceback e exit 1. Todas as linhas inválidas são listadas em uma execução (até 20), não só a primeira.
- **Suspeito mas calculável é aviso** (WARNING no stderr, exit 0, JSON inalterado): `reservation_id` repetido
  (possível cobrança em dobro), mesmo `hotel_id` com nomes diferentes (o relatório usa o primeiro do arquivo),
  mais de um `company_id` e moeda sem taxa em reserva `CANCELLED` ou `NO_SHOW` (o relatório não converte essas
  reservas). Rejeitar esses casos mudaria a semântica de "número de reservas no arquivo".
- **Aceito sem aviso:** check-out igual ao check-in (0 noites, ex.: day use; é o "sem noites → `0.00`" do README),
  valor zero, valor com até 6 casas decimais (o arredondamento é só na saída), moeda em minúsculas (normalizada,
  como a tabela de câmbio já fazia) e CSV com BOM do Excel.
- **Precisão explícita.** A conta de dinheiro roda com 60 dígitos. Com a entrada limitada (valor e taxa de até 21
  dígitos), nenhuma soma é arredondada; a precisão padrão do `Decimal` (28) arredondaria em silêncio a partir de
  totais de 29 dígitos.
- **CLI.**
  - `--output` apontando para o mesmo arquivo de `--input` ou `--rates` é argumento inválido (exit 2); antes o
    CSV de origem era sobrescrito pelo JSON com exit 0.
  - Só os quatro argumentos documentados são aceitos: abreviações como `--inp` (padrão do `argparse`) dão exit 2.
  - O relatório é gravado de forma atômica (arquivo temporário e troca): uma falha no meio não deixa um JSON
    truncado no lugar do relatório anterior.
  - `generated_at` é sempre convertido para `-03:00`.
- **Mantido do código fornecido.** Dois comportamentos pareceram rígidos na revisão, mas já estavam no código
  original e não fazem parte dos defeitos; mudá-los arriscaria divergir de uma correção de referência:
  - as 15 colunas do CSV de reservas continuam obrigatórias, embora só 9 sejam usadas;
  - falha ao gravar o relatório (ex.: `--output` é um diretório) continua exit 1, como o `cli.py` original
    tratava `OSError`.

## Mudanças de estrutura

A arquitetura existente (`repositories/` para I/O, `services/` com uma regra por módulo, `ReportBuilder`
orquestrando) foi mantida:

- `services/hotel_ranking.py`: ranking extraído do `ReportBuilder` para uma função pura.
- `services/aggregation.py`: `Totals` e `ReportData`, os números exatos do relatório, sem arredondar.
- `services/report_serializer.py`: o JSON descrito em `TypedDict`, para o mypy verificar o contrato, e o único
  lugar onde o dinheiro é arredondado. Com isso o `ReportBuilder.build()` só encadeia as etapas.
- `services/consistency_checks.py`: os avisos de inconsistência.
- `repositories/protocols.py`: `ReservationSource` e `RateSource`. O `ReportBuilder` depende dos contratos, não das
  classes CSV, e pode ser testado com fontes em memória.
- `repositories/json_report_writer.py`: a gravação atômica do relatório.
- `number_format.py`: os formatos numéricos aceitos na entrada e a precisão da aritmética.
- `models.ReservationStatus` (`StrEnum`) no lugar de strings soltas.
- CI no GitHub Actions (`.github/workflows/ci.yml`): `ruff`, `mypy` e `pytest` em Python 3.11 e 3.13, e os dois
  relatórios publicados como artifact a cada push.

## Testes

Os 5 testes fornecidos estão inalterados. Os 430 novos ficam em arquivos `tests/test_*.py`:

| Tipo | Arquivos | O que cobrem |
|-|-|-|
| Unitários | `test_unit_*.py` | Cada regra isolada: noites (virada de mês/ano, bissexto), câmbio (exatidão, oráculo com inteiros), status, ranking (empate, corte do top, valor exato), parser (cada validação e a lista de linhas inválidas), formato numérico e precisão, agregação, serialização, gravação atômica (falha simulada no meio da escrita), repositórios, `ReportBuilder` com fontes em memória, avisos. |
| Ponta a ponta | `test_cli_*.py` | O CLI em subprocess: regras de status por seção do relatório, ranking, e os códigos de saída 0/1/2 com stdout e stderr. |
| Contrato | `test_contract_sample.py`, `test_report_format.py` | A amostra do README campo a campo; chaves, tipos e formatos do JSON; half-up. |
| Regressão | `test_full_dataset.py` | O dataset real comparado com um oráculo independente escrito no próprio teste (sem importar `onfly_report`), mais invariantes. |

Os testes novos foram conferidos com contraprovas: 38 bugs plantados um a um nas etapas da revisão (ex.: tirar a
precisão explícita, gravar direto no destino, parar na primeira linha inválida), e a suíte falha em todos.

## Como validar

```bash
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

pytest -q
ruff check .
mypy

PYTHONPATH=src python -m onfly_report \
  --input data/reservas_hoteis.csv \
  --rates data/taxas_cambio.csv \
  --output output/report.json

PYTHONPATH=src python -m onfly_report \
  --input data/exemplo-validacao.csv \
  --rates data/taxas_cambio.csv \
  --output output/exemplo.json
```

No PowerShell, troque `PYTHONPATH=src python ...` por `$env:PYTHONPATH="src"; python ...`.

## Resultado do pytest

Testes fornecidos:

```
$ pytest -q tests/test_currency.py tests/test_nights.py tests/test_regression_report.py tests/test_status_rules.py tests/test_top_hotels.py
.....                                                                    [100%]
5 passed in 1.09s
```

Suíte completa (Python 3.13 local; o CI roda a mesma suíte em 3.11 e 3.13):

```
$ pytest -q
........................................................................ [ 16%]
........................................................................ [ 33%]
........................................................................ [ 49%]
........................................................................ [ 66%]
........................................................................ [ 82%]
........................................................................ [ 99%]
...                                                                      [100%]
435 passed in 18.15s
```

## Uso de IA

O desafio foi feito com um assistente de IA. A exportação da sessão e a declaração (o que a IA fez e o que eu
fiz) estão em `entrega/uso-de-ia/`.
