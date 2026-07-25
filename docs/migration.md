# Migração da instalação legada

## Origem confirmada

A versão legada instala os arquivos executáveis em `~/.local/share/triview-workspace-linux` e mantém as URLs em `~/.config/triview-workspace/config.json`.

O atualizador antigo exige `app.py`, `launcher.sh`, `update.sh`, `uninstall.sh`, `VERSION` e o ícone diretamente na raiz do repositório. A arquitetura modular usa `src/triview_workspace/`, portanto a atualização direta antiga é incompatível.

## Estratégia implementada

O migrador da LEA-192:

1. detecta a instalação antiga pelo caminho oficial ou pelos marcadores do pacote V0.1.0;
2. cria backup integral da aplicação e das configurações;
3. mantém a instalação antiga intacta;
4. instala cada versão nova em `~/.local/share/triview-workspace/releases/<versão>`;
5. troca o link `current` atomicamente;
6. cria comandos e atalhos no escopo do usuário;
7. valida a aplicação antes de concluir;
8. oferece restauração do backup mais recente.

## Dados preservados

- `~/.config/triview-workspace/config.json`;
- qualquer conteúdo do diretório de configuração legado;
- cópia integral da aplicação antiga;
- diretório persistente `~/.local/share/triview-workspace/data`;
- backups em `~/.local/share/triview-workspace-backups`.

## Segurança

Nenhum comando precisa executar o processo inteiro como root. A instalação ocorre no perfil do usuário. O modo `--dry-run` permite revisar o plano antes de alterar arquivos.
