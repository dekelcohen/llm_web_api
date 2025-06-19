# -*- coding: utf-8 -*-
"""
Created on Wed Jun 18 16:40:17 2025

@author: dekel
"""
# First time: pip install selenium plyer undetected_chromedriver
# conda activate env_dl (familypc)
# cd /d E:\views\llm_web_api
import math
import json
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import time
from plyer import notification
from loguru import logger


# ── Constants ─────────────────────────────────────────────────────────────
WAIT_DEF_TIMEOUT = 120  # seconds
WAIT_RESP = 10

# TODO:Modify to your profile to store one-time manual login before automated runs against login llm web pages
PROFILE_PATH = r"E:\views\llm_web_api\chromedriver_profiles\Profile3"

NEW_CHAT_URL = 'https://aistudio.google.com/prompts/new_chat'

# Define button constants

RUN_BUTTON_XPATH = "//button[span[contains(., 'Documents')]]"
LOCATOR_BTN_UPLOAD_FILE = (By.CSS_SELECTOR, "button[aria-label^='Insert assets']")
LOCATOR_BTN_UPLOAD_IMAGE = (By.CSS_SELECTOR,"button[aria-label^='Upload Image']")
LOCATOR_CHAT_TEXTAREA = (By.CSS_SELECTOR,"textarea[aria-label*='prompt'], textarea[aria-label*='text']")
LOCATOR_BTN_RUN_XPATH = (
    By.XPATH,
    "//button[(@type='submit' or contains(@class,'run-button'))"
    " and contains(translate(@aria-label,"
    " 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), 'run')]"
)

LOCATOR_CHAT_TURNS = (
    By.CSS_SELECTOR,
    "ms-chat-turn"
)

LOCATOR_TEXT_PARAGRAPHS = (
    By.XPATH,
    "//*[@*[contains(name(), 'ngcontent')]]"
)

LOCATOR_MODEL_ERROR = (
    By.XPATH,
    "//*[contains(@class, 'model-error')]"
)

#### XHR interception by JS injection for LLM internal api - wait for end of Thinking and get final response
# Note: It sends the response of new Chat session to /GenerateTitle internal api, to generate Title for the conversation
# This is where we intercept it
def clear_hxr_watcher_globals(browser):
    CLEAR_XHR_CODE = """    
    window._generateContentSend = null;
    """
    browser.execute_script(CLEAR_XHR_CODE)
    
def inject_xhr_watcher(browser):
    INJECT_XHR_WATCHER = """
    window._generateContentDone = false;

        (function(open, send) {
      XMLHttpRequest.prototype.open = function(method, url, async, user, pass) {
        this._trackedUrl = url;
        console.log(`[XHR Open] Method: ${method}, URL: ${url}`);
        return open.call(this, method, url, async, user, pass);
      };
    
      XMLHttpRequest.prototype.send = function(body) {
        const bodyPreview = body ? (body.length > 100 ? body.substring(0, 300) + '...' : body) : '';
        console.log(`[XHR Send] To URL: ${this._trackedUrl}, Body (first 300 chars): ${bodyPreview}`);
        if (this._trackedUrl.includes('GenerateTitle')) {
          console.log(`GenerateContent DONE: ${this._trackedUrl}`);          
          window._generateContentSend = body;
        }
        this.addEventListener('readystatechange', function() {
          console.log(`[XHR ReadyState ${this.readyState}] DONE: ${this._trackedUrl}`);            
        });
    
        return send.call(this, body);
      };
    })(XMLHttpRequest.prototype.open, XMLHttpRequest.prototype.send);

    """
    browser.execute_script(INJECT_XHR_WATCHER)

def extract_texts_from_xhr_GenerateTitle(json_str):
    """
    Parameters
    ----------
    json_str : Expected: 
     ["From image observer perspective: Where is the furthest golden handle of the large pot ?\n","From the image observer's perspective, the furthest golden handle of the large pot is located in grid cell **f2**.","!YmGlYTnNAAZzWlniU1pCB7oHe8LRLzw7ADQBEArZ1NUq3fdKxNF_5tL4OyyKCNHd6Ua9Le7u5CzrPdVWsugHEJtp...
    Raises
    ------
    Exception
        DESCRIPTION.

    Returns
    -------
    llm_response : llm text response 
    
    """
    data = json.loads(json_str)
    if len(data) < 2:
        raise Exception(f'json_str of GenerateTitle does not contain expected structure: {json_str}')
    llm_response = data[1]
    return llm_response



