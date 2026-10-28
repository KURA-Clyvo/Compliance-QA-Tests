# -*- coding: utf-8 -*-
"""
Execucao automatizada (Selenium WebDriver, Python) dos casos de teste de sistema CT-01..CT-11 e CT-13
do KURA, contra os builds web LOCAIS (clinica :19006, tutor :8082).

- Casos: .superpowers/sdd/KURA_BACKLOG_S4_QA/casos-de-teste.md (CT-12 NAO e executado: defeito E65 documentado).
- Locators: s4-qa-mapa-telas.md. No web, testID vira data-testid e accessibilityLabel vira aria-label.
- Senhas: lidas das variaveis de ambiente DEMO_SENHA e DEMO_SENHA_TUTOR; NUNCA impressas/gravadas.
- Esperas explicitas (WebDriverWait); sem implicit wait.
- Cuidado com o tutor: nunca digitar senha errada (5 erros bloqueiam a conta por 15 min).

Uso:  py executar_casos.py [CT-01 CT-02 ...]   (requer DEMO_SENHA e DEMO_SENHA_TUTOR no ambiente)
Saida: evidencias/execucao-<AAAAMMDD-HHMM>/CT-XX.png + resultados.json
"""
import json
import os
import re
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import selenium
from selenium import webdriver
from selenium.common.exceptions import NoAlertPresentException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

CLINICA = "http://localhost:19006"
TUTOR = "http://localhost:8082"
SENHA_GESTOR = os.environ["DEMO_SENHA"]
SENHA_TUTOR = os.environ["DEMO_SENHA_TUTOR"]
SENHA_VET = "VetQa12345"  # valor ficticio de teste local; pode aparecer no relatorio
TS = datetime.now().strftime("%Y%m%d%H%M%S")

RAIZ = Path(__file__).resolve().parent.parent
# EXEC_PASTA=<nome da pasta existente> reaproveita a execucao (reexecucao de casos com locator corrigido):
# os resultados dos casos reexecutados substituem os anteriores no resultados.json e a tentativa e contada.
_nome = os.environ.get("EXEC_PASTA") or ("execucao-" + datetime.now().strftime("%Y%m%d-%H%M"))
PASTA = RAIZ / "evidencias" / _nome
PASTA.mkdir(parents=True, exist_ok=True)

CTX = {"d": None, "w": None, "app": None}   # driver corrente
RESULTADOS = []
DADOS = {}   # valores gerados em runtime (cpf, e-mails)


# ---------------------------------------------------------------- helpers de driver
def abrir_driver(app):
    """Abre um Chrome headless novo para 'clinica' (desktop) ou 'tutor' (celular)."""
    fechar_driver()
    o = webdriver.ChromeOptions()
    o.add_argument("--headless=new")
    o.add_argument("--window-size=" + ("1280,1300" if app == "clinica" else "430,900"))
    d = webdriver.Chrome(options=o)
    CTX.update(d=d, w=WebDriverWait(d, 30), app=app)
    return d


def fechar_driver():
    if CTX["d"] is not None:
        try:
            CTX["d"].quit()
        except Exception:
            pass
    CTX.update(d=None, w=None, app=None)


def d():
    return CTX["d"]


def w():
    return CTX["w"]


def norm(txt):
    """Normaliza espacos (inclui NBSP U+00A0) para comparar textos."""
    return " ".join(txt.replace(" ", " ").split())


def corpo():
    return norm(d().find_element(By.TAG_NAME, "body").text)


def esperar_texto(txt, timeout=30):
    WebDriverWait(d(), timeout).until(lambda x: txt in corpo())


def css(seletor, timeout=30):
    return WebDriverWait(d(), timeout).until(EC.presence_of_element_located((By.CSS_SELECTOR, seletor)))


def tid(testid, timeout=30):
    return css('[data-testid="%s"]' % testid, timeout)


def clicar_el(el):
    try:
        d().execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        WebDriverWait(d(), 10).until(EC.element_to_be_clickable(el))
        el.click()
    except Exception:
        d().execute_script("arguments[0].click();", el)   # fallback (elemento coberto por overlay)


