import base64
import contextlib
import os
import random
import re
import time
from json import dumps

import requests
from requests.models import Response
from selenium import webdriver
from selenium.common.exceptions import TimeoutException as TE
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait as WDW

# Captcha xpath selectors.
CHECKBOX_CHALLENGE: str = "(//iframe[contains(@title,'checkbox')])[1]"
HOOK_CHALLENGE: str = "(//iframe[contains(@title,'content')])[1]"
PROMPT_TEXT: str = "(//h2[@class='prompt-text'])[1]"
CAPTCHA_CANVAS: str = "(//canvas)[1]"
CAPTCHA_SUBMIT_BUTTON: str = "(//div[@class='button-submit button'])[1]"
CAPTCHA_REFRESH_BUTTON: str = "(//div[@class='refresh button'])[1]"
TASK_IMAGE: str = "//div[@class='task-image']"

NOCAPTCHAAI_ENDPOINTS: dict[str, list[str]] = {
    "free": [
        "https://free.nocaptchaai.com/balance",
        "https://free.nocaptchaai.com/solve",
    ],
    "pro": [
        "https://manage.nocaptchaai.com/balance",
        "https://pro.nocaptchaai.com/solve",
        "https://pro.nocaptchaai.com/status",
    ],
}

GRID_CHALLENGE_PROMPTS: list[str] = [
    "please click each image containing",
    "please click on all images containing",
]

BOUNDING_BOX_CHALLENGE_PROMPTS: list[str] = [
    "please click the center of the",
    "please click on the",
]

MULTIPLE_CHOICE_CHALLENGE_PROMPTS: list[str] = [
    "select the most accurate description of the image",
]


