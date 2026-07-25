# ADR-0010 — Plugins declarativos, versionados e explicitamente ativados

Status: aceito

Data: 2026-07-25

## Contexto

Carregar módulos Python arbitrários permitiria que um plugin executasse código com os mesmos privilégios do usuário. Isso ampliaria riscos de segurança, estabilidade e compatibilidade.

## Decisão

A primeira API de plugins é declarativa. Cada plugin vive em um subdiretório permitido e contém apenas `manifest.json` com:

- esquema e API versionados;
- ID igual ao nome do diretório;
- nome e descrição;
- comando base;
- autorização explícita ou não para argumentos adicionais.

Plugins válidos permanecem desativados até serem incluídos em `enabled-plugins.json`. O comando é executado pelo Application Engine, sem shell. Diretórios ou manifestos simbólicos são ignorados. Falhas geram diagnósticos e não encerram a aplicação.

## Consequências

- nenhum código Python de terceiros é importado;
- ativação não é silenciosa;
- API incompatível é rejeitada;
- plugins reutilizam Panel Runtime e fallback externo;
- capacidades avançadas exigirão futuras versões explícitas da API;
- um marketplace futuro precisará acrescentar assinatura e origem confiável.
