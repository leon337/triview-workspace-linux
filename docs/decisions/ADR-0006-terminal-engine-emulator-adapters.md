# ADR-0006 — Terminal Engine por adaptação de emuladores

Status: aceito

Data: 2026-07-25

## Contexto

Um shell como Bash não cria uma janela gráfica por conta própria. Para exibi-lo em um painel, o TriView precisa iniciar um emulador de terminal e entregar a ele o shell configurado.

Os emuladores Linux usam argumentos diferentes e alguns reutilizam processos existentes, o que pode impedir a localização da janela pelo PID.

## Decisão

O `TerminalEngine` reutiliza o `PanelRuntime` e escolhe um emulador instalado entre `xterm`, `xfce4-terminal`, `gnome-terminal`, `kitty`, `alacritty` e `konsole`.

A variável `TRIVIEW_TERMINAL` pode priorizar um emulador específico. Cada emulador possui uma tradução explícita de argumentos. O shell configurado no painel é validado e executado sem shell intermediário.

Quando a janela pode ser localizada, ela é incorporada. Caso contrário, o terminal permanece externo com estado visual explícito.

## Consequências

- shells permanecem configuráveis;
- não existe dependência obrigatória de um único terminal;
- o código de processo e X11 continua centralizado no Panel Runtime;
- a compatibilidade visual precisa ser validada por emulador no Linux Mint;
- Wayland nativo permanece fora deste marco.
