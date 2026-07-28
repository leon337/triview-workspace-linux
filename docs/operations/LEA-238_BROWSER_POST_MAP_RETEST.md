# LEA-238 — Reteste de Browser após correção de reparenting pós-map

## Escopo

Validar somente os painéis Browser 1 e Browser 2 no Linux Mint. O Terminal já possui evidência física de PASS e não deve ser alterado.

## Critérios

1. O navegador deve abrir dentro do painel correspondente.
2. A janela não pode permanecer externa.
3. O Cinnamon/Muffin não pode retomar a janela após o `windowmap`.
4. Reabrir pelo menu deve manter o mesmo comportamento.
5. Fechar o TriView não pode deixar janelas órfãs.