def clicar_tid(testid, timeout=30):
    el = WebDriverWait(d(), timeout).until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="%s"]' % testid)))
    clicar_el(el)


def clicar_xpath(xp, timeout=30):
    el = WebDriverWait(d(), timeout).until(EC.presence_of_element_located((By.XPATH, xp)))
    clicar_el(el)
    return el


def clicar_botao_texto(texto, timeout=30):
    return clicar_xpath("//*[@role='button'][normalize-space(.)='%s']" % texto, timeout)


def digitar(el, texto):
    d().execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    clicar_el(el)
    el.clear()
    el.send_keys(texto)


def digitar_login(email, senha):
    campo_email = w().until(EC.element_to_be_clickable((By.CSS_SELECTOR, '[aria-label="E-mail"]')))
    digitar(campo_email, email)
    digitar(d().find_element(By.CSS_SELECTOR, '[aria-label="Senha"]'), senha)
    clicar_botao_texto("Entrar")


def limpar_sessao():
    """Esquece a sessao (token fica em localStorage no web)."""
    d().execute_script("try{localStorage.clear();sessionStorage.clear();}catch(e){}")
    d().delete_all_cookies()


def login_clinica(email, senha):
    d().get(CLINICA + "/login")
    limpar_sessao()
    d().get(CLINICA + "/login")
    digitar_login(email, senha)
    w().until(EC.url_contains("/dashboard"))
    css('[data-testid="greeting-block"]')


def sessao_gestor():
    """Garante driver da clinica logado como gestor (reaproveita se ja estiver no app)."""
    if CTX["app"] != "clinica":
        abrir_driver("clinica")
        login_clinica("demo@kura.local", SENHA_GESTOR)
    elif "/login" in d().current_url or d().current_url.rstrip("/") == CLINICA:
        login_clinica("demo@kura.local", SENHA_GESTOR)
    return d()


def sessao_tutor():
    if CTX["app"] != "tutor":
        abrir_driver("tutor")
        d().get(TUTOR + "/login")
        digitar_login("tutor1-demo@kura.local", SENHA_TUTOR)
        w().until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Meus pets"))
    return d()


def navegar(item):
    """Clica no item do menu lateral da clinica (nav-item-<name>)."""
    clicar_tid("nav-item-" + item)


def cpf_valido():
    """Gera um CPF valido (2 digitos verificadores) a partir do timestamp."""
    base = [int(c) for c in (TS[-9:])]
    if len(set(base)) == 1:
        base[0] = (base[0] + 1) % 10
    for n in (9, 10):
        soma = sum(base[i] * (n + 1 - i) for i in range(n))
        dv = (soma * 10) % 11
        base.append(0 if dv == 10 else dv)
    return "".join(map(str, base))


def cnpj_valido():
    """Gera um CNPJ valido (14 digitos, 2 verificadores) a partir do timestamp. Devolve so digitos."""
    base = [int(c) for c in (TS[-8:])] + [0, 0, 0, 1]
    for pesos in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
        soma = sum(b * p for b, p in zip(base, pesos))
        r = soma % 11
        base.append(0 if r < 2 else 11 - r)
    return "".join(map(str, base))


def mascarar_cnpj(c):
    return "%s.%s.%s/%s-%s" % (c[:2], c[2:5], c[5:8], c[8:12], c[12:])


# ---------------------------------------------------------------- registro de casos
def caso(cid, entrada, esperada, app):
    """Decorador: executa o caso, mede, tira screenshot, grava o resultado.
    A funcao devolve (ok:bool, obtido:str, observacao:str)."""
    def deco(fn):
        def run():
            t0 = time.time()
            SUB = os.environ.get("EXEC_SUB")
            if SUB:
                (PASTA / SUB).mkdir(exist_ok=True)
            png = (PASTA / SUB / (cid + ".png")) if SUB else PASTA / (cid + ".png")
            try:
                ok, obtido, obs = fn()
                status = "PASSOU" if ok else "FALHOU"
            except Exception as e:
                status = "FALHOU"
                msg = str(e).splitlines()[0][:300] if str(e) else ""
                obtido = "Excecao no script: %s: %s" % (type(e).__name__, msg)
                obs = "Verificar se e problema de locator/script ou defeito real. " + traceback.format_exc().splitlines()[-3].strip()
            try:
                if d() is not None:
                    d().save_screenshot(str(png))
            except Exception:
                pass
            r = {"id": cid, "status": status, "entrada": entrada, "saida_esperada": esperada,
                 "saida_obtida": obtido,
                 "evidencia": str(png.relative_to(RAIZ)).replace("\\", "/") if png.exists() else None,
                 "duracao_s": round(time.time() - t0, 1), "observacao": obs, "app": app}
            RESULTADOS.append(r)
            print("%s %s (%.1fs) - %s" % (cid, status, r["duracao_s"], obtido[:300]))
            return r
        run.cid = cid
        return run
    return deco


