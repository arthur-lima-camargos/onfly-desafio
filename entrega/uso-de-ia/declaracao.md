# Declaração de uso de IA

## Ferramenta e modelo

- Ferramenta: Claude Code (aba Code do app desktop do Claude, Windows).
- Modelos: Claude Opus 5.5 (`claude-opus-5-5`) das etapas 1 a 9, e Claude Fable 5.2 (`claude-fable-5-2`) na
  revisão final (etapas 10 a 14 e atualização dos documentos).
- Sessão: uma única sessão, em `sessao.jsonl`. É o transcript do export nativo do app (menu Export da sessão), sem
  os arquivos de estado interno que vêm no mesmo zip.
- Dados ocultados no transcript: dois endereços de e-mail meus e o código de dispositivo do `gh auth login`, já
  expirado, foram trocados pelos marcadores `<email-removido>` e `<codigo-removido>`, porque o repositório é
  público. São 21 das 2265 linhas; as demais estão idênticas ao export.
- Limite do export: ele foi feito no fim da sessão e não inclui as últimas mensagens, em que o transcript foi
  mascarado, colocado nesta pasta e commitado.

## O que a IA fez

- Leu o enunciado, o código, os testes e os dados, e identificou os cinco defeitos (D1 a D5) e a causa raiz de cada um.
- Propôs o plano em etapas, com um commit por etapa, e apontou as regras do enunciado que o plano precisava respeitar,
  incluindo esta declaração.
- Escreveu o código das correções, das validações de entrada, dos avisos de inconsistência e dos Protocols.
- Escreveu os testes novos e rodou, a cada etapa, lint, mypy, a suíte e contraprovas (testes contra o código antigo ou
  contra mutantes com o bug plantado).
- Configurou o workflow do GitHub Actions e acompanhou os runs pelo `gh`.
- Na revisão final, reproduziu no CLI cada ponto frágil que eu levantei, apontou quais comportamentos vinham do
  código fornecido (as 15 colunas obrigatórias e o exit 1 na falha de escrita) e implementou as etapas 10 a 14.
- Redigiu o `README-ENTREGA.md` e o rascunho desta declaração.

## O que eu fiz

- Defini os requisitos do trabalho: boas práticas, arquitetura coerente com o projeto existente, testes para tudo,
  um commit por etapa mostrando a evolução, testes rodando no GitHub via `gh`, e nenhuma regra do desafio descumprida.
- Tomei as decisões de escopo e de regra de negócio que o enunciado não fecha, entre as opções apresentadas:
  - CI no GitHub Actions, mantendo Python 3.11 e 3.13, e mypy no CI;
  - teste e correção no mesmo commit; testes em arquivos planos em `tests/`;
  - ordenar o ranking pelo valor exato, e não pelo valor arredondado;
  - quais entradas viram erro (exit 2) e quais viram aviso, após o risco de reprovar testes do avaliador ser apontado;
  - rejeitar status com caixa diferente e normalizar moeda;
  - aceitar check-out igual ao check-in (0 noites), seguindo a regra "sem noites, 0.00" do README;
  - avisar, sem incluir campos novos no JSON, quando há mais de uma empresa no arquivo.
- Revisei cada etapa e pedi mudanças: mais casos e nomes melhores nos testes de noites, mais testes de câmbio, o teste
  de status misturados no mesmo hotel e mês, os testes de empate no corte do ranking, e a troca da leitura do README
  por valores literais no teste de contrato.
- Questionei se os testes fornecidos tinham sido alterados e conferi contra o zip original do desafio.
- Depois das correções, trouxe para a sessão uma revisão do resultado com os pontos frágeis (parser que aceitava
  `1_000.50` e `1E+3`, valores extremos saindo com traceback, `--output` inválido, rigor além do enunciado, escrita
  não atômica, parada na primeira linha inválida, `generated_at` sem conversão de fuso) e as refatorações sugeridas
  (parser estrito por regex, agregação tipada com `Totals` separada da serialização com `TypedDict`, escrita
  atômica e `astimezone`).
- Decidi os quatro pontos dessa revisão em que havia escolha: manter o exit 1 na falha de escrita, manter as 15
  colunas obrigatórias, transformar em aviso a moeda sem taxa em reserva não faturável e desligar as abreviações
  de argumento.
- Executei todos os comandos de git e GitHub: criação do repositório, commits, push e acompanhamento do CI.