def wait_for_js_condition_or_timeout(browser, js_condition_script, timeout, poll_interval=5):
    start = time.time()
    while time.time() - start < timeout:        
        result = browser.execute_script(js_condition_script)
        if result:
            return True  # Condition met        
        time.sleep(poll_interval)  # Poll interval
    return False  # Timeout occurred


        
def prompt_llm(prompt: str, upload_file_path: str = None, file_type=None, max_retries=3):
    """
    Parameters
    ----------
    prompt : prompt text
    upload_file_path: optional path to a file (ex: image, pdf) to attach to prompt    
    file_type: optional string to describe the type of upload_file_path - 'image', 'file', 'video' ...
    max_retries: max number of retries on model error
    -------
    None.
    Return:
        llm_response : str - llm text response if success or None if failed
    """
    options = uc.options.ChromeOptions()

    # Set the language to English
    options.add_argument("--lang=en")
    options.add_argument(f"--user-data-dir={PROFILE_PATH}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.headless = False

    browser = uc.Chrome(options)
        
    llm_response = None
    try:
        for attempt in range(1, max_retries + 1):
            logger.info(f"Attempt {attempt} of {max_retries}")

            browser.get(NEW_CHAT_URL)

            # XHR Watcher for GenerateContent xhr requests
            inject_xhr_watcher(browser)

            # Upload an image if provided
            if upload_file_path:
                file_upload_dropdown_button = WebDriverWait(browser, WAIT_DEF_TIMEOUT).until(
                    EC.element_to_be_clickable(LOCATOR_BTN_UPLOAD_FILE)
                )
                file_upload_dropdown_button.click()
                logger.info("Clicked file_upload_dropdown_button")

                if file_type == 'image':
                    image_file_input = WebDriverWait(browser, WAIT_DEF_TIMEOUT).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "button[aria-label='Upload File'] input[type='file']"))
                    )
                    image_file_input.send_keys(str(upload_file_path))
                    logger.info(f"Uploaded image {upload_file_path}")
                         
                        
            time.sleep(2)
            
            SEND_KEYS = False
            if SEND_KEYS:
                # Insert prompt text
                chat_input = WebDriverWait(browser, WAIT_DEF_TIMEOUT).until(
                    EC.element_to_be_clickable(LOCATOR_CHAT_TEXTAREA)
                )
                chat_input.clear()
                chat_input.send_keys(prompt)
            
            PY_AUTO_GUI = True 
            if PY_AUTO_GUI:
                import pyautogui
                import random
                def human_like_typing(text, min_delay=0.01, max_delay=0.1, max_chars_before_newline=None):
                    """
                    Types out a string with a random, human-like delay between each character.
                    
                    Parameters:
                    - text: string to type
                    - min_delay: minimum delay between characters
                    - max_delay: maximum delay between characters
                    - max_chars_before_newline: insert newline after this many characters (optional)
                    """
                    char_count = 0
                    for char in text:
                        pyautogui.write(char)
                        char_count += 1
                
                        if max_chars_before_newline and char_count >= max_chars_before_newline:
                            pyautogui.press('enter')
                            char_count = 0
                
                        time.sleep(random.uniform(min_delay, max_delay))
                
                # 2) Execute JS to get midpoints of textarea & Run button
                points = browser.execute_script("""
                      try {
                        const textarea = document.querySelector("textarea[aria-label*='prompt'], textarea[aria-label*='text']");
                        const runBtn = document.evaluate(
                          "//button[(@type='submit' or contains(@class,'run-button'))"
                            + " and contains(translate(@aria-label,"
                            + " 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), 'run')]",
                          document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null
                        ).singleNodeValue;
                    
                        if (!textarea || !runBtn) return null;
                    
                        const r1 = textarea.getBoundingClientRect();
                        const r2 = runBtn.getBoundingClientRect();
                    
                        return {
                          textareaMid: { x: r1.left, y: r1.top },
                          runBtnMid: { x: r2.left + r2.width/2, y: r2.top + r2.height/2 }
                        };
                      } catch (e) {
                        return { error: e.toString() };
                      }
                    """)
                if not points:
                    raise RuntimeError("Could not find textarea or Run button via JS")
                
                from pygetwindow import getWindowsWithTitle
                chrome_window = next(w for w in getWindowsWithTitle('Google AI Studio') if w.isActive)
                win_x, win_y = chrome_window.left, chrome_window.top

                # 3) Chat input: move +100px down from midpoint
                x_input = points['textareaMid']['x']
                y_input = points['textareaMid']['y']
                pyautogui.FAILSAFE = True
                
                time.sleep(1.1)
                pyautogui.moveTo(win_x + x_input + 30, win_y + y_input + 100, duration=random.uniform(0.6, 3.2))
                pyautogui.click()
                chat_input = WebDriverWait(browser, WAIT_DEF_TIMEOUT).until(
                    EC.element_to_be_clickable(LOCATOR_CHAT_TEXTAREA)
                )
                chat_input.click()
                time.sleep(0.0)
                pyautogui.click()
                #prompt = 'From image observer perspective: Where is the furthest golden handle of the large pot utput: cell id (e.g a0, k6)'
                COPY_FROM_CLIPBOARD = True
                if COPY_FROM_CLIPBOARD:
                    import pyperclip
                    pyperclip.copy(prompt)
                    pyautogui.hotkey("ctrl", "v")
                else:
                    human_like_typing(prompt, max_chars_before_newline=40)  # TODO:Restore:promptFrom i
                
                time.sleep(1.1)
                
                # 4) Run button: use the midpoint +100px
                x_run = points['runBtnMid']['x']
                y_run = points['runBtnMid']['y'] + 100
                
                logger.info(f"btn_run x,y: {x_run},{y_run}")
                #pyautogui.moveTo(x_run + 30, y_run - 20, duration=random.uniform(0.5, 1.2))
                pyautogui.moveTo(x_run, y_run, duration=random.uniform(0.6, 3.2))
                pyautogui.click()              
                
            

            SEND_CTRL_ENTER = False
            if SEND_CTRL_ENTER:
                # Run button is grayed out for a while - wait until clickable
                WebDriverWait(browser, WAIT_DEF_TIMEOUT).until(
                    EC.element_to_be_clickable(LOCATOR_BTN_RUN_XPATH)
                )
                # 2. Click the textarea to give it focus
                chat_input.click()                
                #browser.execute_script("arguments[0].focus();", chat_input)
                time.sleep(2)  # tiny pause to ensure focus
                                    
                chat_input.send_keys(Keys.CONTROL, Keys.ENTER)    

            CLICK_RUN = False
            if CLICK_RUN:
                time.sleep(2)
                # Run button click with animation can be inserted here if needed
                WebDriverWait(browser, WAIT_DEF_TIMEOUT).until(
                    EC.element_to_be_clickable(LOCATOR_BTN_RUN_XPATH)
                ).click()
                    
                logger.info("Clicked Run button")

            # Wait for JS flag
            max_wait_js_attempts = 5
            model_errors = None
            for wait_js_attempt in range(1, max_wait_js_attempts + 1):
                wait_res = wait_for_js_condition_or_timeout(
                    browser, "return window._generateContentSend != null", WAIT_RESP, poll_interval=WAIT_RESP / max_wait_js_attempts
                )
                logger.info(f"wait_for_js_condition_or_timeout: wait_js_attempt {wait_js_attempt}")
                if wait_res:                
                    break # LLM responded - success: response is on window._generateContentSend
                    
                # Check for model error after waiting
                model_errors = browser.find_elements(By.XPATH, "//*[contains(@class, 'model-error')]")
    
                if model_errors:
                    logger.error("Model error detected. Retrying...")
                    clear_hxr_watcher_globals(browser)
                    if attempt == max_retries:
                        raise Exception("Max retries reached. Aborting.")                        
                    else:
                        break  # break from wait for JS loop - Retry from start of outer loop (browser nav to url ...)
                        
            # If errors - Retry from start of outer loop (browser nav to url ...)
            if model_errors:
                continue    
            # Extract response
            llm_text_resp = browser.execute_script("return window._generateContentSend")
            logger.info(f"window._generateContentSend:\n{llm_text_resp}")
            llm_response = extract_texts_from_xhr_GenerateTitle(llm_text_resp)
            logger.info(f"extract_texts_from_xhr_GenerateTitle: {llm_response}")
            clear_hxr_watcher_globals(browser)
            if llm_response:
                logger.info('++++ success! return with llm_response')
                break
            

    except Exception as e:
        logger.error(f"{e}", exc_info=True)

    finally:
        browser.close()
        browser.quit()
    
    return llm_response  # Success or None (if model error or other exception), return result    


if __name__ == '__main__':
    prompt = 'From image observer perspective: Where is the furthest golden handle of the large pot ?	Output: cell id (e.g a0, k6)'
    upload_file_path = r"E:\Robotics\Robotics VLM\robotic_perception\outputs\img_grid.png" 
    file_type = 'image'
    prompt_llm(prompt, upload_file_path, file_type)
    #prompt_llm(prompt, upload_file_path, file_type)
    #prompt_llm(prompt, upload_file_path, file_type)
    