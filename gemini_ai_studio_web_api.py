# -*- coding: utf-8 -*-
"""
Created on Wed Jun 18 16:40:17 2025

@author: dekel
"""
# First time: pip install selenium plyer undetected_chromedriver
# conda activate env_dl (familypc)
# cd /d E:\views\llm_web_api
import os
import json
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pathlib import Path
import time
from plyer import notification
from loguru import logger


# ── Constants ─────────────────────────────────────────────────────────────
WAIT_DEF_TIMEOUT = 120  # seconds
WAIT_RESP = 60

# TODO:Modify to your profile to store one-time manual login before automated runs against login llm web pages
PROFILE_PATH = r"E:\views\llm_web_api\chromedriver_profiles\Profile1"

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
    
def prompt_llm(prompt : str, upload_file_path : str = None, file_type = None):
    """

    Parameters
    ----------
    prompt : prompt text
    upload_file_path: optional path to a file (ex: image, pdf) to attach to prompt    
    file_type: optional string to describe the type of upload_file_path - 'image', 'file', 'video' ...
    -------
    None.

    """
    options =  uc.options.ChromeOptions()

    # Set the language to English
    options.add_argument("--lang=en")
    options.add_argument(f"--user-data-dir={PROFILE_PATH}")
    options.headless = False
    
    # Create a new Chrome driver instance
    browser =  uc.Chrome(options) 
 
 
    try:
        # Check if the file already exists in the Downloads folder, and if so, skip it
                
        # Navigate to the desired website
        browser.get(NEW_CHAT_URL)
        
        # XHR Watcher for GenerateContent xhr requests - that returns LLM respose from internal servers
        inject_xhr_watcher(browser)
        
        # Upload an image 
        if upload_file_path:     
            file_upload_dropdown_button = WebDriverWait(browser, WAIT_DEF_TIMEOUT).until(EC.element_to_be_clickable(LOCATOR_BTN_UPLOAD_FILE))
            file_upload_dropdown_button.click()
            logger.info("Clicked file_upload_dropdown_button")
            if file_type == 'image':               
                image_file_input = WebDriverWait(browser, WAIT_DEF_TIMEOUT).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file'][accept*='image']"))
                )

                image_file_input.send_keys(str(upload_file_path))
                logger.info(f"Uploaded image {upload_file_path}")
            
                
        # Insert prompt text 
        chat_input = WebDriverWait(browser, WAIT_DEF_TIMEOUT).until(EC.element_to_be_clickable(LOCATOR_CHAT_TEXTAREA))
        chat_input.send_keys(prompt)
        
        time.sleep(5)
        
        # Run button Click - to execute prompt
        WebDriverWait(browser, WAIT_DEF_TIMEOUT) \
            .until(EC.element_to_be_clickable(LOCATOR_BTN_RUN_XPATH)) \
            .click()
        
        logger.info("Clicked Run button")
        
        # Poll that JS flag until it turns true
        wait_res = wait_for_js_condition_or_timeout(browser,"return window._generateContentSend != null", WAIT_RESP, poll_interval=WAIT_RESP / 5)
        
        
        if not wait_res and browser.find_elements(By.XPATH,"//*[contains(@class, 'model-error')]"):
            logger.error("Model error. Retry")
                    

        llm_text_resp = browser.execute_script("return window._generateContentSend")
        llm_response = extract_texts_from_xhr_GenerateTitle(llm_text_resp)
        print("XHR response body:", llm_response)
        clear_hxr_watcher_globals(browser)
                
                       
       
    except Exception as e:
        # Log error and continue to the next file
        logger.error("Error while automatic chat {e}")
        
        
    browser.close()
    browser.quit()

if __name__ == '__main__':
    prompt = 'From image observer perspective: Where is the furthest golden handle of the large pot ?	Output: cell id (e.g a0, k6)'
    upload_file_path = r"E:\Robotics\Robotics VLM\robotic_perception\outputs\img_grid.png" 
    file_type = 'image'