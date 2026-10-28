# KURA-QA.side - Record & Playback (Selenium IDE)

Projeto `KURA-QA.side` (formato Selenium IDE 4, `version 2.0`), suíte **"KURA - Regressao QA Sprint 4"** com 5 testes
automatizados. Pré-requisito: apps locais no ar - clínica `http://localhost:19006`, tutor `http://localhost:8082`.

## Abrir e preparar no Selenium IDE
1. Selenium IDE -> *Open an existing project* -> `KURA-QA.side`.
2. **Senhas (somente na sua cópia local, nunca commitar):** em cada teste o primeiro comando é um `store` com o valor
   `DEFINA_NO_IDE`. Troque-o pela senha real:
   - `senhaGestor` (usuário `demo@kura.local`, `DEMO_SENHA`): testes CT-01, CT-08, CT-07;
   - `senhaTutor` (usuário `tutor1-demo@kura.local`, `DEMO_SENHA_TUTOR`): teste CT-11.
   Por que em cada teste e não num teste "00" único: no `selenium-side-runner` 4.0.13 a opção `persistSession` não
   preservou a sessão entre testes (o 1º `open` do teste seguinte falhou com `invalid session id`), então as variáveis
   não podem ser herdadas. A suíte está com `persistSession: false`.
3. Selecione a suíte e clique em *Run all tests in suite*. Cuidado: **não digite senha errada do tutor** (5 erros
   bloqueiam a conta por 15 min). A única senha errada é a do CT-02 (clínica).

## O que cada teste verifica
| Teste | Fluxo | Verificações |
|---|---|---|
| CT-01 Login gestor | login `demo@kura.local` | `greeting-block` presente; caminho da URL = `/dashboard` |
| CT-02 Login senha errada | senha `SenhaErrada123` | texto "E-mail ou senha incorretos" presente; "Sem conex..." ausente; `nav-drawer` ausente |
| CT-08 Fila da Luna | login, menu Luna | `fila-luna-lista` presente; `total-triagens` = "Total de triagens: 4" (massa do seed) |
| CT-11 Loja do tutor | login tutor, aba Loja | `loja-aviso` igual ao aviso literal de pré-lançamento; `loja-grade` presente |
| CT-07 Veterinário sem financeiro | gestor cria vet `vet.ide+<Date.now()>@kura.local` (senha `VetIde12345`), sai, entra como vet | `btn-ver-painel-financeiro` e `btn-painel-financeiro` ausentes; `/financeiro` redireciona para `/dashboard`; "Painel de gestão" ausente |

Observações: o CT-07 **cria um usuário veterinário novo a cada execução** (e-mail único gerado por `execute script`).
Os cliques nos itens do menu lateral usam `execute script` (`element.click()`), porque o Selenium os considera não
visíveis (mesmo fallback do script Python). Nenhum seletor `css=.css-*` (classes geradas) é usado.

## Rodar pela linha de comando
```
npx selenium-side-runner@4.0.13 -c "browserName=chrome goog:chromeOptions.args=[headless=new,window-size=1280,900]" -w 1 -t 15000 -T 100000 -o <pasta_sem_espacos> <copia_local_com_senhas>.side
```
O runner 4.0.13 **não tem** `--output-format` nem injeção de variáveis: grava JSON (`-o`) e as senhas precisam estar
no `.side` usado - use uma **cópia fora do repositório** e apague-a depois. Evite caminhos com espaço em `-o`
(o runner corta o caminho no espaço). Não use `-d` (modo debug imprime os valores de `store`).
