# ADR-0008 — Captura pelo identificador da janela do painel

Status: aceito

Data: 2026-07-25

## Contexto

O botão Print precisa capturar somente um painel, independentemente de seu conteúdo ser navegador, aplicação, terminal, PDF ou placeholder. Recortar a tela por coordenadas seria mais sensível a bordas, escala e movimentação da janela.

## Decisão

O Capture Engine recebe o identificador X11 da moldura nativa do painel e delega a captura a um backend externo. A prioridade inicial é:

1. `maim`;
2. ImageMagick `import`.

A imagem é gravada primeiro em arquivo parcial e depois movida para o destino final. Os arquivos são organizados por workspace, painel e data, com histórico JSONL auditável.

## Consequências

- captura isolada do painel inteiro, incluindo cabeçalho e ações;
- funcionamento independente do tipo do painel;
- nomes e caminhos previsíveis;
- falhas não derrubam a interface;
- dependência inicial de X11 e de uma ferramenta de captura instalada;
- backend Wayland permanece posterior.