# ---------------------------------------------------------------- casos
@caso("CT-01", "demo@kura.local / <DEMO_SENHA>",
      "URL termina em /dashboard; greeting-block e menu lateral; rodape do menu = CRMV-DEMO-0001", "clinica")
def ct01():
    abrir_driver("clinica")
    d().get(CLINICA + "/login")
    digitar_login("demo@kura.local", SENHA_GESTOR)
    w().until(EC.url_contains("/dashboard"))
    css('[data-testid="greeting-block"]')
    css('[data-testid="nav-drawer"]')
    sec = tid("nav-drawer-user-secondary").text.strip()
    ok = d().current_url.rstrip("/").endswith("/dashboard") and sec == "CRMV-DEMO-0001"
    return ok, "url=%s; rodape=%r; greeting-block e nav-drawer presentes" % (d().current_url, sec), ""


@caso("CT-02", "demo@kura.local / SenhaErrada123",
      "Mensagem 'E-mail ou senha incorretos'; URL continua em /login; sem menu lateral", "clinica")
def ct02():
    d().get(CLINICA + "/login")
    limpar_sessao()
    d().get(CLINICA + "/login")
    digitar_login("demo@kura.local", "SenhaErrada123")
    w().until(lambda x: "incorretos" in corpo() or "Sem conex" in corpo())
    c = corpo()
    certa = "E-mail ou senha incorretos" in c
    rede = "Sem conexão. Verifique sua internet." in c
    menu = len(d().find_elements(By.CSS_SELECTOR, '[data-testid="nav-drawer"]')) > 0
    ok = certa and "/login" in d().current_url and not menu
    obtido = "mensagem 'E-mail ou senha incorretos'=%s; mensagem 'Sem conexão. Verifique sua internet.'=%s; url=%s; menu=%s" % (
        certa, rede, d().current_url, menu)
    obs = "DEFEITO REAL E66: a API devolve 422 e o app so reconhece 401, entao exibe a mensagem de rede." if rede and not certa else ""
    return ok, obtido, obs


@caso("CT-08", "Menu Luna; chip 7 dias (padrao)",
      "4 cartoes; urgencia Alta primeiro; 'Total de triagens: 4'", "clinica")
def ct08():
    sessao_gestor()
    navegar("luna")
    css('[data-testid="total-triagens"]')
    # a fila carrega depois do relatorio (skeleton primeiro): espera ao menos 1 cartao ou o estado vazio
    try:
        w().until(lambda x: x.find_elements(By.CSS_SELECTOR, '[data-testid^="fila-card-"]')
                  or x.find_elements(By.CSS_SELECTOR, '[data-testid="empty-fila"]'))
    except TimeoutException:
        pass
    time.sleep(1)
    cards = d().find_elements(By.CSS_SELECTOR, '[data-testid^="fila-card-"]')
    chips = [e.text.strip() for e in d().find_elements(By.CSS_SELECTOR, '[data-testid^="fila-urg-"]')]
    total = norm(tid("total-triagens").text)
    ok = len(cards) == 4 and total == "Total de triagens: 4" and bool(chips) and chips[0].lower().startswith("alta")
    return ok, "cartoes=%d; ordem dos chips=%s; %r" % (len(cards), chips, total), "N=%s" % total


