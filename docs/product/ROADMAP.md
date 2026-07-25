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

Status: **concluído e validado no Linux Mint**

- Browser Engine com contrato de backend substituível;
- Browser Adapter integrado ao Panel Registry;
- URL HTTP/HTTPS validada e normalizada;
- Brave/Chromium incorporado com X11 e `xdotool`;
- perfis locais separados por painel;
- redimensionamento e estados visuais;
- fallback controlado;
- validação real de ChatGPT e GitHub simultâneos.

Limite conhecido: o backend inicial é validado em X11, mas ainda não oferece incorporação nativa em Wayland.

### `0.3.0` — Workspaces persistentes

Status: **concluído tecnicamente; aguardando validação visual no Linux Mint**

- catálogo JSON com esquema versionado;
- gravação atômica e recuperação de arquivo corrompido;
- migração do bundle único legado;
- restauração automática do último workspace;
- criação por cópia do workspace atual;
- renomeação e exclusão controlada;
- edição de títulos, tipos e destinos dos painéis;
- seleção de layouts disponíveis;
- Session Engine desacoplado da interface;
- dados persistentes fora dos diretórios versionados da aplicação;
- testes de persistência, migração, recuperação e sessão.

## Próximos marcos recomendados

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

### `0.7.0` — Sessões e perfis de navegador

Status: **planejado**

- cookies e autenticação persistentes por painel quando suportados;
- gerenciamento de perfis de navegador;
- isolamento de configurações;
- recuperação de processos após encerramento inesperado.

### `0.8.0` — Layouts e refinamento visual

Status: **planejado**

- painéis ocupando maior percentual da tela maximizada;
- margens e espaçamentos responsivos;
- breakpoints para três colunas, duas mais uma e coluna única;
- editor completo de layouts;
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

- testes automatizados;
- CI;
- logs e mensagens de erro;
- documentação;
- backup e compatibilidade de dados;
- avaliação de X11 e Wayland;
- rastreabilidade Linear ↔ GitHub.
