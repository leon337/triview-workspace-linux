# Changelog

## 0.3.0 — Workspaces persistentes

- adiciona catálogo JSON com `schema_version` explícito;
- grava alterações de forma atômica, sem expor arquivo parcial;
- restaura automaticamente o último workspace utilizado;
- permite criar uma cópia, renomear, editar e excluir workspaces;
- permite editar títulos, tipos e destinos dos painéis;
- permite selecionar layouts disponíveis;
- preserva ao menos um workspace para impedir catálogo vazio;
- migra automaticamente o bundle único legado para o catálogo versionado;
- preserva arquivos corrompidos com sufixo de quarentena e restaura o padrão;
- adiciona `WorkspaceSessionEngine` desacoplado da interface;
- adiciona `WorkspaceRepository` em infraestrutura;
- mantém dados fora dos diretórios versionados do atualizador;
- estende o diagnóstico com esquema, catálogo e workspace ativo;
- adiciona testes de persistência, migração, recuperação e ciclo de sessão;
- atualiza interface, README, arquitetura, roadmap e histórico.

## 0.2.0 — Primeiro Browser Engine funcional

- adiciona contrato explícito para backends de navegador;
- valida e normaliza URLs HTTP e HTTPS;
- adiciona `BrowserPanelAdapter` ao registro de painéis da interface;
- implementa backend inicial para Brave/Chromium em X11;
- incorpora a janela do navegador no host nativo do painel com `xdotool`;
- cria perfis locais separados por identidade de painel;
- adiciona estados visuais disponível, abrindo, ativo, indisponível e erro;
- mantém a interface aberta quando o backend não está disponível;
- redimensiona a janela incorporada junto com o painel;
- encerra sessões abertas ao fechar o TriView Workspace;
- preserva o modo CLI `--diagnostic` sem abrir a interface;
- adiciona testes de URL, adaptador, ciclo de vida e fallback;
- registra a ADR-0003 sobre a estratégia X11 inicial;
- atualiza roadmap, histórico, README e documentação dos Engines.

Limite conhecido: a incorporação inicial depende de X11, navegador Chromium compatível e `xdotool`. Um backend nativo de Wayland permanece planejado.

## Consolidação documental — LEA-194

- adiciona índice central em `docs/README.md`;
- registra visão, princípios e roadmap do produto;
- consolida o histórico explicado das versões `0.1.0`, `0.1.1` e `0.1.2`;
- documenta responsabilidades e estado dos Engines;
- cria o manual operacional da Fábrica de Softwares;
- registra a ADR-0002 sobre governança documental;
- adiciona testes para arquivos obrigatórios e links Markdown internos;
- reorganiza o README da raiz como porta de entrada para a documentação.

Esta mudança não alterou a versão funcional da aplicação.

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