@caso("CT-03", "Pet Bolinha (etapa 'Agendada'); clicar em Chegou",
      "Antes: Rex 'Em atendimento', Mimi 'Chegou', Bolinha 'Agendada', Rex retorno 'Agendada'; sem botao Chegou em Rex(em atendimento) e Mimi. Depois: chip da Bolinha 'Chegou' e botao some", "clinica")
def ct03():
    sessao_gestor()
    navegar("agenda")
    clicar_tid("btn-modo-hoje")
    tid("agenda-hoje-lista")
    w().until(lambda x: len(x.find_elements(By.CSS_SELECTOR, '[data-testid="agenda-hoje-card"]')) >= 1)
    time.sleep(1)

    def estado():
        res = []
        for c in d().find_elements(By.CSS_SELECTOR, '[data-testid="agenda-hoje-card"]'):
            nome = next((n for n in ("Rex", "Mimi", "Bolinha", "Thor") if n in norm(c.text)), "?")
            etapa = c.find_element(By.CSS_SELECTOR, '[data-testid^="etapa-"]').text.strip()
            botao = len(c.find_elements(By.CSS_SELECTOR, '[data-testid^="btn-chegou-"]')) > 0
            res.append((nome, etapa, botao))
        return res
    antes = estado()
    esp = {("Rex", "Em atendimento", False), ("Mimi", "Chegou", False), ("Bolinha", "Agendada", True), ("Rex", "Agendada", True)}
    ok_antes = set(antes) == esp
    card = d().find_element(By.XPATH, "//*[@data-testid='agenda-hoje-card'][contains(.,'Bolinha')]")
    clicar_el(card.find_element(By.CSS_SELECTOR, '[data-testid^="btn-chegou-"]'))
    w().until(lambda x: any(n == "Bolinha" and e == "Chegou" for n, e, _ in estado()))
    depois = estado()
    bol = [t for t in depois if t[0] == "Bolinha"][0]
    ok_depois = bol[1] == "Chegou" and bol[2] is False
    obs = "Mutacao: check-in da Bolinha so pode ser feito 1x por seed. ok_antes=%s ok_depois=%s" % (ok_antes, ok_depois)
    return ok_antes and ok_depois, "antes(nome,etapa,botaoChegou)=%s; depois=%s" % (antes, depois), obs


@caso("CT-04", "Tutor Ana Teste QA / CPF gerado / e-mail unico / 11987654321; pet Pipoca Cao Labrador M porte M",
      "Salvar desabilitado sem aviso; 'Tutor cadastrado! Agora, o primeiro pet'; 'Ana Teste QA foi cadastrado(a)!' + QR", "clinica")
def ct04():
    sessao_gestor()
    DADOS["cpf"] = cpf_valido()
    DADOS["email_tutor"] = "qa+%s@kura.local" % TS
    navegar("pacientes")
    clicar_tid("btn-novo-tutor")
    digitar(tid("input-nome-tutor"), "Ana Teste QA")
    digitar(tid("input-cpf-tutor"), DADOS["cpf"])
    digitar(tid("input-email-tutor"), DADOS["email_tutor"])
    digitar(tid("input-telefone-tutor"), "11987654321")
    btn = tid("btn-salvar-tutor")
    desab = btn.get_attribute("aria-disabled") == "true" or btn.get_attribute("disabled") is not None
    clicar_tid("checkbox-aviso-privacidade")
    w().until(lambda x: tid("btn-salvar-tutor").get_attribute("aria-disabled") != "true")
    clicar_tid("btn-salvar-tutor")
    esperar_texto("Tutor cadastrado! Agora, o primeiro pet")
    clicar_tid("chip-especie-1")
    clicar_tid("chip-raca-1")
    digitar(tid("input-nome-pet"), "Pipoca")
    clicar_tid("chip-sexo-M")
    clicar_tid("chip-porte-M")
    clicar_tid("btn-salvar-pet")
    esperar_texto("Ana Teste QA foi cadastrado(a)!")
    qr = len(d().find_elements(By.CSS_SELECTOR, '[data-testid="convite-qrcode"]')) > 0
    ok = desab and qr
    return ok, "botao Salvar desabilitado antes do aceite=%s; mensagens finais exibidas; QR=%s" % (desab, qr), \
        "CPF usado=%s; e-mail=%s" % (DADOS["cpf"], DADOS["email_tutor"])


