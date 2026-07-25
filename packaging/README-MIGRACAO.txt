TRIVIEW WORKSPACE — MIGRAÇÃO SEGURA 0.1.1

1. Extraia o ZIP completo.
2. Abra a pasta extraída.
3. Clique duas vezes em MIGRAR.desktop.
4. Escolha "Executar" ou "Executar no terminal".
5. Confirme a migração quando solicitado.

O migrador:
- detecta a instalação antiga em ~/.local/share/triview-workspace-linux;
- também detecta a pasta antiga quando o pacote foi extraído dentro dela;
- cria backup integral antes de instalar;
- preserva ~/.config/triview-workspace/config.json, onde ficam as URLs;
- não apaga a instalação antiga;
- instala a nova base em ~/.local/share/triview-workspace;
- cria atalhos no menu para abrir, atualizar e restaurar.

SIMULAÇÃO SEM ALTERAR O COMPUTADOR
Abra um terminal nesta pasta e execute:

  ./migrar.sh --dry-run

RESTAURAÇÃO
Use RESTAURAR.desktop. O backup fica em:

  ~/.local/share/triview-workspace-backups/

Observação: esta versão instala a fundação modular e o novo sistema de atualização.
A interface final com painéis de aplicações e captura individual será entregue nas tarefas seguintes.
