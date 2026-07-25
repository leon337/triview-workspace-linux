# Roadmap do produto

Este roadmap registra direção e sequência. Uma funcionalidade só é concluída após implementação, CI, integração no trem e teste de aceite no Linux Mint.

## Marcos concluídos

### `0.1.0` — Fundação modular

Status: **concluído**

- modelos de workspace, layout e painel;
- Layout Engine e Workspace Engine;
- registro extensível de adaptadores;
- testes e CI iniciais.

### `0.1.1` — Migração e atualização segura

Status: **concluído**

- backup, restauração e migração;
- instalação em diretórios versionados;
- atualização com troca atômica.

### `0.1.2` — Primeira interface gráfica

Status: **concluído**

- janela desktop responsiva;
- três painéis móveis;
- maximizar, restaurar e redimensionar;
- diagnóstico separado da GUI.

### LEA-194 — Consolidação documental

Status: **concluído**

- visão, princípios, roadmap e histórico;
- responsabilidades dos Engines;
- manual da Fábrica de Softwares.

### `0.2.0` — Browser Engine

Status: **concluído e validado no Linux Mint**

- navegador incorporado com X11 e `xdotool`;
- sessões separadas por painel;
- redimensionamento, reabertura e encerramento;
- fallback e diagnóstico controlados.

### `0.3.0` — Workspaces persistentes

Status: **concluído e validado no Linux Mint**

- catálogo JSON com esquema versionado;
- gravação atômica e recuperação de corrupção;
- criação, cópia, renomeação, edição e exclusão;
- restauração automática do último workspace;
- seleção de layouts;
- dados separados das releases.

## Trem de desenvolvimento LEA-197–205

A branch `main` permanece estável. O trem é integrado em `train/road-to-1.0`. Cada LEA usa branch, PR, CI e candidato isolado antes da promoção.

### `0.4.0` — Application Engine — LEA-197

Status: **implementado no candidato; aguardando CI e teste no Linux Mint**

- Panel Runtime comum para processos e janelas;
- execução segura sem shell;
- Application Adapter e Application Engine;
- incorporação X11 quando compatível;
- fallback para janela externa;
- instalador de candidato isolado.

### `0.5.0` — Terminal Engine — LEA-198

Status: **planejado**

- terminal incorporado;
- shell configurável;
- ciclo de vida e fallback externo.

### `0.6.0` — PDF Engine — LEA-199

Status: **planejado**

- validação e abertura de PDFs;
- visualizador incorporado ou fallback controlado.

### `0.7.0` — Capture Engine — LEA-200

Status: **planejado**

- print de um painel;
- organização por workspace, painel e data;
- feedback e histórico inicial.

### `0.8.0` — Recording Engine — LEA-201

Status: **planejado**

- gravação individual;
- indicador de estado;
- formatos e qualidade suportados;
- encerramento seguro de processos.

### `0.9.0` — Plugin Engine — LEA-202

Status: **planejado**

- API pública versionada;
- descoberta somente em diretórios permitidos;
- validação e isolamento de falhas.

### `0.10.0` — Layout Engine avançado — LEA-203

Status: **planejado**

- layouts de um a quatro painéis e grade 2×2;
- breakpoints responsivos;
- editor visual e validação de sobreposição.

### `0.11.0` — Session Engine completo — LEA-204

Status: **planejado**

- estado operacional versionado por painel;
- restauração parcial e recuperação após falhas;
- isolamento de perfis e configurações.

### `1.0.0` — Workspace Hub — LEA-205

Status: **planejado**

- biblioteca de workspaces e templates;
- busca, favoritos e categorias;
- importação e exportação versionadas;
- primeira versão estável após aceite de todos os marcos mínimos.

## Evoluções posteriores

- backend nativo ou híbrido para Wayland;
- múltiplos monitores;
- sincronização opcional;
- marketplace e assinatura de plugins;
- automações e agentes de IA.

## Itens transversais

- testes automatizados e CI;
- logs e mensagens de erro;
- documentação e ADRs;
- backup e compatibilidade de dados;
- candidatos isolados;
- rastreabilidade Linear ↔ GitHub.
