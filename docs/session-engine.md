# Session Engine operacional

A configuração estrutural dos workspaces continua armazenada no catálogo `workspaces.json`. O estado operacional entre reinicializações é mantido separadamente em:

```text
${XDG_STATE_HOME:-$HOME/.local/state}/triview-workspace/sessions/<workspace-id>.json
```

## Contrato

Cada sessão possui esquema versionado, workspace, layout, painel em foco, modo de visualização, data do checkpoint e estados permitidos por tipo de painel.

Estados suportados:

- Browser: URL atual sanitizada;
- Application: diretório de trabalho;
- Terminal: diretório de trabalho, sem histórico de comandos;
- PDF: arquivo, página e zoom;
- Custom: nenhum estado operacional automático.

## Segurança

A persistência usa allowlist por tipo de painel. Senhas, tokens, cookies, credenciais, histórico, clipboard e perfis de navegador não são gravados. Parâmetros sensíveis são removidos de URLs, fragmentos não são preservados e os arquivos recebem permissão `0600`.

Duplicar um workspace copia apenas sua configuração estrutural. A sessão operacional do workspace original não é copiada.

## Recuperação

O TriView cria checkpoints periódicos e antes do encerramento normal ou emergencial. Na inicialização:

1. o catálogo estrutural é carregado e migrado;
2. cada sessão é analisada de forma independente;
3. estado suportado é aplicado em memória;
4. esquema incompatível é ignorado com diagnóstico;
5. entradas individuais inválidas são descartadas sem bloquear os outros painéis;
6. arquivo corrompido é isolado com sufixo `invalid-<data>`;
7. o runtime Browser/Xephyr aprovado não é substituído nem modificado.

A sessão operacional não é promovida automaticamente ao catálogo estrutural e não altera arquivos de configuração compartilháveis.
