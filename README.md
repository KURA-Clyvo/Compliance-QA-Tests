# KURA · Compliance, Quality Assurance & Tests — Sprint 4

Entrega da disciplina **Compliance, Quality Assurance & Tests** (Challenge FIAP 2026, 2TDS) para o
sistema **KURA**: gestão de continuidade veterinária com app da clínica, app do tutor e a assistente
de triagem Luna.

## Equipe

| Integrante | RM |
|---|---|
| Felipe Ferrete | RM562999 |
| Clayton Alves | RM562285 |
| Guilherme Sola | RM563674 |
| Gustavo Bosak | RM566315 |
| Nikolas Brisola | RM564371 |

## Entregáveis

| Parte | O quê | Onde |
|---|---|---|
| **A — Teste manual (80%)** | Plano e relatório de testes de sistema: 13 casos, cada um com objetivo, dados de entrada, procedimento e saída esperada; dados controlados; resultados de 2 execuções e análise | [`manual/2TDSPF_2026_PlanoTestes_KURA.pdf`](manual/2TDSPF_2026_PlanoTestes_KURA.pdf) |
| **B — Automação (20%)** | Projeto **Selenium IDE** com 5 casos automatizados (CT-01, CT-02, CT-07, CT-08, CT-11) | [`automacao/KURA-QA.side`](automacao/KURA-QA.side) · [como rodar](automacao/README-selenium-ide.md) |
| Vídeo | Configuração, execução e resultado da automação no Selenium IDE | **(link do vídeo)** |

> O plano de testes manuais foi entregue em **PDF**, no lugar do Azure Boards, por acordo da equipe
> com o professor.

## Resumo dos resultados

| Execução | Data | Resultado |
|---|---|---|
| 1ª execução | 28/10/2026 01:48 | 11 casos: 8 passaram, 1 falhou por **defeito real** (E66), 1 bloqueado por pré-condição, 1 com saída esperada corrigida |
| Reteste, depois das correções | 28/10/2026 04:13 | **12 de 12 passaram**, incluindo a regressão CT-13 do defeito E67 |
| Selenium IDE (runner de linha de comando) | 28/10/2026 | **5 de 5 passaram** |

**Defeitos encontrados pelos testes e corrigidos antes da entrega:**
- **E66:** senha errada no login aparecia como "Sem conexão".
- **E67:** CNPJ digitado sem pontuação era recusado.

Os dois foram corrigidos e retestados, com o ciclo inteiro documentado no PDF.

## Como reproduzir

1. Subir o ambiente local do KURA (Oracle, MongoDB e APIs .NET/Java) e rodar os scripts de seed do
   repositório `DevOps-Cloud`. Os dados de teste são sempre os mesmos.
2. Servir os apps web: a clínica em `http://localhost:19006` e o tutor em `http://localhost:8082`.
3. **Selenium IDE:** abrir `automacao/KURA-QA.side`, preencher as variáveis de senha **só na cópia
   local** (os valores `DEFINA_NO_IDE` são marcadores) e rodar a suíte. Detalhes em
   `automacao/README-selenium-ide.md`.
4. **Execução completa por script (opcional):** `automacao/executar_casos.py` (Python + Selenium
   WebDriver). As senhas vêm das variáveis de ambiente `DEMO_SENHA` e `DEMO_SENHA_TUTOR`; nenhuma
   senha está no repositório.

## Licença

Licença proprietária source-available. Ver [`LICENSE`](LICENSE).