class Solver:
    """
    Initializes the Solver object. Sets the API key and API url.
    If the api_key and api_url are not provided, it will try to get them from the environment variables.

    Args:
        api_key (str | None): The API key for the captcha solver.
        api_url (str | None): The API url for the captcha solver.
    """

    driver: webdriver = None
    user_agent: str

    api_key: str
    api_url: str
    api_endpoints: list[str]

    api_error: bool = False
    balance: int = 0
    requests_left: int = 0

    solved: bool = False
    target: str | None = None
    captcha_type: int | None = None

    captcha_frame = None

    def __init__(self, api_key: str = None, api_url: str = None) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("API_KEY")
        self.api_url = api_url if api_url is not None else os.getenv("API_URL")
        self.api_endpoints = NOCAPTCHAAI_ENDPOINTS[self.api_url]

    def identify_challenge(
        self,
    ) -> None:
        """
        Identifies the type of captcha challenge.
        There are 3 types of captcha challenges:
            - Grid - Select all images of X.
            - Bounding Box - Click in a specific area of X.
            - Multiple Choice - Select the most accurate description of X.
        """
        target: str = self.target.lower().strip()

        # TODO Improve method of checking captcha version.
        # Check if keywords are present in the target.
        if any(keyword in target for keyword in GRID_CHALLENGE_PROMPTS):
            self.captcha_type = 0
        if any(keyword in target for keyword in BOUNDING_BOX_CHALLENGE_PROMPTS):
            self.captcha_type = 1
        if any(keyword in target for keyword in MULTIPLE_CHOICE_CHALLENGE_PROMPTS):
            self.captcha_type = 2

    def is_challenge_image_clickable(
        self,
        wait: int = 2,
    ) -> bool:
        """
        Checks if the challenge image is clickable.

        Returns:
            bool: True if the challenge image is clickable, False otherwise.
        """
        try:
            WDW(self.driver, wait).until(
                EC.element_to_be_clickable((By.XPATH, HOOK_CHALLENGE)),
            )
            return True
        except TE:
            return False

    def is_captcha_visible(
        self,
    ) -> bool:
        """
        Checks if the captcha is visible on the screen.
        Will either check if checkbox from captcha is shown and click it,
        or check if the images are already showing.

        Returns:
            bool: True if the captcha is visible, False otherwise.
        """
        already_visible: bool = bool(self.is_challenge_image_clickable(wait=1))

        if not already_visible:
            # Check if the checkbox is visible.
            with contextlib.suppress(TE):
                WDW(self.driver, 1).until(
                    EC.element_to_be_clickable((By.XPATH, CHECKBOX_CHALLENGE)),
                ).click()

                time.sleep(1)

            # This could mean that simply clicking the checkbox solved the captcha.
            if not self.is_challenge_image_clickable(wait=10):
                return False

        WDW(self.driver, 2).until(
            EC.presence_of_all_elements_located((By.XPATH, HOOK_CHALLENGE)),
        )

        # Switch to the captcha iframe.
        self.captcha_frame = self.driver.find_element(By.XPATH, HOOK_CHALLENGE)

        self.driver.switch_to.frame(self.captcha_frame)

        time.sleep(0.5)

        # Get the target text.
        self.target = self.driver.find_element(By.XPATH, PROMPT_TEXT).text

        # Go back to the main frame.
        self.driver.switch_to.default_content()

        return True

    def solve_hcaptcha_grid(
        self,
    ) -> None:
        """
        Solves the captcha challenge of type Grid (type = 0).
        """
        time.sleep(1)

        if not self.is_challenge_image_clickable(wait=1):
            self.solved = True
            return

        # Switch to the captcha iframe.
        self.captcha_frame = self.driver.find_element(By.XPATH, HOOK_CHALLENGE)

        self.driver.switch_to.frame(self.captcha_frame)

        # Getting the images for the captcha solver.
        images = self.driver.find_elements(By.XPATH, TASK_IMAGE)

        headers: dict[str, str] = {
            "Authority": "hcaptcha.com",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/json",
            "Origin": "https://newassets.hcaptcha.com/",
            "Sec-Fetch-Site": "same-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "User-Agent": self.user_agent,
        }

        image_data: dict[int, str] = {}

        # Populating data for the API call.
        for index, image in enumerate(images):
            image_style: str | None = image.find_element(
                By.CLASS_NAME,
                "image",
            ).get_attribute("style")

            if image_style is None:
                return

            url: str = re.split(r'[(")]', image_style)[2]
            img_base64: bytes = base64.b64encode(
                requests.get(
                    url,
                    headers=headers,
                    timeout=2,
                ).content
            )
            img_base64_decoded: str = img_base64.decode("utf-8")
            image_data[index] = img_base64_decoded

        # Doing final formating for api by adding mandatory fields.
        data_to_send = {
            "target": self.target,
            "method": "hcaptcha_base64",
            "sitekey": "sitekey",
            "site": "site",
            "images": image_data,
        }

        # Post the problem and get the solution.
        r: Response = requests.post(
            url=self.api_endpoints[1],
            headers={
                "Content-Type": "application/json",
                "apikey": self.api_key,
            },
            data=dumps(data_to_send),
            timeout=2,
        )

        # Decrease the requests_left counter.
        self.requests_left -= 1

        if r.json()["status"] == "solved":
            solution = r.json()["solution"]
            correct_images: list[int] = list(map(int, solution))

            for index in correct_images:
                self.driver.execute_script("arguments[0].click();", images[index])
                time.sleep(random.uniform(0.2, 0.25))

            button = self.driver.find_element(By.XPATH, CAPTCHA_SUBMIT_BUTTON)

            label: str | None = button.get_attribute("title")

            time.sleep(0.5)

            button.click()
            self.driver.switch_to.default_content()

            # Checking if there's another step to solve.
            if label == "Next Challenge":
                self.solve_hcaptcha_grid()

        elif r.json()["status"] in ["skip", "error"]:
            self.driver.find_element(By.XPATH, CAPTCHA_REFRESH_BUTTON).click()
            self.driver.switch_to.default_content()

            time.sleep(1)

    def solve_hcaptcha_bbox(
        self,
    ) -> None:
        """
        Solves the captcha challenge of type Bounding Box (type = 1).
        """
        time.sleep(1)

        if not self.is_challenge_image_clickable(wait=1):
            self.solved = True
            return

        # To get the image url, we have to draw a new canvas using the existing one
        # and then use toDataURL() to get the image url in base64.
        get_image_base64 = """
            function sliceOG() {
                const originalCanvas = document.querySelector("canvas");
                if (!originalCanvas) return null;

                const [originalWidth, originalHeight] = [
                    originalCanvas.width,
                    originalCanvas.height,
                ];
                const scaleFactor = Math.min(500 / originalWidth, 536 / originalHeight);
                const [outputWidth, outputHeight] = [
                    originalWidth * scaleFactor,
                    originalHeight * scaleFactor,
                ];

                const outputCanvas = document.createElement("canvas");
                Object.assign(outputCanvas, { width: outputWidth, height: outputHeight });

                const ctx = outputCanvas.getContext("2d");
                ctx.drawImage(
                    originalCanvas,
                    0,
                    0,
                    originalWidth,
                    originalHeight,
                    0,
                    0,
                    outputWidth,
                    outputHeight
                );

                return outputCanvas
                    .toDataURL("image/jpeg", 0.4)
                    .replace(/^data:image\\/(png|jpeg);base64,/, "");
            }

            return sliceOG();
        """

        # Get captcha frame.
        self.captcha_frame = self.driver.find_element(By.XPATH, HOOK_CHALLENGE)

        self.driver.switch_to.frame(self.captcha_frame)

        image_base64: str = self.driver.execute_script(get_image_base64)

        if not image_base64:
            return

        data_to_send = {
            "target": self.target,
            "method": "hcaptcha_base64",
            "sitekey": "sitekey",
            "site": "site",
            "type": "bbox",
            "choices": [],
            "ln": "en",
            "images": {
                0: image_base64,
            },
        }

        # Post the problem.
        post_response: Response = requests.post(
            url=self.api_endpoints[1],
            headers={
                "Content-Type": "application/json",
                "apikey": self.api_key,
            },
            data=dumps(data_to_send),
            timeout=2,
        )

        # Decrease the requests_left counter.
        self.requests_left -= 1

        if post_response.json()["status"] == "error":
            # Click on captcha reload button.
            self.driver.find_element(By.XPATH, CAPTCHA_REFRESH_BUTTON).click()
            self.driver.switch_to.default_content()
            return

        headers: dict[str, str] = {
            "Accept-Language": "last-requested-languages",
            "apikey": self.api_key,
        }

        url: str = post_response.json()["url"]

        # Wait for the solution.
        while True:
            time.sleep(0.2)

            solve_response: Response = requests.get(
                url=url,
                headers=headers,
                timeout=1,
            )

            if solve_response.json()["status"] in ["error", "skip"]:
                self.driver.find_element(By.XPATH, CAPTCHA_REFRESH_BUTTON).click()
                self.driver.switch_to.default_content()

                time.sleep(1)

                return

            if solve_response.json()["status"] == "solved":
                break

        x_pos, y_pos = solve_response.json()["answer"]

        canvas = self.driver.find_element(By.XPATH, CAPTCHA_CANVAS)

        # This always clicks in the center,
        # so we need to move the cursor negative pixels or positive depending
        # on the response from the API.
        move_by_x: int = canvas.size["width"] / 2 - x_pos
        move_by_y: int = canvas.size["height"] / 2 - y_pos

        action = webdriver.common.action_chains.ActionChains(self.driver)
        action.move_to_element(
            canvas,
        ).move_by_offset(
            move_by_x * -1,
            move_by_y * -1,
        ).click().perform()

        time.sleep(0.5)

        button = self.driver.find_element(By.XPATH, CAPTCHA_SUBMIT_BUTTON)

        label: str | None = button.get_attribute("title")

        time.sleep(0.5)

        button.click()
        self.driver.switch_to.default_content()

        # Checking if there's another step to solve.
        if label == "Next Challenge":
            self.solve_hcaptcha_bbox()

    def has_balance(
        self,
    ) -> None:
        """
        Checks if the user has balance or if the daily limit has been hit.

        Returns:
            bool: True if the user has balance, False otherwise.
        """
        response: Response = requests.get(
            self.api_endpoints[0],
            headers={"apikey": self.api_key},
            timeout=2,
        )

        if not response:
            self.api_error = True
            return

        res_json: list = response.json()

        # Check if request was successful.
        if "error" in res_json:
            print(res_json["error"])
            return

        if self.api_url == "pro" and "Subscription" in res_json and "Balance" in res_json:
            self.balance = res_json["Balance"]
            self.requests_left = res_json["Subscription"]["remaining"]
            return

        if self.api_url == "free" and "remaining" in res_json:
            self.balance = 0
            self.requests_left = res_json["remaining"]
            return

        print("Response from the API didn't have necessary keys to check Balance/Remaining Solves.")
        self.api_error = True

    def solve(
        self,
        driver: webdriver,
    ) -> bool:
        """
        Will check if there's any captcha in the page,
        identify the challenge and solve it.

        Args:
            driver (webdriver): The webdriver object.

        Returns:
            bool: True if the captcha was solved, False otherwise.
        """
        # Save the page object.
        self.driver = driver

        self.user_agent = self.driver.execute_script("return navigator.userAgent")

        while not self.solved:
            self.has_balance()

            # Check if user has balance or daily limit hasn't been hit.
            if self.balance <= 0 and self.requests_left <= 0:
                self.api_error = True
                print("No balance/requests left on your nocatpchaAI account.")
                return self.solved

            # If captcha is not visible it means it has been solved.
            if not self.is_captcha_visible():
                break

            # Identify the type of captcha.
            self.identify_challenge()

            match self.captcha_type:
                case 0:
                    self.solve_hcaptcha_grid()
                case 1:
                    self.solve_hcaptcha_bbox()
                case 2:
                    break

            if not self.solved:
                time.sleep(2)

        return self.solved
