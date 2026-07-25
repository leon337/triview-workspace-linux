# ADR-0001 — Tratar o produto como plataforma de workspaces

- Status: aceito
- Data: 2026-07-24
- Tarefa: LEA-191

## Contexto

A ideia inicial organizava três janelas do Brave. Essa solução dependia de coordenadas de tela, preservava molduras do navegador, gerava sobreposições e limitava a expansão para outras aplicações.

O produto também precisa abrir aplicações junto com navegadores e, futuramente, capturar ou gravar cada painel individualmente.

## Decisão

O núcleo será uma plataforma de workspaces. Cada workspace referencia um layout proporcional e uma coleção de painéis. Cada painel declara seu tipo e seu alvo; adaptadores resolvem a execução concreta.

## Consequências positivas

- suporte futuro a navegadores, aplicações, terminais, PDFs e plugins;
- layout responsivo sem coordenadas fixas como regra principal;
- captura individual poderá operar sobre limites conhecidos de cada painel;
- menor acoplamento e menos refatorações profundas.

## Consequências e riscos

- incorporar aplicações Linux de terceiros exige avaliar X11 e Wayland separadamente;
- nem toda aplicação aceita reparenting ou captura isolada;
- gravação por painel exigirá backends diferentes conforme a sessão gráfica;
- a primeira versão funcional terá mais etapas que um simples script com `wmctrl`.