def abrir_pet(nome):
    navegar("pacientes")
    digitar(tid("search-input"), nome)
    clicar_xpath("(//*[@role='button'][.//*[normalize-space(text())='%s']])[1]" % nome)


@caso("CT-05", "Mimi; motivo 'Pele irritada'; valor 150,00; forma Pix",
      "'Cobranca de R$ 150,00 lancada' e 'Forma: Pix'", "clinica")
def ct05():
    sessao_gestor()
    abrir_pet("Mimi")
    clicar_tid("btn-consulta")
    digitar(tid("field-motivo"), "Pele irritada")
    clicar_tid("btn-salvar")
    css('[data-testid="card-lancar-cobranca"]')
    digitar(tid("input-valor-cobranca"), "150,00")
    clicar_tid("chip-forma-Pix")
    clicar_tid("btn-lancar-cobranca")
    t = norm(tid("cobranca-confirmacao").text)
    ok = "150,00" in t and "lançada" in t and "Pix" in t
    return ok, "cobranca-confirmacao=%r" % t, ""


@caso("CT-06", "Dashboard > Ver painel financeiro",
      "Titulo 'Painel de gestao'; receita bruta inclui 150,00; '(avulso)' no mix", "clinica")
def ct06():
    sessao_gestor()
    # Ritmo humano: o resumo financeiro fica em cache 30 s (useFinanceiro.ts staleTime) e lancar cobranca NAO o invalida
    # (useCobrancas.ts). Na tentativa 1, a 3 s de CT-05, o painel mostrou 'Nenhuma cobranca' (cache velho). Espera 31 s.
    time.sleep(31)
    navegar("dashboard")
    clicar_tid("btn-ver-painel-financeiro")
    esperar_texto("Painel de gestão")
    esperar_texto("150,00")
    c = corpo()
    avulso = "(avulso)" in c
    return "150,00" in c, "'Painel de gestão' visivel; '150,00' presente; '(avulso)' no mix=%s" % avulso, ""


@caso("CT-07", "vet.qa+<ts>@kura.local / VetQa12345 (papel Veterinario) criado pelo gestor",
      "Sem botoes de financeiro; perfil 'Veterinario'; /financeiro volta para /dashboard sem 'Painel de gestao'", "clinica")
def ct07():
    sessao_gestor()
    DADOS["email_vet"] = "vet.qa+%s@kura.local" % TS
    navegar("settings")
    clicar_tid("btn-convidar")
    clicar_tid("btn-novo-usuario")
    digitar(tid("input-email-usuario"), DADOS["email_vet"])
    digitar(tid("input-senha-usuario"), SENHA_VET)
    clicar_tid("chip-papel-veterinario")
    clicar_tid("btn-salvar-usuario")
    esperar_texto(DADOS["email_vet"])
    # logout pela UI e login como o veterinario
    navegar("settings")
    clicar_tid("btn-sair")
    clicar_tid("confirm-ok")
    w().until(EC.url_contains("/login"))
    login_clinica(DADOS["email_vet"], SENHA_VET)
    sem_btn_dash = len(d().find_elements(By.CSS_SELECTOR, '[data-testid="btn-ver-painel-financeiro"]')) == 0
    navegar("settings")
    perfil = tid("vet-perfil").text.strip()
    sem_btn_cfg = len(d().find_elements(By.CSS_SELECTOR, '[data-testid="btn-painel-financeiro"]')) == 0
    d().get(CLINICA + "/financeiro")
    time.sleep(3)  # deixa o redirecionamento (useRequireGestor) acontecer
    url = d().current_url
    sem_painel = "Painel de gestão" not in corpo()
    ok = sem_btn_dash and sem_btn_cfg and "Veterin" in perfil and "/dashboard" in url and sem_painel
    obtido = "sem btn no dashboard=%s; sem btn em configuracoes=%s; perfil=%r; url apos /financeiro=%s; sem 'Painel de gestao'=%s" % (
        sem_btn_dash, sem_btn_cfg, perfil, url, sem_painel)
    return ok, obtido, "Usuario criado: %s (senha ficticia local %s)" % (DADOS["email_vet"], SENHA_VET)


