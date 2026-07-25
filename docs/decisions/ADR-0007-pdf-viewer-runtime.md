# ADR-0007 — PDF Engine por visualizadores do sistema

Status: aceito

Data: 2026-07-25

## Decisão

O PDF Engine valida um arquivo local `.pdf`, detecta um visualizador instalado e reutiliza o Panel Runtime para incorporação X11 ou fallback externo.

Visualizadores iniciais: Xreader, Evince, Atril, Okular, Zathura e MuPDF.

A aplicação não interpreta nem reescreve o conteúdo do PDF. O arquivo permanece sob controle do visualizador do sistema.

## Consequências

- evita incorporar uma biblioteca PDF pesada no núcleo;
- reaproveita ciclo de vida e fallback já testados;
- arquivos ausentes ou com extensão inválida são rejeitados antes da abertura;
- a compatibilidade de incorporação varia por visualizador;
- backend PDF nativo pode ser avaliado posteriormente.
