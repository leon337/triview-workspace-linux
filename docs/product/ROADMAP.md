# Roadmap do produto

Este roadmap registra direção e sequência. Datas não são prometidas por este documento. Cada marco só muda para concluído após implementação, testes, integração na branch principal e documentação.

## Marcos concluídos

### `0.1.0` — Fundação modular

Status: **concluído**

- modelos de workspace, layout e painel;
- Layout Engine proporcional;
- Workspace Engine;
- registro extensível de adaptadores;
- configuração de exemplo com três painéis;
- testes e CI iniciais.

### `0.1.1` — Migração e atualização segura

Status: **concluído**

- migração da instalação legada;
- preservação de URLs e configurações;
- backups e restauração;
- instalação em diretórios versionados;
- atualizador com troca atômica da versão ativa.

### `0.1.2` — Primeira interface gráfica

Status: **concluído**

- janela desktop real;
- três painéis móveis;
- redimensionamento responsivo;
- maximizar, minimizar e restaurar pelo gerenciador de janelas;
- CLI de diagnóstico mantida separadamente.

### LEA-194 — Consolidação documental

Status: **concluído**

- visão e princípios do produto;
- roadmap e histórico de versões;
- responsabilidades dos Engines;
- manual da Fábrica de Softwares;
- índice documental central.

### `0.2.0` — Primeiro painel funcional

Status: **concluído**

Objetivo entregue: provar a execução real dentro da arquitetura de painéis.

Entregas:

- Browser Engine com contrato de backend substituível;
- Browser Adapter integrado ao Panel Registry;
- URL HTTP/HTTPS validada e normalizada;
- Brave/Chromium iniciado em modo aplicativo;
- incorporação da janela no host do painel através de X11 e `xdotool`;
- perfis locais separados por painel;
- redimensionamento da janela incorporada;
- estados visuais de disponibilidade, abertura, atividade e erro;
- fallback controlado quando navegador, `DISPLAY` ou `xdotool` não estão disponíveis;
- preservação do modo `--diagnostic`;
- testes headless e documentação arquitetural.

Limite conhecido: o backend inicial não é nativo de Wayland e precisa ser validado no Linux Mint real.

## Próximos marcos recomendados

### `0.3.0` — Workspaces persistentes

Status: **planejado**

- criar, editar, salvar e excluir workspaces;
- selecionar layouts;
- restaurar o workspace usado anteriormente;
- versionar o esquema persistido;
- preservar configurações durante atualizações.

### `0.4.0` — Captura individual de imagem

Status: **planejado**

- print de um único painel;
- nomes e diretórios organizados por workspace, painel e data;
- feedback visual de sucesso ou falha;
- histórico inicial de capturas.

### `0.5.0` — Gravação individual por painel

Status: **planejado**

- iniciar, pausar e encerrar gravação de um painel;
- indicador de gravação;
- seleção de formato e qualidade suportados;
- organização automática dos vídeos;
- avaliação separada de X11 e Wayland.

### `0.6.0` — Aplicações e terminais

Status: **planejado**

- Application Adapter;
- Terminal Adapter;
- validação de aplicações que aceitam ou não incorporação;
- fallback para execução externa controlada.

### `0.7.0` — Sessões e perfis

Status: **planejado**

- sessões independentes persistentes por painel quando suportadas;
- gerenciamento de perfis de navegador;
- isolamento de configurações;
- recuperação após encerramento inesperado.

### `0.8.0` — Layouts e refinamento visual

Status: **planejado**

- painéis ocupando maior percentual da tela maximizada;
- margens e espaçamentos responsivos;
- breakpoints para três colunas, duas mais uma e coluna única;
- editor ou seletor de layouts;
- acessibilidade e conforto de leitura.

### `0.9.0` — Plugins e preparação de estabilidade

Status: **planejado**

- contratos públicos para adaptadores;
- descoberta controlada de plugins;
- validação de compatibilidade;
- revisão de segurança, desempenho e recuperação.

### `0.10.0` — Compatibilidade gráfica ampliada

Status: **planejado**

- backend nativo ou híbrido para Wayland;
- seleção automática de backend gráfico;
- fallback para janela externa controlada quando necessário;
- matriz de compatibilidade por distribuição e sessão gráfica.

### `1.0.0` — Primeira versão estável

Status: **planejado**

Critérios mínimos esperados:

- instalação e atualização confiáveis;
- workspaces persistentes;
- ao menos um navegador ou conteúdo web funcional;
- ao menos uma integração de aplicação validada;
- print individual funcional;
- gravação individual funcional em pelo menos um ambiente gráfico suportado;
- documentação de usuário e arquitetura;
- testes de regressão e restauração.

## Itens transversais

Estes itens acompanham todos os marcos:

- testes automatizados;
- CI;
- logs e mensagens de erro;
- documentação;
- backup e compatibilidade de dados;
- avaliação de X11 e Wayland;
- rastreabilidade Linear ↔ GitHub.
