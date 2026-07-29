# Changelog

## 1.0.0a3 — Controladores e quatro atalhos estáveis

- adiciona `scripts/stable-launch.sh` com instância única, ativação da janela existente, dependências X11, logs e proveniência do runtime;
- adiciona `scripts/stable-diagnose.sh` para executar o diagnóstico caixa-preta sanitizado sobre a instalação estável;
- instala controladores versionados de abertura, atualização, diagnóstico e rollback em `~/.local/share/triview-workspace/updater/`;
- instala quatro comandos oficiais em `~/.local/bin` e quatro atalhos em Applications e Área de Trabalho;
- passa a copiar os controladores da release que ficou ativa, em vez de restaurar arquivos antigos do processo que iniciou a atualização;
- preserva os controladores após a sobrescrita do núcleo legado e após a segunda atualização;
- adiciona testes funcionais do launcher, da instância única, da passagem de argumentos e do pacote de diagnóstico;
- inclui launcher e diagnóstico no gatilho e no gate completo da publicação.

Nenhum módulo de GUI, Browser, Xephyr, workspace ou coletor de diagnóstico fisicamente aceito foi alterado.

## 1.0.0a2 — Rollback estável verificável

- adiciona `scripts/stable-rollback.sh` para restaurar backups controlados da instalação estável;
- recusa backups fora da raiz oficial e valida estrutura, versão, compilação, diagnóstico e módulo principal antes da troca;
- bloqueia rollback enquanto o TriView está ativo ou quando outra operação de ciclo de vida possui o lock;
- cria backup pré-rollback da versão corrente e preserva o catálogo e os demais dados persistentes;
- restaura o código em novo diretório de release e substitui o link `current` atomicamente;
- atualiza versão e canal por escrita atômica e gera log e relatório JSON auditável;
- permite operação inversa usando automaticamente o backup pré-rollback mais recente;
- instala comando e atalho oficial **Restaurar TriView Workspace** junto do atualizador persistente;
- adiciona testes de restauração, reversão, dry-run, confinamento de caminho, preservação de dados e persistência do controlador;
- inclui o script de rollback no gate completo de publicação da release.

Nenhum módulo de GUI, Browser, Xephyr, workspace ou diagnóstico funcional fisicamente aceito foi alterado.

## 1.0.0a1 — Liberação RC4 aceita

- consolida a interface RC4 proporcional aprovada no Linux Mint;
- mantém workspaces vivos por `park/restore`, sem destruir ou relançar sessões ao alternar;
- preserva PID, PGID, Window ID, conversa, rolagem e foco durante a mesma execução;
- encaminha roda e teclado ao Browser Panel correto;
- inicia navegadores dentro de Xephyr autenticado, impedindo exposição externa antes da incorporação;
- adiciona diagnóstico caixa-preta sanitizado com linha do tempo correlacionada de usuário, sistema, X11 e TriView;
- distingue eventos físicos de eventos sintéticos XTEST no veredito do scroll;
- entrega atalhos oficiais de abertura, atualização, diagnóstico e rollback;
- reconcilia os hotfixes históricos do atualizador de `main` sem descartar o trem aceito;
- define `stable` como canal padrão e exige opt-in explícito para `testing`;
- condiciona a publicação da release à suíte completa, shell, X11, XTEST e Xephyr em PASS.

Aceite físico registrado: flash externo, scroll, teclado e continuidade entre workspaces em PASS.

## 0.9.0 — Plugin Engine

- adiciona manifestos declarativos com esquema e API versionados;
- descobre plugins somente em diretórios permitidos;
- ignora symlinks e rejeita IDs ou versões incompatíveis;
- exige ativação explícita;
- grava estado de ativação atomicamente;
- adiciona Plugin Adapter para painéis `custom`;
- executa comandos pelo Application Engine, sem shell;
- isola falhas e apresenta diagnósticos;
- adiciona gerenciador na GUI, exemplo e instalador;
- adiciona testes e ADR-0010.

## 0.8.0 — Recording Engine

- gravação individual com FFmpeg x11grab;
- botão Gravar/Parar, indicador e histórico;
- ADR-0009.

## 0.7.0 — Capture Engine

- captura individual com maim ou ImageMagick;
- botão Print e histórico;
- ADR-0008.

## 0.6.0 — PDF Engine

- PDF Adapter, visualizadores e fallback;
- ADR-0007.

## 0.5.0 — Terminal Engine

- Terminal Adapter, shells e emuladores;
- ADR-0006.

## 0.4.0 — Application Engine e Panel Runtime

- runtime comum, aplicações e fallback;
- ADR-0005.

## 0.3.0 — Workspaces persistentes

- catálogo versionado e restaurável.

## 0.2.0 — Browser Engine

- navegador incorporado e ciclo de vida.

## 0.1.x — Fundação

- arquitetura modular, migração e interface gráfica.
