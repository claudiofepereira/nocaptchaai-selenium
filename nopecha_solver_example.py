import os

from selenium import webdriver
from selenium.webdriver.chrome.service import Service

from nocaptchaai_selenium.solver import Solver

API_KEY: str = "your_api_key"
API_URL: str = "pro"  # Specify if "free" or "pro".


def main() -> None:
    """
    Example of using the nocaptchaai-selenium package.
    """
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

    driver = webdriver.Chrome(
        service=Service(),
        options=options,
    )

    captcha_solver = Solver()

    while not captcha_solver.solved:
        driver.get("https://nocaptchaai.com/demo/hcaptcha.html")

        captcha_solver.solve(driver)

        if captcha_solver.api_error:
            break

    print("Solved")

    driver.quit()


if __name__ == "__main__":
    main()
