import os
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from nocaptchaai_selenium.solver import Solver

API_KEY: str = "your_api_key"
API_URL: str = "https://pro.nocaptchaai.com/api/solve"  # Specify API URL (pro or not).


def main() -> None:
    os.environ["API_KEY"] = API_KEY
    os.environ["API_URL"] = API_URL

    # - Restrict browser startup parameters
    options = webdriver.ChromeOptions()

    options.add_argument("--disable-logging")
    options.add_argument("--log-level=3")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")

    # - Restrict the language of hCaptcha label
    # - Environment variables are valid only in the current process
    # and do not affect other processes in the operating system
    os.environ["LANGUAGE"] = "en"
    options.add_argument(f"--lang={os.getenv('LANGUAGE')}")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    captcha_solver = Solver()

    while True:
        driver.get("https://nocaptchaai.com/demo/hcaptcha.html")
        captcha_solver.solve(driver)


if __name__ == "__main__":
    main()
