# ADR-0004 — Catálogo versionado de workspaces fora do código

## Status

Aceita na LEA-196.

## Contexto

As versões anteriores carregavam um bundle JSON presente no repositório. Esse modelo era suficiente para a demonstração inicial, mas não permitia criar, editar ou restaurar workspaces sem alterar arquivos do código. Também havia risco de uma atualização substituir configurações locais.

## Decisão

O TriView Workspace manterá um catálogo persistente separado do código, com:

- `schema_version` explícito;
- `active_workspace_id`;
- coleção de layouts;
- coleção de workspaces;
- gravação por arquivo temporário e substituição atômica;
- migração do bundle único legado;
- quarentena de arquivo inválido recuperável;
- restauração segura do workspace padrão.

Local padrão:

```text
$XDG_DATA_HOME/triview-workspace/workspaces.json
```

Fallback:

```text
~/.local/share/triview-workspace/workspaces.json
```

A interface usa o `WorkspaceSessionEngine`. O Engine delega a persistência ao `WorkspaceRepository`, que não conhece Tkinter.

## Consequências positivas

- workspaces sobrevivem às atualizações;
- o último workspace pode ser restaurado automaticamente;
- persistência pode ser testada sem servidor gráfico;
- o formato pode evoluir por migrações de esquema;
- arquivos corrompidos não são apagados silenciosamente;
- interface, domínio e armazenamento permanecem desacoplados.

## Consequências e limites

- mudanças incompatíveis exigem migração de esquema;
- o catálogo precisa permanecer consistente entre layouts e workspaces;
- cookies, autenticação e processos de navegador não fazem parte deste catálogo;
- sincronização em nuvem não está incluída;
- a criação gráfica completa de layouts permanece posterior.

## Alternativas rejeitadas

### Salvar dentro do diretório da release

Rejeitada porque o atualizador troca diretórios versionados e poderia perder ou duplicar dados do usuário.

### Alterar diretamente `config/workspaces/three-mobile.json`

Rejeitada porque mistura exemplo de distribuição com estado pessoal e dificulta restauração segura.

### Banco de dados nesta etapa

Adiado. O volume e a estrutura atuais são compatíveis com JSON versionado e gravação atômica. Um banco poderá ser avaliado quando houver histórico extenso, sincronização ou concorrência real.
