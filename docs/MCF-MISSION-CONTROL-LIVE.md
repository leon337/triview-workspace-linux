# TriView — MCF Mission Control ao vivo

Status: `IMPLEMENTATION_CANDIDATE — STAGING ONLY`

O Cockpit pode descobrir e projetar automaticamente a missão canônica mais
recente de um repositório. A cada três segundos ele faz uma leitura `GET` no
boundary dedicado do MCF; não cria missões, não executa fases e não grava
estado canônico.

## Entradas transitórias

```text
TRIVIEW_MCF_RUNTIME_URL=https://mcf-runtime-staging-api.onrender.com
TRIVIEW_MCF_MISSION_CONTROL_REPOSITORY=leon337/multiagent-collaboration-framework
TRIVIEW_MCF_MISSION_CONTROL_TOKEN=<segredo dedicado>
```

O token é uma credencial de autenticação do MCF, não uma chave de API de IA e
não gera cobrança de tokens OpenAI. Ele permanece apenas no processo e nunca é
gravado em `mcf-bindings.json`, modelos de apresentação, logs ou timeline.

## Fluxo

1. O usuário envia uma solicitação ao GPT Mestre.
2. A GPT Action autenticada chama `POST /v1/mcf/mission-control/dispatch`.
3. O MCF cria a missão e executa somente o bootstrap interno governado.
4. O Cockpit chama `GET /v1/mcf/mission-control/latest` a cada três segundos.
5. A missão, autoridade, continuidade e timeline são projetadas em modo
   `READ_ONLY`.

GitHub, deploy, produção e VPS continuam fora desse bootstrap. Fases externas
permanecem aguardando seus gates e evidências existentes.
