# Declaração de uso de IA

## Ferramenta e modelo

- Ferramenta: Claude Code (aba Code do app desktop do Claude, Windows).
- Modelo: Claude Opus 5.5 (`claude-opus-5-5`).
- Sessão: uma única sessão, exportada em `sessao.md`.

## O que a IA fez

- Leu o enunciado, o código, os testes e os dados, e identificou os cinco defeitos (D1 a D5) e a causa raiz de cada um.
- Propôs o plano em etapas, com um commit por etapa, e apontou as regras do enunciado que o plano precisava respeitar,
  incluindo esta declaração.
- Escreveu o código das correções, das validações de entrada, dos avisos de inconsistência e dos Protocols.
- Escreveu os testes novos e rodou, a cada etapa, lint, mypy, a suíte e contraprovas (testes contra o código antigo ou
  contra mutantes com o bug plantado).
- Configurou o workflow do GitHub Actions e acompanhou os runs pelo `gh`.
- Redigiu o `README-ENTREGA.md` e o rascunho desta declaração.

## O que eu fiz

- Defini os requisitos do trabalho: boas práticas, arquitetura coerente com o projeto existente, testes para tudo,
  um commit por etapa mostrando a evolução, testes rodando no GitHub via `gh`, e nenhuma regra do desafio descumprida.
- Tomei as decisões de escopo e de regra de negócio que o enunciado não fecha, entre as opções apresentadas:
  - CI no GitHub Actions, mantendo Python 3.11 e 3.13, e mypy no CI;
  - teste e correção no mesmo commit; testes em arquivos planos em `tests/`;
  - ordenar o ranking pelo valor exato, e não pelo valor arredondado;
  - quais entradas viram erro (exit 2) e quais viram aviso, após o risco de reprovar testes do avaliador ser apontado;
  - rejeitar status com caixa diferente e normalizar moeda; checar moeda sem taxa em todas as reservas;
  - aceitar check-out igual ao check-in (0 noites), seguindo a regra "sem noites, 0.00" do README;
  - avisar, sem incluir campos novos no JSON, quando há mais de uma empresa no arquivo.
- Revisei cada etapa e pedi mudanças: mais casos e nomes melhores nos testes de noites, mais testes de câmbio, o teste
  de status misturados no mesmo hotel e mês, os testes de empate no corte do ranking, e a troca da leitura do README
  por valores literais no teste de contrato.
- Questionei se os testes fornecidos tinham sido alterados e conferi contra o zip original do desafio.
- Executei todos os comandos de git e GitHub: criação do repositório, commits, push e acompanhamento do CI.
