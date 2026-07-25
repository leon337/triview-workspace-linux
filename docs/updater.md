# Estratégia de atualização

## Resposta operacional

O usuário não deverá baixar um ZIP completo a cada tarefa. A meta é executar um atualizador que obtenha uma release validada do GitHub.

Entretanto, o atualizador enviado na primeira distribuição ZIP **não foi validado dentro deste repositório**. Portanto, não é seguro afirmar que ele já consegue migrar para esta nova arquitetura. Sua compatibilidade depende do endereço do repositório, da estrutura de diretórios e do formato de release que ele espera.

## Modos suportados por `scripts/update.sh`

1. **Instalação Git:** faz `fetch` e `pull --ff-only` da branch configurada.
2. **Instalação empacotada:** baixa o `tar.gz` da release mais recente, preserva o diretório `data/` e substitui os arquivos da aplicação.

## Migração do atualizador legado

Antes da primeira release instalável:

- recuperar o `update.sh` do primeiro ZIP;
- comparar a origem, os caminhos e as permissões;
- criar backup automático;
- testar migração em uma cópia da instalação;
- somente então declarar atualização direta como compatível.

## Política de segurança

- nunca atualizar com alterações locais não salvas;
- fazer backup antes de substituir uma instalação empacotada;
- usar somente HTTPS;
- interromper em qualquer falha;
- não apagar dados, capturas ou gravações do usuário.
