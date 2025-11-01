from playwright.sync_api import sync_playwright
import os, threading, re
from datetime import datetime

AUTH_FILE = "cognigy_state.json"
stop_flag = False


def wait_for_stop():
    global stop_flag
    input("\n💡 Pressione ENTER a qualquer momento para parar o processo...\n")
    stop_flag = True


def get_apply_count(page):
    try:
        btn = page.locator("button:has-text('Apply')").first
        if btn and btn.is_visible():
            text = btn.inner_text().strip()
            match = re.search(r"Apply\s*\((\d+)\)", text)
            return int(match.group(1)) if match else 0
    except Exception as e:
        print(f"⚠️ Erro ao ler Apply count: {e}")
    return 0


def scroll_to_load_more(page):
    try:
        old_count = page.locator("button[aria-label*='Ignore']").count()
        last_btn = page.locator("button[aria-label*='Ignore']").last
        if last_btn.is_visible():
            last_btn.scroll_into_view_if_needed()
            page.wait_for_timeout(800)
        page.wait_for_function(
            f"document.querySelectorAll('button[aria-label*=\"Ignore\"]').length > {old_count}",
            timeout=4000,
        )
    except Exception:
        page.mouse.wheel(0, 800)
    page.wait_for_timeout(800)


def is_selected_blue(page, btn):
    try:
        color = btn.evaluate("el => window.getComputedStyle(el).backgroundColor")
        return '0, 97, 255' in color or 'rgb(0, 97, 255)' in color
    except Exception:
        return False


def select_flow(page, flow_name):
    print(f"🔽 Selecionando flow '{flow_name}'...")
    page.wait_for_selector("#flowSelectId", timeout=20000)
    flow_input = page.locator("#flowSelectId")
    flow_input.click()
    page.fill("#flowSelectId", flow_name)
    page.keyboard.press("Enter")
    page.wait_for_timeout(3000)
    print(f"✅ Flow '{flow_name}' selecionado com sucesso!\n")


def apply_changes(page):
    try:
        apply_btn = page.locator("button:has-text('Apply')").first
        if apply_btn.is_visible():
            apply_btn.click(timeout=8000)
            page.wait_for_timeout(3000)
            print("✅ Apply executado com sucesso!\n")
        else:
            print("⚠️ Botão Apply não visível.")
    except Exception as e:
        print(f"⚠️ Erro ao tentar aplicar: {e}")


def run(playwright):
    global stop_flag

    browser = playwright.chromium.launch(headless=False, args=["--start-maximized"], slow_mo=100)

    if os.path.exists(AUTH_FILE):
        context = browser.new_context(storage_state=AUTH_FILE, viewport=None)
    else:
        context = browser.new_context(viewport=None)

    page = context.new_page()

    if not os.path.exists(AUTH_FILE):
        page.goto("https://app-us.cognigy.ai/login")
        input("⚙️ Faça login e pressione ENTER quando o painel estiver carregado...")
        context.storage_state(path=AUTH_FILE)
        print("💾 Sessão salva em cognigy_state.json.")

    trainer_url = "https://app-us.cognigy.ai/project/664ceec434d705675ccfb939/68d4459ac3bf99944bb5eafc/trainer"
    page.goto(trainer_url)
    page.wait_for_selector("button[aria-label*='Ignore']", timeout=60000)

    #flow_name = input("Digite o nome exato do flow que deseja usar: ").strip()
    flow_name = "00 - Gerador de tokens [aux]"
    select_flow(page, flow_name)

    max_to_ignore = 11
    ciclo = 1
    threading.Thread(target=wait_for_stop, daemon=True).start()

    print("\n🚀 Iniciando processo contínuo de ignorar intents...\n")

    while not stop_flag:
        print(f"\n📊 Iniciando {ciclo}° ciclo (meta: {max_to_ignore} ignores)...")
        start_count = get_apply_count(page)
        clicked_batch = 0

        while (get_apply_count(page) - start_count) < max_to_ignore and not stop_flag:
            buttons = page.locator("button[aria-label*='Ignore']")
            total = buttons.count()

            if total == 0:
                scroll_to_load_more(page)
                continue

            for i in range(total):
                if stop_flag:
                    break

                try:
                    btn = buttons.nth(i)
                    if not (btn.is_visible() and btn.is_enabled()):
                        continue

                    if is_selected_blue(page, btn):
                        continue

                    btn.scroll_into_view_if_needed()
                    btn.click(force=True, timeout=3000)
                    page.wait_for_timeout(800)
                    clicked_batch += 1

                    new_count = get_apply_count(page)
                    print(f"✅ [{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] Intents ignorados: {new_count}")

                    if clicked_batch >= 3:
                        page.mouse.wheel(0, 385)
                        page.wait_for_timeout(1000)
                        clicked_batch = 0

                    if new_count - start_count >= max_to_ignore:
                        break

                except Exception as e:
                    print(f"⚠️ Erro ao clicar no botão {i+1}/{total}: {e}")
                    page.wait_for_timeout(800)

        delta = get_apply_count(page) - start_count
        if delta > 0:
            print(f"\n💾 {ciclo}° ciclo concluído — {delta} de {max_to_ignore} intents ignoradas.\nAplicando mudanças...")
            apply_changes(page)
        else:
            print(f"⚠️ Nenhuma intent nova para aplicar no {ciclo}° ciclo.\n")

        if not stop_flag:
            ciclo += 1
            scroll_to_load_more(page)
            page.wait_for_timeout(2000)

    print("\n🏁 Processo interrompido pelo usuário.")
    browser.close()


if __name__ == "__main__":
    with sync_playwright() as pw:
        run(pw)
