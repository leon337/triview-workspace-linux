# ADR-0009 — Gravação da região do painel com FFmpeg

Status: aceito

Data: 2026-07-25

## Decisão

O Recording Engine usa a geometria absoluta do painel e o backend `ffmpeg` com `x11grab` para gravar somente aquela região.

O processo é iniciado sem shell, grava em arquivo parcial MP4/H.264 e recebe SIGINT para finalizar o contêiner corretamente. Pausa e retomada usam SIGSTOP e SIGCONT. Em encerramentos ou trocas de workspace, todas as sessões são finalizadas em melhor esforço.

## Consequências

- gravação isolada por painel;
- arquivo MP4 compatível com reprodução comum;
- indicador visual vinculado ao estado do processo;
- histórico JSONL auditável;
- dependência inicial de X11 e FFmpeg;
- áudio não faz parte deste marco;
- backend Wayland permanece posterior.
