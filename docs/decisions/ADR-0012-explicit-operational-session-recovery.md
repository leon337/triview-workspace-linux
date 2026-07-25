# ADR-0012 — Recuperação operacional explícita e sem segredos

Status: aceito

Data: 2026-07-25

## Contexto

Restaurar processos automaticamente pode reabrir aplicações inesperadas, executar comandos ou repetir operações após uma falha. Também seria inadequado persistir cookies, conteúdo de terminal, tokens ou destinos sensíveis em um arquivo de estado operacional.

## Decisão

O Session Engine completo registra somente:

- workspace e layout ativos;
- identidade e adaptador dos painéis;
- hash da configuração do painel;
- estado aberto, incorporado ou externo;
- indicador de encerramento limpo;
- horário da última sincronização.

Destinos, cookies, conteúdo de terminal, argumentos resolvidos, PIDs e credenciais não são armazenados. Na abertura seguinte, o Engine constrói um plano apenas para painéis cuja configuração ainda corresponde ao hash salvo.

A restauração nunca inicia processos silenciosamente. A interface apresenta uma confirmação com a lista dos painéis recuperáveis. O usuário pode aceitar ou ignorar.

O arquivo é gravado atomicamente e um estado inválido é preservado em quarentena antes da recuperação segura.

## Consequências

- recuperação após fechamento normal ou interrupção;
- nenhuma repetição automática sem consentimento;
- alteração de destino invalida a restauração daquele painel;
- menor exposição de dados sensíveis;
- cookies e conteúdo interno permanecem responsabilidade dos respectivos programas;
- versões futuras podem evoluir o esquema mediante migração explícita.
