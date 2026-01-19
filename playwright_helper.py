"""
PlaywrightHelper - Custom Playwright helper class with retry system and humanization.
"""

import random
import time
from typing import Optional, List, Dict, Any, Union
from playwright.sync_api import Page, FrameLocator, Locator
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import Error as PlaywrightError


class PlaywrightHelper:
    """
    Custom Playwright helper class with retry system and humanization.
    All methods return True/False for success/failure.
    """

    def __init__(
        self,
        page: Page,
        default_retries: int = 3,
        default_timeout: int = 5000,
        humanize: bool = True,
        humanize_min_delay: float = 0.1,
        humanize_max_delay: float = 0.4
    ):
        self.page = page
        self.default_retries = default_retries
        self.default_timeout = default_timeout
        self.humanize = humanize
        self.humanize_min_delay = humanize_min_delay
        self.humanize_max_delay = humanize_max_delay

    # =========================================================================
    # PRIVATE HELPER METHODS
    # =========================================================================

    def _humanize_delay(
        self,
        min_delay: Optional[float] = None,
        max_delay: Optional[float] = None
    ) -> None:
        """Add a random delay to simulate human behavior."""
        if not self.humanize:
            return

        min_d = min_delay if min_delay is not None else self.humanize_min_delay
        max_d = max_delay if max_delay is not None else self.humanize_max_delay

        delay = random.uniform(min_d, max_d)
        time.sleep(delay)

    def _humanize_typing(self, text: str) -> List[tuple]:
        """Generate human-like typing delays for each character."""
        typing_data = []
        for char in text:
            if char == ' ':
                delay = random.uniform(0.05, 0.15)
            elif char in '.,!?':
                delay = random.uniform(0.1, 0.25)
            else:
                delay = random.uniform(0.03, 0.12)
            typing_data.append((char, delay))
        return typing_data

    def _get_locator(
        self,
        selector: str,
        iframe_selector: Optional[str] = None
    ) -> Union[Locator, None]:
        """Get a locator for the given selector, optionally within an iframe."""
        try:
            if iframe_selector:
                frame_locator: FrameLocator = self.page.frame_locator(iframe_selector)
                return frame_locator.locator(selector)
            else:
                return self.page.locator(selector)
        except Exception:
            return None

    def _move_mouse_humanized(self, locator: Locator) -> bool:
        """Move mouse to element in a human-like way."""
        try:
            box = locator.bounding_box()
            if not box:
                return False

            target_x = box['x'] + random.uniform(box['width'] * 0.2, box['width'] * 0.8)
            target_y = box['y'] + random.uniform(box['height'] * 0.2, box['height'] * 0.8)

            steps = random.randint(3, 7)
            current_x, current_y = 0, 0

            for i in range(1, steps + 1):
                progress = i / steps
                offset_x = random.uniform(-5, 5) if i < steps else 0
                offset_y = random.uniform(-5, 5) if i < steps else 0

                intermediate_x = current_x + (target_x - current_x) * progress + offset_x
                intermediate_y = current_y + (target_y - current_y) * progress + offset_y

                self.page.mouse.move(intermediate_x, intermediate_y)
                time.sleep(random.uniform(0.01, 0.05))

            return True
        except Exception:
            return False

    # =========================================================================
    # PUBLIC METHODS
    # =========================================================================

    def wait_natural_delay(
        self,
        min_delay: float = 0.5,
        max_delay: float = 2.0
    ) -> bool:
        """Wait for a random delay between min and max."""
        try:
            if min_delay > max_delay:
                min_delay, max_delay = max_delay, min_delay
            delay = random.uniform(min_delay, max_delay)
            time.sleep(delay)
            return True
        except Exception:
            return False

    def wait_for_network_idle(self, timeout: Optional[int] = None) -> bool:
        """Wait for network to become idle."""
        try:
            op_timeout = timeout if timeout is not None else self.default_timeout
            self.page.wait_for_load_state("networkidle", timeout=op_timeout)
            return True
        except Exception:
            return False

    def wait_for_load_state(
        self,
        state: str = "domcontentloaded",
        timeout: Optional[int] = None
    ) -> bool:
        """Wait for specific load state."""
        try:
            op_timeout = timeout if timeout is not None else self.default_timeout
            self.page.wait_for_load_state(state, timeout=op_timeout)
            return True
        except Exception:
            return False

    def goto(
        self,
        url: str,
        retries: Optional[int] = None,
        timeout: Optional[int] = None,
        wait_until: str = "domcontentloaded"
    ) -> bool:
        """Navigate to a URL with retry system."""
        max_retries = retries if retries is not None else self.default_retries
        op_timeout = timeout if timeout is not None else self.default_timeout

        for attempt in range(max_retries):
            try:
                self._humanize_delay()

                response = self.page.goto(
                    url,
                    timeout=op_timeout,
                    wait_until=wait_until
                )

                if response is not None:
                    if response.ok or (300 <= response.status < 400):
                        try:
                            self.page.wait_for_load_state("domcontentloaded", timeout=op_timeout)
                            return True
                        except PlaywrightTimeoutError:
                            pass

                if response is None:
                    try:
                        current_url = self.page.url
                        if url in current_url or current_url in url:
                            return True
                    except Exception:
                        pass

            except (PlaywrightTimeoutError, PlaywrightError, Exception):
                pass

            if attempt < max_retries - 1:
                self._humanize_delay(0.5, 1.5)

        return False

    def check_element_exists(
        self,
        selector: str,
        iframe_selector: Optional[str] = None,
        retries: Optional[int] = None,
        timeout: Optional[int] = None,
        state: str = "attached"
    ) -> bool:
        """Check if an element exists using multiple Playwright methods."""
        max_retries = retries if retries is not None else self.default_retries
        op_timeout = timeout if timeout is not None else self.default_timeout
        single_check_timeout = max(op_timeout // 4, 1000)

        for attempt in range(max_retries):
            try:
                self._humanize_delay(0.05, 0.15)

                locator = self._get_locator(selector, iframe_selector)
                if locator is None:
                    continue

                # METHOD 1: count()
                try:
                    count = locator.count()
                    if count > 0:
                        return True
                except Exception:
                    pass

                # METHOD 2: is_visible()
                try:
                    if locator.first.is_visible(timeout=single_check_timeout):
                        return True
                except Exception:
                    pass

                # METHOD 3: is_enabled()
                try:
                    if locator.first.is_enabled(timeout=single_check_timeout):
                        return True
                except Exception:
                    pass

                # METHOD 4: wait_for() with state
                try:
                    locator.first.wait_for(state=state, timeout=single_check_timeout)
                    return True
                except Exception:
                    pass

                # METHOD 5: element_handle()
                try:
                    handle = locator.first.element_handle(timeout=single_check_timeout)
                    if handle is not None:
                        handle.dispose()
                        return True
                except Exception:
                    pass

                # METHOD 6: bounding_box()
                try:
                    box = locator.first.bounding_box(timeout=single_check_timeout)
                    if box is not None:
                        return True
                except Exception:
                    pass

            except Exception:
                pass

            if attempt < max_retries - 1:
                self._humanize_delay(0.3, 0.7)

        return False

    def check_element_visible(
        self,
        selector: str,
        iframe_selector: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> bool:
        """Quick check if element is visible (no retries)."""
        try:
            op_timeout = timeout if timeout is not None else self.default_timeout
            locator = self._get_locator(selector, iframe_selector)
            if locator is None:
                return False
            return locator.first.is_visible(timeout=op_timeout)
        except Exception:
            return False

    def click(
        self,
        selector: str,
        iframe_selector: Optional[str] = None,
        retries: Optional[int] = None,
        timeout: Optional[int] = None,
        force: bool = False,
        double_click: bool = False,
        hover_first: bool = True
    ) -> bool:
        """Click on an element with retry system and humanization."""
        max_retries = retries if retries is not None else self.default_retries
        op_timeout = timeout if timeout is not None else self.default_timeout

        for attempt in range(max_retries):
            try:
                if not self.check_element_exists(selector, iframe_selector, retries=1, timeout=op_timeout):
                    if attempt < max_retries - 1:
                        self._humanize_delay(0.3, 0.7)
                    continue

                locator = self._get_locator(selector, iframe_selector)
                if locator is None:
                    continue

                # Hover first for human-like behavior
                if hover_first and not iframe_selector and self.humanize:
                    try:
                        locator.first.hover(timeout=op_timeout)
                        self._humanize_delay(0.1, 0.3)
                    except Exception:
                        pass

                self._humanize_delay(0.05, 0.15)

                click_options = {"timeout": op_timeout, "force": force}

                if double_click:
                    locator.first.dblclick(**click_options)
                else:
                    try:
                        box = locator.first.bounding_box()
                        if box and self.humanize:
                            pos_x = random.uniform(box['width'] * 0.3, box['width'] * 0.7)
                            pos_y = random.uniform(box['height'] * 0.3, box['height'] * 0.7)
                            click_options["position"] = {"x": pos_x, "y": pos_y}
                    except Exception:
                        pass

                    locator.first.click(**click_options)

                self._humanize_delay(0.1, 0.3)
                return True

            except (PlaywrightTimeoutError, PlaywrightError, Exception):
                pass

            if attempt < max_retries - 1:
                self._humanize_delay(0.5, 1.0)

        # Final attempt with force click
        try:
            locator = self._get_locator(selector, iframe_selector)
            if locator:
                locator.first.click(force=True, timeout=op_timeout)
                return True
        except Exception:
            pass

        return False

    def fill(
        self,
        selector: str,
        value: str,
        iframe_selector: Optional[str] = None,
        retries: Optional[int] = None,
        timeout: Optional[int] = None,
        clear_first: bool = True,
        humanize_typing: bool = True,
        press_tab_after: bool = False
    ) -> bool:
        """Fill a field with retry system and humanization."""
        max_retries = retries if retries is not None else self.default_retries
        op_timeout = timeout if timeout is not None else self.default_timeout

        for attempt in range(max_retries):
            try:
                if not self.check_element_exists(selector, iframe_selector, retries=1, timeout=op_timeout):
                    if attempt < max_retries - 1:
                        self._humanize_delay(0.3, 0.7)
                    continue

                locator = self._get_locator(selector, iframe_selector)
                if locator is None:
                    continue

                # Click on field first
                self._humanize_delay(0.1, 0.2)
                try:
                    locator.first.click(timeout=op_timeout)
                except Exception:
                    pass

                self._humanize_delay(0.1, 0.2)

                # Clear field
                if clear_first:
                    try:
                        locator.first.clear(timeout=op_timeout)
                        self._humanize_delay(0.1, 0.2)
                    except Exception:
                        try:
                            locator.first.fill("", timeout=op_timeout)
                        except Exception:
                            pass

                # Fill the field
                if humanize_typing and self.humanize:
                    typing_data = self._humanize_typing(value)
                    for char, delay in typing_data:
                        try:
                            self.page.keyboard.type(char, delay=int(delay * 1000))
                        except Exception:
                            pass
                        time.sleep(delay)
                else:
                    locator.first.fill(value, timeout=op_timeout)

                # Press tab after if requested
                if press_tab_after:
                    self._humanize_delay(0.1, 0.2)
                    self.page.keyboard.press("Tab")

                self._humanize_delay(0.1, 0.3)
                return True

            except (PlaywrightTimeoutError, PlaywrightError, Exception):
                pass

            if attempt < max_retries - 1:
                self._humanize_delay(0.5, 1.0)

        return False
    
    def clear_field(
        self,
        selector: str,
        iframe_selector: Optional[str] = None,
        retries: Optional[int] = None,
        timeout: Optional[int] = None,
        click_first: bool = True,
        method: str = "auto"
    ) -> bool:
        """
        Clear a field with retry system and humanization.
        
        Args:
            selector: CSS/XPath selector for the field
            iframe_selector: Optional iframe selector if element is inside iframe
            retries: Number of retries (uses default if None)
            timeout: Timeout in milliseconds (uses default if None)
            click_first: Click on the field before clearing
            method: Clear method to use:
                - "auto": Try multiple methods until one works
                - "clear": Use Playwright's clear() method
                - "fill_empty": Use fill("") method
                - "select_all": Use Ctrl+A then Delete
                - "backspace": Use multiple backspace keys
                - "triple_click": Triple-click to select all then Delete
        
        Returns:
            True if clear successful, False otherwise
        
        Example:
            # Auto clear (tries multiple methods)
            helper.clear_field("#email-input")
            
            # Clear using specific method
            helper.clear_field("#search-box", method="select_all")
            
            # Clear field in iframe
            helper.clear_field("#card-number", iframe_selector="iframe#payment")
        """
        max_retries = retries if retries is not None else self.default_retries
        op_timeout = timeout if timeout is not None else self.default_timeout

        for attempt in range(max_retries):
            try:
                # Check if element exists
                if not self.check_element_exists(selector, iframe_selector, retries=1, timeout=op_timeout):
                    if attempt < max_retries - 1:
                        self._humanize_delay(0.3, 0.7)
                    continue

                locator = self._get_locator(selector, iframe_selector)
                if locator is None:
                    continue

                # Click on field first if requested
                if click_first:
                    self._humanize_delay(0.1, 0.2)
                    try:
                        locator.first.click(timeout=op_timeout)
                        self._humanize_delay(0.1, 0.2)
                    except Exception:
                        pass

                cleared = False

                # =================================================================
                # METHOD: AUTO (try multiple methods)
                # =================================================================
                if method == "auto":
                    # Try clear()
                    try:
                        locator.first.clear(timeout=op_timeout)
                        cleared = True
                    except Exception:
                        pass

                    # If not cleared, try fill("")
                    if not cleared:
                        try:
                            locator.first.fill("", timeout=op_timeout)
                            cleared = True
                        except Exception:
                            pass

                    # If not cleared, try Ctrl+A + Delete
                    if not cleared:
                        try:
                            locator.first.click(timeout=op_timeout)
                            self._humanize_delay(0.05, 0.1)
                            self.page.keyboard.press("Control+a")
                            self._humanize_delay(0.05, 0.1)
                            self.page.keyboard.press("Delete")
                            cleared = True
                        except Exception:
                            pass

                    # If not cleared, try triple-click + Delete
                    if not cleared:
                        try:
                            locator.first.click(click_count=3, timeout=op_timeout)
                            self._humanize_delay(0.05, 0.1)
                            self.page.keyboard.press("Delete")
                            cleared = True
                        except Exception:
                            pass

                # =================================================================
                # METHOD: CLEAR
                # =================================================================
                elif method == "clear":
                    try:
                        locator.first.clear(timeout=op_timeout)
                        cleared = True
                    except Exception:
                        pass

                # =================================================================
                # METHOD: FILL EMPTY
                # =================================================================
                elif method == "fill_empty":
                    try:
                        locator.first.fill("", timeout=op_timeout)
                        cleared = True
                    except Exception:
                        pass

                # =================================================================
                # METHOD: SELECT ALL (Ctrl+A + Delete)
                # =================================================================
                elif method == "select_all":
                    try:
                        locator.first.click(timeout=op_timeout)
                        self._humanize_delay(0.05, 0.1)
                        self.page.keyboard.press("Control+a")
                        self._humanize_delay(0.05, 0.1)
                        self.page.keyboard.press("Delete")
                        cleared = True
                    except Exception:
                        pass

                # =================================================================
                # METHOD: BACKSPACE (multiple backspaces)
                # =================================================================
                elif method == "backspace":
                    try:
                        # Get current value length
                        current_value = locator.first.input_value(timeout=op_timeout)
                        if current_value:
                            locator.first.click(timeout=op_timeout)
                            self._humanize_delay(0.05, 0.1)
                            # Move to end of input
                            self.page.keyboard.press("End")
                            self._humanize_delay(0.05, 0.1)
                            # Press backspace for each character
                            for _ in range(len(current_value)):
                                self.page.keyboard.press("Backspace")
                                if self.humanize:
                                    time.sleep(random.uniform(0.02, 0.08))
                        cleared = True
                    except Exception:
                        pass

                # =================================================================
                # METHOD: TRIPLE CLICK (select all via triple-click + Delete)
                # =================================================================
                elif method == "triple_click":
                    try:
                        locator.first.click(click_count=3, timeout=op_timeout)
                        self._humanize_delay(0.05, 0.1)
                        self.page.keyboard.press("Delete")
                        cleared = True
                    except Exception:
                        pass

                # =================================================================
                # UNKNOWN METHOD
                # =================================================================
                else:
                    # Default to auto behavior
                    try:
                        locator.first.clear(timeout=op_timeout)
                        cleared = True
                    except Exception:
                        pass

                if cleared:
                    # Verify field is empty (optional verification)
                    try:
                        current_value = locator.first.input_value(timeout=1000)
                        if current_value == "" or current_value is None:
                            self._humanize_delay(0.1, 0.2)
                            return True
                    except Exception:
                        # If we can't verify, assume success
                        self._humanize_delay(0.1, 0.2)
                        return True

            except (PlaywrightTimeoutError, PlaywrightError, Exception):
                pass

            if attempt < max_retries - 1:
                self._humanize_delay(0.5, 1.0)

        return False

    def type_text(
        self,
        selector: str,
        text: str,
        iframe_selector: Optional[str] = None,
        retries: Optional[int] = None,
        timeout: Optional[int] = None,
        delay_ms: Optional[int] = None
    ) -> bool:
        """Type text into an element using page.type() method."""
        max_retries = retries if retries is not None else self.default_retries
        op_timeout = timeout if timeout is not None else self.default_timeout

        for attempt in range(max_retries):
            try:
                if not self.check_element_exists(selector, iframe_selector, retries=1, timeout=op_timeout):
                    if attempt < max_retries - 1:
                        self._humanize_delay(0.3, 0.7)
                    continue

                type_delay = delay_ms if delay_ms is not None else random.randint(50, 150)

                if iframe_selector:
                    frame = self.page.frame_locator(iframe_selector)
                    frame.locator(selector).first.type(text, delay=type_delay, timeout=op_timeout)
                else:
                    self.page.type(selector, text, delay=type_delay, timeout=op_timeout)

                return True

            except (PlaywrightTimeoutError, PlaywrightError, Exception):
                pass

            if attempt < max_retries - 1:
                self._humanize_delay(0.5, 1.0)

        return False

    def press_key(
        self,
        key: str,
        selector: Optional[str] = None,
        retries: Optional[int] = None,
        timeout: Optional[int] = None
    ) -> bool:
        """Press a keyboard key."""
        max_retries = retries if retries is not None else self.default_retries
        op_timeout = timeout if timeout is not None else self.default_timeout

        for attempt in range(max_retries):
            try:
                self._humanize_delay(0.05, 0.15)

                if selector:
                    self.page.press(selector, key, timeout=op_timeout)
                else:
                    self.page.keyboard.press(key)

                return True

            except (PlaywrightTimeoutError, PlaywrightError, Exception):
                pass

            if attempt < max_retries - 1:
                self._humanize_delay(0.3, 0.7)

        return False

    def hover(
        self,
        selector: str,
        iframe_selector: Optional[str] = None,
        retries: Optional[int] = None,
        timeout: Optional[int] = None
    ) -> bool:
        """Hover over an element."""
        max_retries = retries if retries is not None else self.default_retries
        op_timeout = timeout if timeout is not None else self.default_timeout

        for attempt in range(max_retries):
            try:
                if not self.check_element_exists(selector, iframe_selector, retries=1, timeout=op_timeout):
                    continue

                locator = self._get_locator(selector, iframe_selector)
                if locator is None:
                    continue

                if not iframe_selector and self.humanize:
                    self._move_mouse_humanized(locator.first)

                locator.first.hover(timeout=op_timeout)
                self._humanize_delay(0.2, 0.5)
                return True

            except Exception:
                pass

            if attempt < max_retries - 1:
                self._humanize_delay(0.3, 0.7)

        return False

    def scroll_to_element(
        self,
        selector: str,
        iframe_selector: Optional[str] = None,
        retries: Optional[int] = None,
        timeout: Optional[int] = None
    ) -> bool:
        """Scroll to an element."""
        max_retries = retries if retries is not None else self.default_retries
        op_timeout = timeout if timeout is not None else self.default_timeout

        for attempt in range(max_retries):
            try:
                locator = self._get_locator(selector, iframe_selector)
                if locator is None:
                    continue

                locator.first.scroll_into_view_if_needed(timeout=op_timeout)
                self._humanize_delay(0.2, 0.5)
                return True

            except Exception:
                pass

            if attempt < max_retries - 1:
                self._humanize_delay(0.3, 0.7)

        return False

    def scroll_page(
        self,
        direction: str = "down",
        amount: Optional[int] = None
    ) -> bool:
        """Scroll the page up or down with human-like smooth scrolling."""
        try:
            import random
            import time
            
            if amount is None:
                # Get target position based on direction
                if direction == "down":
                    target = self.page.evaluate("document.body.scrollHeight")
                elif direction == "up":
                    target = 0
                elif direction == "middle":
                    target = self.page.evaluate("document.body.scrollHeight / 2")
                else:
                    return False
                
                current = self.page.evaluate("window.scrollY")
                total_distance = target - current
                
                if total_distance == 0:
                    return True
                
                # Scroll in small increments for human-like behavior
                scroll_direction = 1 if total_distance > 0 else -1
                remaining = abs(total_distance)
                
                while remaining > 0:
                    # Random step size between 50-150 pixels
                    step = min(random.randint(50, 150), remaining)
                    self.page.evaluate(f"window.scrollBy(0, {step * scroll_direction})")
                    remaining -= step
                    # Small random delay between scrolls (20-80ms)
                    time.sleep(random.uniform(0.02, 0.08))
            else:
                # Scroll specific amount in increments
                scroll_direction = 1 if direction == "down" else -1
                remaining = amount
                
                while remaining > 0:
                    step = min(random.randint(50, 150), remaining)
                    self.page.evaluate(f"window.scrollBy(0, {step * scroll_direction})")
                    remaining -= step
                    time.sleep(random.uniform(0.02, 0.08))

            self._humanize_delay(0.2, 0.5)
            return True
        except Exception:
            return False

    def get_element_content(
        self,
        selector: str,
        content_type: str = "text",
        attribute: Optional[str] = None,
        iframe_selector: Optional[str] = None,
        retries: Optional[int] = None,
        timeout: Optional[int] = None
    ) -> Optional[str]:
        """Get content from an element."""
        max_retries = retries if retries is not None else self.default_retries
        op_timeout = timeout if timeout is not None else self.default_timeout

        for attempt in range(max_retries):
            try:
                self._humanize_delay(0.05, 0.15)

                if not self.check_element_exists(selector, iframe_selector, retries=1, timeout=op_timeout):
                    if attempt < max_retries - 1:
                        self._humanize_delay(0.3, 0.7)
                    continue

                locator = self._get_locator(selector, iframe_selector)
                if locator is None:
                    continue

                content: Optional[str] = None

                if content_type == "text":
                    content = locator.first.text_content(timeout=op_timeout)
                elif content_type == "inner_text":
                    content = locator.first.inner_text(timeout=op_timeout)
                elif content_type == "inner_html":
                    content = locator.first.inner_html(timeout=op_timeout)
                elif content_type == "outer_html":
                    content = locator.first.evaluate("el => el.outerHTML")
                elif content_type == "value":
                    content = locator.first.input_value(timeout=op_timeout)
                elif content_type == "attribute" and attribute:
                    content = locator.first.get_attribute(attribute, timeout=op_timeout)
                elif content_type == "all_text":
                    content = locator.first.evaluate("el => el.textContent")
                else:
                    content = locator.first.text_content(timeout=op_timeout)

                return content

            except (PlaywrightTimeoutError, PlaywrightError, Exception):
                pass

            if attempt < max_retries - 1:
                self._humanize_delay(0.3, 0.7)

        return None

    def get_all_elements_content(
        self,
        selector: str,
        content_type: str = "text",
        iframe_selector: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> Optional[List[str]]:
        """Get content from all matching elements."""
        try:
            op_timeout = timeout if timeout is not None else self.default_timeout
            locator = self._get_locator(selector, iframe_selector)

            if locator is None:
                return None

            count = locator.count()
            if count == 0:
                return None

            contents = []
            for i in range(count):
                try:
                    element = locator.nth(i)
                    if content_type == "text":
                        content = element.text_content(timeout=op_timeout)
                    elif content_type == "inner_text":
                        content = element.inner_text(timeout=op_timeout)
                    else:
                        content = element.text_content(timeout=op_timeout)

                    if content is not None:
                        contents.append(content)
                except Exception:
                    pass

            return contents if contents else None

        except Exception:
            return None

    def get_current_url(self) -> Optional[str]:
        """Get current page URL."""
        try:
            return self.page.url
        except Exception:
            return None

    def wait_for_url(
        self,
        url_pattern: str,
        timeout: Optional[int] = None
    ) -> bool:
        """Wait for URL to match pattern."""
        try:
            op_timeout = timeout if timeout is not None else self.default_timeout
            self.page.wait_for_url(url_pattern, timeout=op_timeout)
            return True
        except Exception:
            return False

    def wait_for_url_contains(
        self,
        url_substring: str,
        timeout: Optional[int] = None,
        retries: Optional[int] = None
    ) -> bool:
        """Wait for URL to contain a substring."""
        max_retries = retries if retries is not None else self.default_retries
        op_timeout = timeout if timeout is not None else self.default_timeout

        for attempt in range(max_retries):
            try:
                self.page.wait_for_url(f"**/*{url_substring}*", timeout=op_timeout)
                return True
            except Exception:
                pass

            if attempt < max_retries - 1:
                self._humanize_delay(0.5, 1.0)

        return False

    def execute_actions(self, actions: List[Dict[str, Any]]) -> Union[bool, Dict[str, Any]]:
        """Execute a list of actions sequentially."""
        results_data: Dict[str, Any] = {}
        has_get_content = any(
            action.get('type', '').lower().replace(' ', '_') in ['get_content', 'get_element_content']
            for action in actions
        )

        for action in actions:
            action_type = action.get('type', '').lower().replace(' ', '_')
            result = False

            try:
                # GOTO
                if action_type in ['goto', 'goto_link']:
                    url = action.get('url') or action.get('link')
                    if url:
                        result = self.goto(
                            url=url,
                            retries=action.get('retries'),
                            timeout=action.get('timeout')
                        )

                # WAIT
                elif action_type in ['wait']:
                    min_delay = action.get('min_delay') or action.get('min delay', 0.5)
                    max_delay = action.get('max_delay') or action.get('max delay', 2.0)
                    result = self.wait_natural_delay(float(min_delay), float(max_delay))

                # CLICK
                elif action_type in ['click']:
                    selector = action.get('selector')
                    if selector:
                        result = self.click(
                            selector=selector,
                            iframe_selector=action.get('iframe_selector') or action.get('iframeSelector'),
                            retries=action.get('retries'),
                            timeout=action.get('timeout'),
                            force=action.get('force', False)
                        )

                # FILL
                elif action_type in ['fill', 'fill_field']:
                    selector = action.get('selector')
                    value = action.get('value', '')
                    if selector:
                        result = self.fill(
                            selector=selector,
                            value=str(value),
                            iframe_selector=action.get('iframe_selector') or action.get('iframeSelector'),
                            retries=action.get('retries'),
                            timeout=action.get('timeout'),
                            clear_first=action.get('clear_first', True),
                            humanize_typing=action.get('humanize_typing', True),
                            press_tab_after=action.get('press_tab_after', False)
                        )

                # ================================================================
                # CLEAR FIELD ACTION (NEW)
                # ================================================================
                elif action_type in ['clear', 'clear_field']:
                    selector = action.get('selector')
                    if selector:
                        result = self.clear_field(
                            selector=selector,
                            iframe_selector=action.get('iframe_selector') or action.get('iframeSelector'),
                            retries=action.get('retries'),
                            timeout=action.get('timeout'),
                            click_first=action.get('click_first', True),
                            method=action.get('method', 'auto')
                        )

                # TYPE
                elif action_type in ['type', 'type_text']:
                    selector = action.get('selector')
                    text = action.get('text') or action.get('value', '')
                    if selector:
                        result = self.type_text(
                            selector=selector,
                            text=str(text),
                            iframe_selector=action.get('iframe_selector'),
                            retries=action.get('retries'),
                            timeout=action.get('timeout')
                        )

                # PRESS KEY
                elif action_type in ['press', 'press_key']:
                    key = action.get('key')
                    if key:
                        result = self.press_key(
                            key=key,
                            selector=action.get('selector'),
                            retries=action.get('retries'),
                            timeout=action.get('timeout')
                        )

                # CHECK EXISTS
                elif action_type in ['check_exists', 'check_element_exists']:
                    selector = action.get('selector')
                    if selector:
                        result = self.check_element_exists(
                            selector=selector,
                            iframe_selector=action.get('iframe_selector') or action.get('iframeSelector'),
                            retries=action.get('retries'),
                            timeout=action.get('timeout')
                        )

                # GET CONTENT
                elif action_type in ['get_content', 'get_element_content']:
                    selector = action.get('selector')
                    if selector:
                        content = self.get_element_content(
                            selector=selector,
                            content_type=action.get('content_type', 'text'),
                            attribute=action.get('attribute'),
                            iframe_selector=action.get('iframe_selector') or action.get('iframeSelector'),
                            retries=action.get('retries'),
                            timeout=action.get('timeout')
                        )
                        save_as = action.get('save_as')
                        if save_as:
                            results_data[save_as] = content
                        result = content is not None

                # SCROLL
                elif action_type in ['scroll', 'scroll_page']:
                    result = self.scroll_page(
                        direction=action.get('direction', 'down'),
                        amount=action.get('amount')
                    )

                # SCROLL TO ELEMENT
                elif action_type in ['scroll_to', 'scroll_to_element']:
                    selector = action.get('selector')
                    if selector:
                        result = self.scroll_to_element(
                            selector=selector,
                            iframe_selector=action.get('iframe_selector'),
                            retries=action.get('retries'),
                            timeout=action.get('timeout')
                        )

                # HOVER
                elif action_type in ['hover']:
                    selector = action.get('selector')
                    if selector:
                        result = self.hover(
                            selector=selector,
                            iframe_selector=action.get('iframe_selector'),
                            retries=action.get('retries'),
                            timeout=action.get('timeout')
                        )

                # UNKNOWN
                else:
                    return False if not has_get_content else {'success': False, 'data': results_data}

                if not result:
                    return False if not has_get_content else {'success': False, 'data': results_data}

            except Exception:
                return False if not has_get_content else {'success': False, 'data': results_data}

        if has_get_content:
            return {'success': True, 'data': results_data}
        return True