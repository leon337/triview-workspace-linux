# ADR-0011 — Layouts normalizados, presets e breakpoints responsivos

Status: aceito

Data: 2026-07-25

## Decisão

Layouts continuam persistidos como slots normalizados entre 0 e 1. Um validador central rejeita limites fora da área e sobreposições. O editor visual modifica coordenadas normalizadas e mostra uma prévia antes de salvar.

O `ResponsiveLayoutEngine` mantém o layout persistido em telas largas e deriva variantes temporárias:

- tela estreita: pilha vertical;
- tela média com três painéis: dois mais um;
- tela média com quatro ou mais: grade;
- tela larga: layout salvo pelo usuário.

As variantes derivadas não alteram o catálogo e removem proporções rígidas para ocupar melhor a área útil.

## Consequências

- layouts independentes de resolução;
- criação visual com validação antes da persistência;
- melhor uso de telas estreitas e médias;
- nenhum layout existente é sobrescrito silenciosamente;
- edição por arrastar pode ser adicionada posteriormente sem mudar o formato persistido.
