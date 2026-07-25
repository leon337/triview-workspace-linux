# ADR-0003 — Primeiro Browser Engine por incorporação X11

- Status: aceito
- Data: 2026-07-25
- Tarefa: LEA-195

## Contexto

A versão `0.1.2` possui uma janela Tkinter com painéis responsivos, mas ainda exibe apenas placeholders. O primeiro painel funcional precisa abrir conteúdo web real sem abandonar a arquitetura modular nem voltar ao modelo de três janelas soltas e sobrepostas.

As alternativas avaliadas foram:

1. abrir o navegador externamente e apenas posicioná-lo;
2. substituir imediatamente toda a interface por outro toolkit com WebEngine;
3. incorporar uma janela Brave/Chromium no host nativo do painel usando X11;
4. adiar a funcionalidade até existir uma solução única para X11 e Wayland.

## Decisão

O primeiro Browser Engine utilizará uma arquitetura de backend substituível. O backend inicial, `X11BraveBrowserBackend`, executa Brave ou outro navegador Chromium compatível em modo aplicativo e incorpora sua janela no frame nativo do painel através de `xdotool windowreparent`.

O domínio e a interface dependem do contrato `BrowserBackend`, não diretamente de comandos X11. A URL é normalizada e limitada a HTTP ou HTTPS. Cada painel recebe um diretório de perfil separado no estado local do usuário.

## Requisitos do backend inicial

- sessão gráfica com `DISPLAY` disponível;
- Brave, Chromium ou Google Chrome compatível;
- utilitário `xdotool`;
- suporte do navegador e do gerenciador de janelas à incorporação X11.

## Consequências positivas

- conteúdo web real dentro da área do painel;
- manutenção da interface Tkinter e da arquitetura atual;
- isolamento do código específico de X11;
- possibilidade de substituir o backend posteriormente;
- mensagens controladas quando o backend não estiver disponível;
- perfis separados por identidade de painel.

## Limitações e riscos

- o backend inicial não é uma solução nativa de Wayland;
- alguns navegadores ou gerenciadores de janelas podem não aceitar reparenting da mesma forma;
- a janela precisa ser localizada após o processo iniciar;
- autenticação e persistência avançada de sessões pertencem ao futuro Session Engine;
- a incorporação deve ser validada no Linux Mint real, além dos testes headless da CI.

## Alternativas futuras

- backend nativo baseado em Qt WebEngine;
- backend Wayland específico;
- abordagem híbrida com janela externa controlada quando incorporação não for possível;
- seleção automática de backend conforme o ambiente gráfico.

## Regra de evolução

Nenhum código de workspace, layout ou persistência poderá depender diretamente de `xdotool`. Novos backends devem implementar o mesmo contrato e manter fallback explícito.
