# Responsabilidades dos Engines

Este documento separa componentes existentes de componentes planejados. A palavra **implementado** indica código presente e integrado; **planejado** indica direção arquitetural ainda não entregue.

## Visão geral

```text
Interface gráfica / CLI
          ↓
Workspace Engine
   ├── Layout Engine
   ├── Panel Registry / adapters
   ├── Session Engine          [planejado]
   ├── Capture Engine          [planejado]
   └── Plugin Engine           [planejado]
          ↓
Configuração, persistência, sistema gráfico e sistema operacional
```

## Workspace Engine

Status: **implementado na fundação**

Responsabilidades:

- receber um workspace e um layout;
- verificar compatibilidade entre número de painéis e slots;
- solicitar os limites calculados ao Layout Engine;
- localizar o adaptador adequado para cada painel;
- produzir a representação preparada para execução.

Não deve:

- desenhar diretamente a interface;
- executar comandos específicos de navegador;
- capturar tela;
- persistir sessões por conta própria.

## Layout Engine

Status: **implementado**

Responsabilidades:

- converter regiões normalizadas em retângulos de pixels;
- recalcular o layout para a dimensão atual da área útil;
- preservar proporção visual opcional;
- manter layouts independentes de resolução fixa.

Não deve:

- iniciar aplicações;
- controlar cookies ou sessões;
- gravar tela;
- decidir qual conteúdo pertence ao painel.

Próximas evoluções planejadas:

- breakpoints responsivos;
- ocupação maior da área maximizada;
- múltiplos layouts configuráveis;
- editor ou seletor de layout.

## Panel Registry e adaptadores

Status: **registro implementado; adaptadores reais planejados**

Responsabilidades:

- associar um tipo de painel ao adaptador compatível;
- proteger o domínio de detalhes de Brave, terminal, X11 ou Wayland;
- produzir solicitações de abertura ou incorporação;
- informar indisponibilidade de forma controlada.

Adaptadores previstos:

- Browser Adapter;
- Application Adapter;
- Terminal Adapter;
- PDF Adapter;
- Custom/Plugin Adapter.

## Interface gráfica

Status: **implementada como casca funcional na versão 0.1.2**

Responsabilidades atuais:

- manter uma janela desktop aberta;
- exibir os painéis preparados;
- reagir ao redimensionamento;
- apresentar título, alvo e estado;
- reservar ações de abrir, print e gravação.

Limite atual:

- o conteúdo exibido é placeholder;
- as ações funcionais dependem dos Engines e adaptadores posteriores.

## Browser Engine

Status: **planejado**

Responsabilidades esperadas:

- abrir conteúdo web através do backend escolhido;
- gerenciar navegação e estado do painel;
- definir estratégia para sessões e perfis;
- fornecer fallback quando incorporação não for possível;
- tratar diferenças entre X11 e Wayland.

Decisão pendente:

- navegador incorporado, janela externa controlada ou arquitetura híbrida. Essa escolha exige prova técnica específica.

## Application Engine

Status: **planejado**

Responsabilidades esperadas:

- iniciar aplicações Linux;
- avaliar se a aplicação aceita incorporação;
- controlar fallback para janela externa;
- acompanhar processo e encerramento;
- comunicar estado ao painel.

## Session Engine

Status: **planejado**

Responsabilidades esperadas:

- salvar e restaurar workspace ativo;
- manter configuração dos painéis;
- gerenciar perfis e sessões quando suportados;
- recuperar estado após encerramento inesperado;
- versionar dados persistidos.

## Capture Engine

Status: **planejado**

Responsabilidades esperadas:

- receber identidade e limites do painel;
- capturar imagem somente da área ou superfície correspondente;
- iniciar e encerrar gravação individual;
- produzir metadados de arquivo;
- organizar capturas por workspace, painel e data;
- selecionar backend compatível com X11 ou Wayland.

Não deve:

- decidir o layout;
- alterar o conteúdo do painel;
- armazenar configurações de sessão.

## Plugin Engine

Status: **planejado**

Responsabilidades esperadas:

- descobrir plugins permitidos;
- verificar versão e compatibilidade;
- registrar novos adaptadores de forma controlada;
- isolar falhas de plugin;
- impedir carregamento silencioso de componentes não confiáveis.

## Persistência

Status: **configuração JSON inicial implementada; gestão completa planejada**

Responsabilidades esperadas:

- armazenar workspaces e layouts;
- manter versão de esquema;
- aplicar migrações compatíveis;
- preservar dados durante atualização;
- suportar backup e restauração.

## Regras de dependência

1. A interface chama os Engines, não o contrário.
2. Layout não executa aplicações.
3. Adaptadores não definem o modelo persistente.
4. Captura não altera layout nem sessão.
5. Persistência não deve conhecer widgets gráficos.
6. Integrações específicas do sistema operacional permanecem na infraestrutura ou em adaptadores.
