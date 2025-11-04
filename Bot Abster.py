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
    try:
        color = btn.evaluate("el => window.getComputedStyle(el).backgroundColor")
        return '0, 97, 255' in color or 'rgb(0, 97, 255)' in color
    except:
        return False

def select_flow(page, flow_name, skip_zoom=False):
    """Seleciona o flow desejado"""
    if not skip_zoom:
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
    page.wait_for_timeout(5000)

def apply_changes(page):
    """Clica em Apply apenas se houver mudanças pendentes (valor > 0)"""
    try:
        pending = get_apply_count(page)
        if pending and pending > 0:
            apply_btn = page.locator("button:has-text('Apply')").first
            if apply_btn.is_visible() and apply_btn.is_enabled():
                print(f"🔔 Aplicando {pending} intents pendentes antes do reload...")
                apply_btn.click(timeout=8000)
                page.wait_for_timeout(2500)
                print("✅ Apply executado com sucesso!\n")
                return True
            else:
                print("⚠️ Botão Apply não visível ou não habilitado no momento.")
        else:
            print("ℹ️ Nenhuma alteração pendente para aplicar.")
    except Exception as e:
        print(f"⚠️ Erro ao tentar executar Apply: {e}")
    return False

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

    flow_name = input("Digite o nome exato do flow que deseja usar: ").strip()
    #flow_name = "00.2 - Protocolo [aux]"
    select_flow(page, flow_name)

    max_to_ignore = 22
    threading.Thread(target=wait_for_stop, daemon=True).start()
    ciclo = 1
    total_ignored = 0
    same_count_cycles = 0

    print("\n🚀 Iniciando processo contínuo de ignorar intents...\n")

    while not stop_flag:
        print(f"\n📊 Iniciando {ciclo}° ciclo (meta: {max_to_ignore} intents)...")
        start_count = get_apply_count(page)
        ignored_this_cycle = 0
        last_apply_count = start_count
        same_click_attempts = 0
        click_fail_limit = 5  # depois de X tentativas sem progresso, aplicar + reload

        while not stop_flag and ignored_this_cycle < max_to_ignore:
            buttons = page.locator("button[aria-label*='Ignore']")
            total = buttons.count()

            if total == 0:
                print("\n🏁 Nenhuma intent restante. Encerrando...")
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
                    btn.evaluate("el => el.scrollIntoView({block:'center'})")
                    page.wait_for_timeout(400)
                    btn.click(force=True, timeout=3000)
                    page.wait_for_timeout(600)

                    current_apply_count = get_apply_count(page)
                    if current_apply_count == last_apply_count:
                        same_click_attempts += 1
                        print(f"⚠️ Tentativa sem progresso ({same_click_attempts}/{click_fail_limit})")
                    else:
                        same_click_attempts = 0
                        ignored_this_cycle = current_apply_count - start_count
                        last_apply_count = current_apply_count
                        print(f"✅ [{datetime.now().strftime('%H:%M:%S')}] Contador Apply: {current_apply_count}")

                    # Se atingir o limite de tentativas sem progresso:
                    if same_click_attempts >= click_fail_limit:
                        # Primeiro: tentar aplicar o que já existe
                        applied = False
                        try:
                            applied = apply_changes(page)
                        except Exception as e:
                            print(f"⚠️ Falha ao aplicar antes do reload: {e}")

                        # aguarda um pouco para o apply refletir
                        page.wait_for_timeout(1500)

                        # atualiza contadores com base no apply
                        new_after_apply = get_apply_count(page)
                        if new_after_apply != last_apply_count:
                            print(f"🔁 Apply alterou contador: {last_apply_count} -> {new_after_apply}")

                            # Se o contador resetou para zero, significa que 'last_apply_count' intents foram aplicadas
                            if new_after_apply == 0 and last_apply_count > 0:
                                total_ignored += last_apply_count
                            # Caso contrário, soma a diferença positiva
                            elif new_after_apply > last_apply_count:
                                total_ignored += new_after_apply - last_apply_count

                            print(f"📈 Total de {total_ignored} intents ignoradas até agora.")

                        # agora sim: recarrega e reseleciona o flow
                        print("🌀 Site parece travado — recarregando trainer e reselecionando flow...")
                        try:
                            page.reload()
                            page.wait_for_selector("button[aria-label*='Ignore']", timeout=60000)
                            # Reseleciona o flow automaticamente após reload (pula zoom)
                            select_flow(page, flow_name, skip_zoom=True)
                        except Exception as e:
                            print(f"⚠️ Falha ao reload/reselecionar flow: {e}")

                        same_click_attempts = 0
                        break  # sai do for para reavaliar lista de botões após reload

                except Exception as e:
                    print(f"❌ Erro ao clicar no botão: {e}")
                    # não incrementa sem motivo; tentar próximo botão
                    continue

            # rola um pouco a lista antes de continuar
            page.mouse.wheel(0, 400)
            page.wait_for_timeout(1200)

        delta = get_apply_count(page) - start_count
        if delta > 0:
            total_ignored += delta
            same_count_cycles = 0
            print(f"\n💾 {ciclo}° ciclo concluído — {delta} intents ignoradas.")
            print(f"📈 Total acumulado: {total_ignored}")
            # garante aplicar no final do ciclo
            apply_changes(page)
        else:
            same_count_cycles += 1
            print(f"⚠️ Nenhuma intent nova no {ciclo}° ciclo. ({same_count_cycles}/3 sem progresso)")
            if same_count_cycles >= 3:
                print(f"\n🏁 Nenhum progresso em 3 ciclos consecutivos. Encerrando o bot.")
                stop_flag = True
                break

        ciclo += 1
        page.wait_for_timeout(2500)

    print(f"\n🏁 Finalizado. Total geral: {total_ignored} intents ignoradas.")
    browser.close()

if __name__ == "__main__":
    with sync_playwright() as pw:
        run(pw)
