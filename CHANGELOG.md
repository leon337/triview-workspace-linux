# Changelog

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