@caso("CT-09", "tutor1-demo@kura.local / <DEMO_SENHA_TUTOR>; abrir Rex > aba Consultas",
      "'Meus pets.' com Rex e Mimi; em Rex, titulo 'Historico de consultas.', contador 'N · VISITAS' e um cartao por evento com data e 'VER PRONTUARIO'", "tutor")
def ct09():
    abrir_driver("tutor")
    d().get(TUTOR + "/login")
    digitar_login("tutor1-demo@kura.local", SENHA_TUTOR)
    esperar_texto("Meus pets")
    c = corpo()
    pets = "Rex" in c and "Mimi" in c
    clicar_xpath("//*[starts-with(@aria-label,'Rex')][@role='button' or @role='link' or @tabindex]")
    clicar_xpath("//*[@role='tab'][contains(normalize-space(.),'Consultas')] | (//*[normalize-space(text())='Consultas'])[1]")
    esperar_texto("Histórico de consultas")
    esperar_texto("VISITAS")
    time.sleep(2)
    c2 = corpo()
    m = re.search(r"(\d+) · VISITAS", c2)
    visitas_n = int(m.group(1)) if m else None
    botoes = c2.count("VER PRONTUÁRIO")
    datas = len(re.findall(r"\d{2}/\d{2}/\d{4}|\d{1,2} de \w+", c2))
    ok = pets and visitas_n is not None and visitas_n >= 1 and botoes >= 1
    return ok, "Meus pets com Rex=%s e Mimi=%s; titulo 'Histórico de consultas'=True; contador N · VISITAS=%s; cartoes com 'VER PRONTUÁRIO'=%d; padroes de data no corpo=%d" % (
        "Rex" in c, "Mimi" in c, visitas_n, botoes, datas), ""


@caso("CT-10", "Rex; motivo Vacina; primeiro dia e primeiro periodo disponiveis; antes, envio vazio",
      "Alerta 'Escolha o pet. Escolha o motivo. Escolha o dia. Escolha o periodo.'; depois toast 'Horario solicitado' e item 'Aguardando'", "tutor")
def ct10():
    sessao_tutor()
    d().get(TUTOR + "/")
    clicar_xpath("//*[@role='tab'][@aria-label='Agenda'] | //*[@role='tab'][contains(normalize-space(.),'Agenda')]")
    clicar_botao_texto("Solicitar")
    esperar_texto("Para quem é o horário?")
    clicar_botao_texto("Pedir horário")
    msg = ""
    try:  # alerta customizado do app (KDialog); cai para alert nativo se houver
        el_msg = tid("kdialog-mensagem", 10)
        WebDriverWait(d(), 10).until(lambda x: norm(el_msg.text) != "")
        msg = norm(el_msg.text)
        clicar_xpath("//*[starts-with(@data-testid,'kdialog-acao-')]")
    except TimeoutException:
        try:
            al = d().switch_to.alert
            msg = norm(al.text)
            al.accept()
        except NoAlertPresentException:
            msg = "(alerta nao encontrado)"
    ok_vazio = msg == "Escolha o pet. Escolha o motivo. Escolha o dia. Escolha o período."
    w().until(lambda x: len(x.find_elements(By.CSS_SELECTOR, '[data-testid="kdialog-card"]')) == 0)
    clicar_xpath("//*[@role='radio'][starts-with(@aria-label,'Rex')]")
    clicar_xpath("//*[@role='radio'][@aria-label='Vacina']")
    clicar_xpath("(//*[@aria-label='Quando fica bom para você']//*[@role='radio'])[1]")
    clicar_xpath("(//*[@aria-label='Período']//*[@role='radio'])[1]")
    clicar_botao_texto("Pedir horário para Rex")
    toast = ""
    try:
        w().until(lambda x: "Horário solicitado" in corpo())
        toast = "Horário solicitado"
    except TimeoutException:
        pass
    esperar_texto("Aguardando")
    ok = ok_vazio and toast == "Horário solicitado"
    return ok, "alerta do envio vazio=%r; toast=%r; 'Aguardando' visivel=%s" % (msg, toast, "Aguardando" in corpo()), \
        "Mutacao: cria 1 pedido de agendamento 'Aguardando' para Rex."


