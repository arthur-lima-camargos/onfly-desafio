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

## Decisões tomadas

O README não cobre todos os casos; estas decisões estão documentadas no código e travadas por teste.

- **Ranking por valor exato.** A ordem usa o total `Decimal` exato, não o valor serializado ("arredonde só na
  serialização"). Dois hotéis que diferem em fração de centavo podem aparecer com o mesmo `total_brl` fora da
  ordem de `hotel_id`.
- **Entrada impossível é erro (exit 2), com o número da linha:** status fora de `CONFIRMED`/`CANCELLED`/`NO_SHOW`
  (caixa diferente também), moeda sem taxa (em qualquer reserva, não só nas faturáveis), `rooms < 1`, check-out
  antes do check-in, valor negativo ou não finito (`NaN`, `Infinity`), data fora de `YYYY-MM-DD` (o
  `date.fromisoformat` do 3.11 aceitaria `20250110`), campo usado no relatório vazio, linha com número de colunas
  diferente do cabeçalho, arquivo fora de UTF-8 e moeda repetida na tabela de câmbio. Antes, parte desses casos
  gerava relatório errado com exit 0 (ex.: noites negativas) e parte saía com traceback e exit 1.
- **Suspeito mas calculável é aviso** (WARNING no stderr, exit 0, JSON inalterado): `reservation_id` repetido
  (possível cobrança em dobro), mesmo `hotel_id` com nomes diferentes (o relatório usa o primeiro do arquivo) e
  mais de um `company_id`. Rejeitar esses casos mudaria a semântica de "número de reservas no arquivo".
- **Aceito sem aviso:** check-out igual ao check-in (0 noites, ex.: day use; é o "sem noites → `0.00`" do README),
  valor zero, valor com mais de 2 casas (o arredondamento é só na saída), moeda em minúsculas (normalizada, como a
  tabela de câmbio já fazia) e CSV com BOM do Excel.

## Mudanças de estrutura

A arquitetura existente (`repositories/` para I/O, `services/` com uma regra por módulo, `ReportBuilder`
orquestrando) foi mantida:

- `services/hotel_ranking.py`: ranking extraído do `ReportBuilder` para uma função pura.
- `repositories/protocols.py`: `ReservationSource` e `RateSource`. O `ReportBuilder` depende dos contratos, não das
  classes CSV, e pode ser testado com fontes em memória.
- `services/consistency_checks.py`: os avisos de inconsistência.
- `models.ReservationStatus` (`StrEnum`) no lugar de strings soltas.
- CI no GitHub Actions (`.github/workflows/ci.yml`): `ruff`, `mypy` e `pytest` em Python 3.11 e 3.13, e os dois
  relatórios publicados como artifact a cada push.

## Testes

Os 5 testes fornecidos estão inalterados. Os novos ficam em arquivos `tests/test_*.py`:

| Tipo | Arquivos | O que cobrem |
|-|-|-|
| Unitários | `test_unit_*.py` | Cada regra isolada: noites (virada de mês/ano, bissexto), câmbio (exatidão, oráculo com inteiros), status, ranking (empate, corte do top, valor exato), parser (cada validação), repositórios, `ReportBuilder` com fontes em memória, avisos. |
| Ponta a ponta | `test_cli_*.py` | O CLI em subprocess: regras de status por seção do relatório, ranking, e os códigos de saída 0/1/2 com stdout e stderr. |
| Contrato | `test_contract_sample.py`, `test_report_format.py` | A amostra do README campo a campo; chaves, tipos e formatos do JSON; half-up. |
| Regressão | `test_full_dataset.py` | O dataset real comparado com um oráculo independente escrito no próprio teste (sem importar `onfly_report`), mais invariantes. |

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
5 passed in 1.23s
```

Suíte completa (Python 3.13 local; o CI roda a mesma suíte em 3.11 e 3.13):

```
$ pytest -q
........................................................................ [ 27%]
........................................................................ [ 54%]
........................................................................ [ 81%]
................................................                         [100%]
264 passed in 14.03s
```

## Uso de IA

O desafio foi feito com um assistente de IA. A exportação da sessão e a declaração (o que a IA fez e o que eu
fiz) estão em `entrega/uso-de-ia/`.
