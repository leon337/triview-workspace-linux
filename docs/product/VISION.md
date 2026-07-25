# Visão do produto

## Declaração de visão

O TriView Workspace será uma plataforma Linux para montar, executar e preservar áreas de trabalho compostas por painéis independentes. Cada painel poderá representar um navegador, aplicação, terminal, documento, monitor de logs ou outro componente fornecido por adaptadores.

O produto não deve ser limitado ao caso inicial de três navegadores. O núcleo deve permanecer capaz de gerenciar diferentes tipos de painel, layouts e sessões sem exigir refatorações profundas a cada expansão.

## Problema que o produto resolve

Fluxos de trabalho modernos exigem várias ferramentas abertas ao mesmo tempo. Organizar essas ferramentas manualmente causa:

- perda de tempo ao reposicionar janelas;
- sobreposições e dimensões inconsistentes;
- dificuldade para repetir a mesma organização;
- captura e gravação excessivamente amplas, incluindo conteúdo que não pertence ao painel desejado;
- dependência de coordenadas fixas e resoluções específicas.

## Proposta de valor

O TriView Workspace deverá permitir que uma pessoa:

1. escolha ou crie um workspace;
2. defina quais painéis farão parte dele;
3. associe navegadores, aplicações ou outros componentes a cada painel;
4. redimensione a janela sem perder a organização proporcional;
5. salve e restaure a sessão;
6. capture imagem ou vídeo de um único painel;
7. expanda o sistema por adaptadores e plugins.

## Público inicial

- desenvolvedores e estudantes de programação;
- profissionais que trabalham com múltiplas ferramentas ao mesmo tempo;
- pessoas que produzem demonstrações, tutoriais e documentação visual;
- usuários Linux que precisam de workspaces repetíveis e organizados.

## Estado atual

A versão `0.1.2` entrega:

- fundação modular;
- modelos de workspace, layout e painel;
- Layout Engine proporcional;
- registro extensível de adaptadores;
- migração segura da versão legada;
- sistema de atualização versionado;
- interface gráfica inicial com três painéis responsivos.

A interface atual é uma **casca gráfica funcional**. Os painéis ainda não incorporam Brave, terminal ou outras aplicações reais.

## Visão de longo prazo

O produto deverá evoluir para um gerenciador universal de áreas de trabalho com:

- múltiplos layouts;
- workspaces persistentes;
- painéis de navegador e aplicações;
- captura e gravação individual;
- histórico de capturas;
- sessões isoladas;
- plugins;
- compatibilidade controlada com X11 e Wayland;
- distribuição instalável e atualização segura.

## Não objetivos atuais

Neste estágio, o projeto não pretende:

- substituir um sistema operacional;
- criar um navegador completo do zero;
- garantir incorporação de toda aplicação Linux sem validação técnica;
- prometer captura isolada idêntica em todos os ambientes gráficos;
- declarar estabilidade de produção antes da versão `1.0`.
