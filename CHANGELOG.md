# Changelog

## Não lançado — Consolidação documental

- adiciona índice central em `docs/README.md`;
- registra visão, princípios e roadmap do produto;
- consolida o histórico explicado das versões `0.1.0`, `0.1.1` e `0.1.2`;
- documenta responsabilidades e estado dos Engines;
- cria o manual operacional da Fábrica de Softwares;
- registra a ADR-0002 sobre governança documental;
- adiciona testes para arquivos obrigatórios e links Markdown internos;
- reorganiza o README da raiz como porta de entrada para a documentação.

Esta mudança não altera a versão funcional da aplicação.

## 0.1.2 — Interface gráfica inicial

- corrige o atalho principal, que antes executava apenas o diagnóstico em JSON;
- adiciona uma janela desktop real que permanece aberta;
- exibe três painéis móveis responsivos;
- recalcula o layout ao maximizar, restaurar ou redimensionar;
- mantém a CLI disponível com `--diagnostic`;
- atualiza o atalho para modo gráfico sem terminal;
- adiciona log de inicialização da GUI;
- adiciona testes da seleção entre GUI e diagnóstico.

## 0.1.1 — Migração segura

- adiciona migrador da instalação legada V0.1.0;
- confirma e preserva as URLs em `~/.config/triview-workspace/config.json`;
- cria backup integral antes de qualquer alteração;
- mantém a aplicação antiga intacta;
- instala versões em diretórios versionados com troca atômica do link `current`;
- adiciona restaurador do backup mais recente;
- adiciona atualizador com fallback para a branch `main` enquanto não houver release estável;
- adiciona atalhos de abertura, atualização e restauração;
- adiciona pacote gráfico executável por duplo clique no Linux Mint;
- adiciona testes do plano de migração.

## 0.1.0 — Fundação

- estrutura modular inicial;
- modelos de workspace, layout e painel;
- Layout Engine proporcional;
- registro extensível de adaptadores;
- configuração de exemplo com três painéis móveis;
- testes automatizados e documentação arquitetural.