@caso("CT-11", "Aba Loja; filtro Higiene",
      "Aviso de pre-lancamento; 10 produtos com selo 'Exemplo' e 'Em breve' desabilitado; filtro mostra so higiene", "tutor")
def ct11():
    sessao_tutor()
    d().get(TUTOR + "/")
    clicar_xpath("//*[@role='tab'][@aria-label='Loja']")
    aviso = norm(tid("loja-aviso").text)
    w().until(lambda x: len(x.find_elements(By.CSS_SELECTOR, '[data-testid^="loja-card-"]')) >= 10)
    cards = len(d().find_elements(By.CSS_SELECTOR, '[data-testid^="loja-card-"]'))
    embreve = d().find_elements(By.CSS_SELECTOR, '[data-testid^="loja-em-breve-"]')
    desab = all(e.get_attribute("aria-disabled") == "true" or e.get_attribute("disabled") is not None for e in embreve)
    exemplo = corpo().count("Exemplo")
    clicar_tid("loja-chip-HIGIENE")
    time.sleep(1)
    filtrados = len(d().find_elements(By.CSS_SELECTOR, '[data-testid^="loja-card-"]'))
    aviso_ok = aviso == "Pré-lançamento: pagamento e entrega serão ativados quando os parceiros logísticos concluírem a integração. Nenhuma cobrança é feita."
    ok = aviso_ok and cards == 10 and len(embreve) == 10 and desab and 0 < filtrados < 10
    return ok, "aviso exato=%s; cards=%d; botoes 'Em breve'=%d (todos desabilitados=%s); selos 'Exemplo'=%d; cards apos filtro Higiene=%d" % (
        aviso_ok, cards, len(embreve), desab, exemplo, filtrados), ""


def preencher_cadastro(cnpj, email_clinica, email_vet, sufixo):
    campos = [("Nome da Clínica", "Clínica QA CNPJ"), ("CNPJ", cnpj), ("E-mail da Clínica", email_clinica),
              ("Telefone", "11987654321"), ("Endereço", "Rua QA 123, Centro"), ("Cidade", "São Paulo"),
              ("UF", "SP"), ("CEP", "01001000"), ("Nome do Veterinário", "Dra. QA Cnpj"),
              ("CRMV", "SP-" + sufixo), ("E-mail do Veterinário", email_vet),
              ("Senha", "QaCnpj12345"), ("Confirmar Senha", "QaCnpj12345")]
    for rotulo, valor in campos:
        sel = (By.CSS_SELECTOR, 'input[aria-label="%s"]' % rotulo)
        # a tela de login segue montada atras (router.push): pega so o input VISIVEL
        w().until(lambda x: any(e.is_displayed() for e in x.find_elements(*sel)))
        el = [e for e in d().find_elements(*sel) if e.is_displayed()][0]
        try:
            digitar(el, valor)
        except Exception:   # sugestao de autofill do Chrome pode cobrir o campo: Escape e repete
            d().find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            d().execute_script("arguments[0].focus();", el)
            el.send_keys(Keys.CONTROL, "a")
            el.send_keys(valor)
    clicar_botao_texto("Cadastrar")


@caso("CT-13", "Cadastrar clinica com CNPJ novo SEM mascara; depois outro e-mail com o MESMO CNPJ COM mascara",
      "1o cadastro aceito (entra no app); 2o mostra mensagem de CNPJ/e-mail ja cadastrado e NAO 'Sem conexao'", "clinica")
