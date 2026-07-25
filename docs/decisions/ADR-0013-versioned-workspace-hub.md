# ADR-0013 — Workspace Hub local, versionado e sem execução na prévia

Status: aceito

Data: 2026-07-25

## Contexto

Workspaces precisam ser reutilizados, compartilhados e transformados em templates sem permitir sobrescrita silenciosa, importações incompatíveis ou execução de painéis durante a inspeção do arquivo.

## Decisão

O Workspace Hub utiliza documentos JSON com esquema explícito e dois tipos permitidos: `workspace` e `template`.

A biblioteca local:

- mantém arquivos independentes do catálogo operacional;
- grava documentos e metadados atomicamente;
- oferece busca, categorias e favoritos;
- rejeita versões incompatíveis, arquivos excessivos e links simbólicos;
- impede substituição silenciosa de itens existentes;
- apresenta apenas uma prévia estrutural, sem abrir URLs, comandos ou aplicações;
- cria workspaces e layouts com identificadores novos ao reutilizar um item;
- permite exportação para compartilhamento por arquivo.

## Consequências

- templates não compartilham identidade persistente com o original;
- importar um arquivo não executa seu conteúdo;
- colisões são tratadas explicitamente;
- o formato pode evoluir mediante incremento de `hub_schema_version`;
- dados do candidato continuam isolados pelos diretórios XDG do instalador modular.
