from playwright.sync_api import sync_playwright
import os, threading, re
from datetime import datetime
import pyautogui
import time

AUTH_FILE = "cognigy_state.json"
stop_flag = False

def wait_for_stop():
    global stop_flag
    input("\n💡 Pressione ENTER a qualquer momento para parar o processo...\n")
    stop_flag = True

def get_apply_count(page):
    """Retorna o número dentro do botão Apply (ex: Apply (15) -> 15)"""
    try:
        btn = page.locator("button:has-text('Apply')").first
        if btn.is_visible():
            text = btn.inner_text().strip()
            match = re.search(r"Apply\s*\((\d+)\)", text)
            return int(match.group(1)) if match else 0
    except:
        pass
    return 0

def is_selected_blue(page, btn):
    """Verifica se o botão já está selecionado (fundo azul)"""
    try:
        color = btn.evaluate("el => window.getComputedStyle(el).backgroundColor")
        return '0, 97, 255' in color or 'rgb(0, 97, 255)' in color
    except:
        return False

def select_flow(page, flow_name):
    print("🔍 Reduzindo zoom para 33% via PyAutoGUI...")
    print("Você tem 6 segundos para clicar na aba do CHROME")
    time.sleep(6)
    for _ in range(6):
        pyautogui.hotkey('ctrl', '-')
        time.sleep(0.2)

    print(f"🔽 Selecionando flow '{flow_name}'...")
    page.wait_for_selector("#flowSelectId", timeout=20000)
    flow_input = page.locator("#flowSelectId")
    flow_input.click()
    page.fill("#flowSelectId", flow_name)
    page.keyboard.press("Enter")
    page.wait_for_timeout(3000)
    print(f"✅ Flow '{flow_name}' selecionado com sucesso!\n")

def apply_changes(page):
    """Clica no botão Apply para confirmar alterações"""
    try:
        apply_btn = page.locator("button:has-text('Apply')").first
        if apply_btn.is_visible():
            apply_btn.click(timeout=8000)
            page.wait_for_timeout(3000)
            print("✅ Apply executado com sucesso!\n")
        else:
            print("⚠️ Botão Apply não visível.")
    except:
        print("⚠️ Erro ao clicar em Apply.")

def run(playwright):
    global stop_flag

    browser = playwright.chromium.launch(headless=False, args=["--start-maximized"], slow_mo=100)
    context = browser.new_context(storage_state=AUTH_FILE, viewport=None) if os.path.exists(AUTH_FILE) else browser.new_context(viewport=None)
    page = context.new_page()

    if not os.path.exists(AUTH_FILE):
        page.goto("https://app-us.cognigy.ai/login")
        input("⚙️ Faça login e pressione ENTER quando o painel estiver carregado...")
        context.storage_state(path=AUTH_FILE)
        print("💾 Sessão salva em cognigy_state.json.")

    page.goto("https://app-us.cognigy.ai/project/664ceec434d705675ccfb939/68d4459ac3bf99944bb5eafc/trainer")
    page.wait_for_selector("button[aria-label*='Ignore']", timeout=60000)
    
    #flow_name = input("Digite o nome exato do flow que deseja usar: ").strip()
    flow_name = "00.6 - Continuação [aux]"
    select_flow(page, flow_name)

    max_to_ignore = 21
    threading.Thread(target=wait_for_stop, daemon=True).start()
    ciclo = 1
    total_ignored = 0
    same_count_cycles = 0  # contador de ciclos sem progresso

    print("\n🚀 Iniciando processo contínuo de ignorar intents...\n")

    while not stop_flag:
        print(f"\n📊 Iniciando {ciclo}° ciclo (meta: {max_to_ignore} intents)...")
        start_count = get_apply_count(page)
        ignored_this_cycle = 0
        same_count_in_cycle = 0
        last_apply_count = start_count

        while not stop_flag and ignored_this_cycle < max_to_ignore:
            buttons = page.locator("button[aria-label*='Ignore']")
            total = buttons.count()
            progress = False

            # Se não tiver mais nada pra ignorar, para o bot
            if total == 0:
                print("\n🏁 Nenhuma intent restante no flow. Encerrando automaticamente...")
                stop_flag = True
                break

            for i in range(total):
                if stop_flag or ignored_this_cycle >= max_to_ignore:
                    break

                btn = buttons.nth(i)
                if not (btn.is_visible() and btn.is_enabled()):
                    continue
                if is_selected_blue(page, btn):
                    continue

                try:
                    page.wait_for_timeout(300)
                    btn.evaluate("el => el.scrollIntoView({block:'center', behavior:'smooth'})")
                    page.wait_for_timeout(500)
                    btn.click(force=True, timeout=3000)
                    page.wait_for_timeout(500)

                    current_apply_count = get_apply_count(page)
                    ignored_this_cycle = current_apply_count - start_count
                    print(f"✅ [{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] Apply count atual: {current_apply_count}")
                    progress = True

                    # 🔹 Se o apply count não muda por 10 tentativas seguidas, encerra o ciclo
                    if current_apply_count == last_apply_count:
                        same_count_in_cycle += 1
                    else:
                        same_count_in_cycle = 0
                        last_apply_count = current_apply_count

                    if same_count_in_cycle >= 10:
                        print("\n⚠️ Nenhum avanço detectado nas últimas 10 tentativas. Encerrando ciclo atual.")
                        stop_flag = True
                        break

                    if ignored_this_cycle >= max_to_ignore:
                        break

                except:
                    continue

            if not progress:
                page.mouse.wheel(0, 400)
                page.wait_for_timeout(1000)

        delta = get_apply_count(page) - start_count
        if delta > 0:
            total_ignored += delta
            same_count_cycles = 0
            print(f"\n💾 {ciclo}° ciclo concluído — {delta} intents ignoradas neste ciclo.")
            print(f"📈 Total acumulado desde o início: {total_ignored}")
            apply_changes(page)
        else:
            same_count_cycles += 1
            print(f"\n⚠️ Nenhuma intent nova para aplicar no {ciclo}° ciclo. ({same_count_cycles} sem progresso)")
            if same_count_cycles >= 3:
                print(f"\n🏁 Nenhum progresso em 3 ciclos consecutivos. Encerrando o bot.")
                stop_flag = True
                break

        ciclo += 1
        page.wait_for_timeout(2000)

    print(f"\n🏁 Processo finalizado com sucesso. Total geral de intents ignoradas: {total_ignored}")
    browser.close()

if __name__ == "__main__":
    with sync_playwright() as pw:
        run(pw)