def ct13():
    abrir_driver("clinica")
    DADOS["cnpj_ct13"] = cnpj_valido()
    DADOS["email_ct13_a"] = "qa.cnpj+%s@kura.local" % TS
    DADOS["email_ct13_b"] = "qa.cnpj+%sb@kura.local" % TS
    d().get(CLINICA + "/login")
    limpar_sessao()
    d().get(CLINICA + "/login")
    clicar_tid("login-register-link")
    w().until(EC.url_contains("/register"))
    preencher_cadastro(DADOS["cnpj_ct13"], DADOS["email_ct13_a"], DADOS["email_ct13_a"], TS[-6:])
    try:
        w().until(lambda x: "/dashboard" in x.current_url or "Sem conexão" in corpo() or "Confira os dados" in corpo()
                  or "já cadastrado" in corpo())
    except TimeoutException:
        pass
    url1 = d().current_url
    ok1 = "/dashboard" in url1
    msg1 = "" if ok1 else corpo()[-300:]
    # sair
    if ok1:
        try:
            css('[data-testid="greeting-block"]')
            navegar("settings")
            clicar_tid("btn-sair")
            clicar_tid("confirm-ok")
            w().until(EC.url_contains("/login"))
        except Exception:
            pass
        limpar_sessao()
    d().get(CLINICA + "/login")
    clicar_tid("login-register-link")
    w().until(EC.url_contains("/register"))
    preencher_cadastro(mascarar_cnpj(DADOS["cnpj_ct13"]), DADOS["email_ct13_b"], DADOS["email_ct13_b"], TS[-6:-1] + "9")
    try:
        w().until(lambda x: "/dashboard" in x.current_url or "Sem conexão" in corpo() or "já cadastrad" in corpo()
                  or "Confira os dados" in corpo() or "Já existe" in corpo())
    except TimeoutException:
        pass
    c = corpo()
    url2 = d().current_url
    rede = "Sem conexão. Verifique sua internet." in c
    dup = ("Já existe uma clínica cadastrada com este CNPJ" in c) or ("já cadastrado" in c)
    ok2 = dup and not rede and "/dashboard" not in url2
    trecho = ""
    for chave in ("Já existe", "já cadastrado", "Sem conexão", "Confira os dados"):
        k = c.find(chave)
        if k >= 0:
            trecho = c[max(0, k - 20):k + 80]
            break
    return ok1 and ok2, "1o cadastro (CNPJ %s sem mascara): url=%s aceito=%s %s; 2o (mascara %s): duplicidade=%s; 'Sem conexao'=%s; url=%s; trecho=%r" % (
        DADOS["cnpj_ct13"], url1, ok1, msg1, mascarar_cnpj(DADOS["cnpj_ct13"]), dup, rede, url2, trecho),         "Cria 1 clinica nova no ambiente (CNPJ %s, e-mail %s)." % (DADOS["cnpj_ct13"], DADOS["email_ct13_a"])


ORDEM = [ct01, ct02, ct08, ct03, ct04, ct05, ct06, ct07, ct09, ct10, ct11, ct13]


def main():
    selecionados = sys.argv[1:]
    inicio = datetime.now()
    versao_chrome = None
    try:
        for fn in ORDEM:
            if selecionados and fn.cid not in selecionados:
                continue
            fn()
            if versao_chrome is None and CTX["d"] is not None:
                versao_chrome = CTX["d"].capabilities.get("browserVersion")
    finally:
        fechar_driver()
        meta = {"inicio": inicio.isoformat(timespec="seconds"), "fim": datetime.now().isoformat(timespec="seconds"),
                "clinica_url": CLINICA, "tutor_url": TUTOR, "selenium": selenium.__version__,
                "chrome": versao_chrome, "dados_gerados": DADOS, "commits": {"mobile-clinica-rn": "ec16881", "backend-clinica-dotnet": "a787df6"}}
        arq = PASTA / "resultados.json"
        anteriores = []
        if arq.exists() and os.environ.get("EXEC_PASTA"):
            anteriores = json.loads(arq.read_text(encoding="utf-8")).get("casos", [])
        por_id = {c["id"]: c for c in anteriores}
        for r in RESULTADOS:
            r["tentativa"] = por_id.get(r["id"], {}).get("tentativa", 0) + 1
            por_id[r["id"]] = r
        for r in anteriores:
            r.setdefault("tentativa", 1)
        casos = sorted(por_id.values(), key=lambda c: c["id"])
        arq.write_text(json.dumps({"meta": meta, "casos": casos}, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Pasta:", PASTA)


if __name__ == "__main__":
    main()
