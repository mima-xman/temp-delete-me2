import random
import time
from typing import Optional, List, Dict, Any, Union
from playwright.sync_api import Page, Frame, FrameLocator, Locator
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
        """
        Initialize the PlaywrightHelper.

        Args:
            page: Playwright Page object
            default_retries: Default number of retries for all operations
            default_timeout: Default timeout in milliseconds
            humanize: Enable/disable humanization delays
            humanize_min_delay: Minimum delay for humanization (seconds)
            humanize_max_delay: Maximum delay for humanization (seconds)
        """
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
        """
        Generate human-like typing delays for each character.
        Returns list of (char, delay) tuples.
        """
        typing_data = []
        for char in text:
            # Variable delay between keystrokes
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
        """
        Get a locator for the given selector, optionally within an iframe.

        Args:
            selector: CSS/XPath selector for the element
            iframe_selector: Optional iframe selector

        Returns:
            Locator object or None if iframe not found
        """
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
            # Get element bounding box
            box = locator.bounding_box()
            if not box:
                return False

            # Calculate random point within element
            target_x = box['x'] + random.uniform(box['width'] * 0.2, box['width'] * 0.8)
            target_y = box['y'] + random.uniform(box['height'] * 0.2, box['height'] * 0.8)

            # Move mouse with slight curve (multiple steps)
            current_pos = self.page.evaluate("() => ({x: 0, y: 0})")
            steps = random.randint(3, 7)

            for i in range(1, steps + 1):
                # Add slight randomness to path
                progress = i / steps
                offset_x = random.uniform(-5, 5) if i < steps else 0
                offset_y = random.uniform(-5, 5) if i < steps else 0

                intermediate_x = current_pos.get('x', 0) + (target_x - current_pos.get('x', 0)) * progress + offset_x
                intermediate_y = current_pos.get('y', 0) + (target_y - current_pos.get('y', 0)) * progress + offset_y

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
        """
        Wait for a random delay between min and max to simulate human behavior.

        Args:
            min_delay: Minimum delay in seconds
            max_delay: Maximum delay in seconds

        Returns:
            True if successful, False otherwise
        """
        try:
            if min_delay > max_delay:
                min_delay, max_delay = max_delay, min_delay

            delay = random.uniform(min_delay, max_delay)
            time.sleep(delay)
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
        """
        Navigate to a URL with retry system.

        Args:
            url: The URL to navigate to
            retries: Number of retries (uses default if None)
            timeout: Timeout in milliseconds (uses default if None)
            wait_until: When to consider navigation succeeded
                       ("load", "domcontentloaded", "networkidle", "commit")

        Returns:
            True if navigation successful, False otherwise
        """
        max_retries = retries if retries is not None else self.default_retries
        op_timeout = timeout if timeout is not None else self.default_timeout

        for attempt in range(max_retries):
            try:
                # Humanize before action
                self._humanize_delay()

                # Attempt navigation
                response = self.page.goto(
                    url,
                    timeout=op_timeout,
                    wait_until=wait_until
                )

                # Check if navigation was successful
                if response is not None:
                    # Check for successful status codes (2xx or 3xx)
                    if response.ok or (300 <= response.status < 400):
                        # Additional check: verify page loaded
                        try:
                            self.page.wait_for_load_state("domcontentloaded", timeout=op_timeout)
                            return True
                        except PlaywrightTimeoutError:
                            pass

                # If response is None but no exception, page might still be valid
                if response is None:
                    try:
                        current_url = self.page.url
                        if url in current_url or current_url in url:
                            return True
                    except Exception:
                        pass

            except PlaywrightTimeoutError:
                pass
            except PlaywrightError:
                pass
            except Exception:
                pass

            # Wait before retry
            if attempt < max_retries - 1:
                self._humanize_delay(0.5, 1.5)

        return False

    def check_element_exists(
        self,
        selector: str,
        iframe_selector: Optional[str] = None,
        retries: Optional[int] = None,
        timeout: Optional[int] = None
    ) -> bool:
        """
        Check if an element exists using multiple Playwright methods.
        Returns True on first successful detection.

        Args:
            selector: CSS/XPath selector for the element
            iframe_selector: Optional iframe selector if element is inside iframe
            retries: Number of retries (uses default if None)
            timeout: Timeout in milliseconds (uses default if None)

        Returns:
            True if element exists, False otherwise
        """
        max_retries = retries if retries is not None else self.default_retries
        op_timeout = timeout if timeout is not None else self.default_timeout
        single_check_timeout = max(op_timeout // 4, 1000)  # Divide timeout among methods

        for attempt in range(max_retries):
            try:
                # Humanize before checking
                self._humanize_delay(0.05, 0.15)

                # Get locator
                locator = self._get_locator(selector, iframe_selector)
                if locator is None:
                    continue

                # ============================================================
                # METHOD 1: Check using count()
                # ============================================================
                try:
                    count = locator.count()
                    if count > 0:
                        return True
                except Exception:
                    pass

                # ============================================================
                # METHOD 2: Check using is_visible()
                # ============================================================
                try:
                    if locator.first.is_visible(timeout=single_check_timeout):
                        return True
                except Exception:
                    pass

                # ============================================================
                # METHOD 3: Check using is_enabled()
                # ============================================================
                try:
                    if locator.first.is_enabled(timeout=single_check_timeout):
                        return True
                except Exception:
                    pass

                # ============================================================
                # METHOD 4: Check using wait_for() with "attached" state
                # ============================================================
                try:
                    locator.first.wait_for(state="attached", timeout=single_check_timeout)
                    return True
                except Exception:
                    pass

                # ============================================================
                # METHOD 5: Check using wait_for() with "visible" state
                # ============================================================
                try:
                    locator.first.wait_for(state="visible", timeout=single_check_timeout)
                    return True
                except Exception:
                    pass

                # ============================================================
                # METHOD 6: Check using element_handle()
                # ============================================================
                try:
                    handle = locator.first.element_handle(timeout=single_check_timeout)
                    if handle is not None:
                        handle.dispose()
                        return True
                except Exception:
                    pass

                # ============================================================
                # METHOD 7: Check using bounding_box()
                # ============================================================
                try:
                    box = locator.first.bounding_box(timeout=single_check_timeout)
                    if box is not None:
                        return True
                except Exception:
                    pass

                # ============================================================
                # METHOD 8: For iframes - try to access frame content
                # ============================================================
                if iframe_selector:
                    try:
                        frame = self.page.frame_locator(iframe_selector)
                        inner_locator = frame.locator(selector)
                        text_content = inner_locator.first.text_content(timeout=single_check_timeout)
                        if text_content is not None:
                            return True
                    except Exception:
                        pass

            except Exception:
                pass

            # Wait before retry
            if attempt < max_retries - 1:
                self._humanize_delay(0.3, 0.7)

        return False

    def click(
        self,
        selector: str,
        iframe_selector: Optional[str] = None,
        retries: Optional[int] = None,
        timeout: Optional[int] = None,
        force: bool = False,
        double_click: bool = False
    ) -> bool:
        """
        Click on an element with retry system and humanization.
        Checks if element exists before clicking.

        Args:
            selector: CSS/XPath selector for the element
            iframe_selector: Optional iframe selector if element is inside iframe
            retries: Number of retries (uses default if None)
            timeout: Timeout in milliseconds (uses default if None)
            force: Force click even if element is not visible
            double_click: Perform double-click instead of single click

        Returns:
            True if click successful, False otherwise
        """
        max_retries = retries if retries is not None else self.default_retries
        op_timeout = timeout if timeout is not None else self.default_timeout

        for attempt in range(max_retries):
            try:
                # First check if element exists
                if not self.check_element_exists(
                    selector,
                    iframe_selector,
                    retries=1,
                    timeout=op_timeout
                ):
                    if attempt < max_retries - 1:
                        self._humanize_delay(0.3, 0.7)
                    continue

                # Get locator
                locator = self._get_locator(selector, iframe_selector)
                if locator is None:
                    continue

                # Humanize: move mouse to element (if not in iframe)
                if not iframe_selector and self.humanize:
                    try:
                        self._move_mouse_humanized(locator.first)
                    except Exception:
                        pass

                # Small delay before click
                self._humanize_delay(0.05, 0.15)

                # Perform click
                click_options = {
                    "timeout": op_timeout,
                    "force": force
                }

                if double_click:
                    locator.first.dblclick(**click_options)
                else:
                    # Add slight position randomization
                    try:
                        box = locator.first.bounding_box()
                        if box and self.humanize:
                            # Click at random position within element
                            pos_x = random.uniform(box['width'] * 0.3, box['width'] * 0.7)
                            pos_y = random.uniform(box['height'] * 0.3, box['height'] * 0.7)
                            click_options["position"] = {"x": pos_x, "y": pos_y}
                    except Exception:
                        pass

                    locator.first.click(**click_options)

                # Small delay after click
                self._humanize_delay(0.1, 0.3)

                return True

            except PlaywrightTimeoutError:
                pass
            except PlaywrightError:
                pass
            except Exception:
                pass

            # Wait before retry
            if attempt < max_retries - 1:
                self._humanize_delay(0.5, 1.0)

        return False

    def fill(
        self,
        selector: str,
        value: str,
        iframe_selector: Optional[str] = None,
        retries: Optional[int] = None,
        timeout: Optional[int] = None,
        clear_first: bool = True,
        humanize_typing: bool = True
    ) -> bool:
        """
        Fill a field with retry system and humanization.
        Checks if element exists before filling.

        Args:
            selector: CSS/XPath selector for the field
            value: Value to fill
            iframe_selector: Optional iframe selector if element is inside iframe
            retries: Number of retries (uses default if None)
            timeout: Timeout in milliseconds (uses default if None)
            clear_first: Clear the field before filling
            humanize_typing: Type character by character with delays

        Returns:
            True if fill successful, False otherwise
        """
        max_retries = retries if retries is not None else self.default_retries
        op_timeout = timeout if timeout is not None else self.default_timeout

        for attempt in range(max_retries):
            try:
                # First check if element exists
                if not self.check_element_exists(
                    selector,
                    iframe_selector,
                    retries=1,
                    timeout=op_timeout
                ):
                    if attempt < max_retries - 1:
                        self._humanize_delay(0.3, 0.7)
                    continue

                # Get locator
                locator = self._get_locator(selector, iframe_selector)
                if locator is None:
                    continue

                # Click on the field first (human-like behavior)
                self._humanize_delay(0.1, 0.2)

                try:
                    locator.first.click(timeout=op_timeout)
                except Exception:
                    pass

                self._humanize_delay(0.1, 0.2)

                # Clear field if requested
                if clear_first:
                    try:
                        locator.first.clear(timeout=op_timeout)
                        self._humanize_delay(0.1, 0.2)
                    except Exception:
                        # Try alternative clear methods
                        try:
                            locator.first.fill("", timeout=op_timeout)
                        except Exception:
                            pass

                # Fill the field
                if humanize_typing and self.humanize:
                    # Type character by character
                    typing_data = self._humanize_typing(value)
                    for char, delay in typing_data:
                        try:
                            locator.first.press_sequentially(
                                char,
                                delay=int(delay * 1000),
                                timeout=op_timeout
                            )
                        except Exception:
                            # Fallback to type
                            try:
                                locator.first.type(char, delay=int(delay * 1000))
                            except Exception:
                                pass
                        time.sleep(delay)
                else:
                    # Fast fill
                    locator.first.fill(value, timeout=op_timeout)

                # Small delay after filling
                self._humanize_delay(0.1, 0.3)

                # Verify the value was entered
                try:
                    input_value = locator.first.input_value(timeout=1000)
                    if input_value == value:
                        return True
                except Exception:
                    # If we can't verify, assume success if no exception was raised
                    return True

                return True

            except PlaywrightTimeoutError:
                pass
            except PlaywrightError:
                pass
            except Exception:
                pass

            # Wait before retry
            if attempt < max_retries - 1:
                self._humanize_delay(0.5, 1.0)

        return False

    def execute_actions(self, actions: List[Dict[str, Any]]) -> Union[bool, Dict[str, Any]]:
        """
        Execute a list of actions sequentially.
        
        Supported action types:
            - 'goto' or 'Goto link': Navigate to a URL
            - 'click' or 'Click': Click on an element
            - 'fill' or 'Fill field': Fill a field
            - 'wait' or 'Wait': Wait for a delay
            - 'check_exists' or 'Check element exists': Check if element exists
            - 'get_content' or 'Get element content': Get element content (stored in results)
        
        Args:
            actions: List of action dictionaries
        
        Returns:
            True if all actions successful, False if any action fails
            If 'get_content' actions are used, returns dict with results
        
        Example:
            actions = [
                {'type': 'goto', 'url': 'https://example.com'},
                {'type': 'get_content', 'selector': 'h1', 'content_type': 'text', 'save_as': 'title'},
                {'type': 'get_content', 'selector': 'a.link', 'content_type': 'attribute', 'attribute': 'href', 'save_as': 'link'},
            ]
            result = helper.execute_actions(actions)
            # result = {'success': True, 'data': {'title': 'Hello World', 'link': 'https://...'}}
        """
        results_data: Dict[str, Any] = {}
        has_get_content = any(
            action.get('type', '').lower().replace(' ', '_') in ['get_content', 'get_element_content']
            for action in actions
        )

        for action in actions:
            action_type = action.get('type', '').lower().replace(' ', '_')
            result = False

            try:
                # =================================================================
                # GOTO ACTION
                # =================================================================
                if action_type in ['goto', 'goto_link']:
                    url = action.get('url') or action.get('link')
                    if url:
                        result = self.goto(
                            url=url,
                            retries=action.get('retries'),
                            timeout=action.get('timeout')
                        )

                # =================================================================
                # WAIT ACTION
                # =================================================================
                elif action_type in ['wait']:
                    min_delay = action.get('min_delay') or action.get('min delay', 0.5)
                    max_delay = action.get('max_delay') or action.get('max delay', 2.0)
                    result = self.wait_natural_delay(
                        min_delay=float(min_delay),
                        max_delay=float(max_delay)
                    )

                # =================================================================
                # CLICK ACTION
                # =================================================================
                elif action_type in ['click']:
                    selector = action.get('selector')
                    if selector:
                        result = self.click(
                            selector=selector,
                            iframe_selector=action.get('iframe_selector') or action.get('iframeSelector'),
                            retries=action.get('retries'),
                            timeout=action.get('timeout'),
                            force=action.get('force', False),
                            double_click=action.get('double_click', False)
                        )

                # =================================================================
                # FILL ACTION
                # =================================================================
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
                            humanize_typing=action.get('humanize_typing', True)
                        )

                # =================================================================
                # CHECK EXISTS ACTION
                # =================================================================
                elif action_type in ['check_exists', 'check_element_exists']:
                    selector = action.get('selector')
                    if selector:
                        result = self.check_element_exists(
                            selector=selector,
                            iframe_selector=action.get('iframe_selector') or action.get('iframeSelector'),
                            retries=action.get('retries'),
                            timeout=action.get('timeout')
                        )

                # =================================================================
                # GET CONTENT ACTION
                # =================================================================
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
                        
                        # Store result if save_as is provided
                        save_as = action.get('save_as')
                        if save_as:
                            results_data[save_as] = content
                        
                        result = content is not None

                # =================================================================
                # UNKNOWN ACTION
                # =================================================================
                else:
                    return False if not has_get_content else {'success': False, 'data': results_data}

                # Check if action failed
                if not result:
                    return False if not has_get_content else {'success': False, 'data': results_data}

            except Exception:
                return False if not has_get_content else {'success': False, 'data': results_data}

        # Return appropriate result
        if has_get_content:
            return {'success': True, 'data': results_data}
        return True

    # =========================================================================
    # ADDITIONAL UTILITY METHODS
    # =========================================================================

    def scroll_to_element(
        self,
        selector: str,
        iframe_selector: Optional[str] = None,
        retries: Optional[int] = None,
        timeout: Optional[int] = None
    ) -> bool:
        """
        Scroll to an element with humanization.

        Args:
            selector: CSS/XPath selector for the element
            iframe_selector: Optional iframe selector
            retries: Number of retries
            timeout: Timeout in milliseconds

        Returns:
            True if successful, False otherwise
        """
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

    def get_text(
        self,
        selector: str,
        iframe_selector: Optional[str] = None,
        retries: Optional[int] = None,
        timeout: Optional[int] = None
    ) -> Optional[str]:
        """
        Get text content of an element.

        Args:
            selector: CSS/XPath selector for the element
            iframe_selector: Optional iframe selector
            retries: Number of retries
            timeout: Timeout in milliseconds

        Returns:
            Text content or None if failed
        """
        max_retries = retries if retries is not None else self.default_retries
        op_timeout = timeout if timeout is not None else self.default_timeout

        for attempt in range(max_retries):
            try:
                if self.check_element_exists(selector, iframe_selector, retries=1, timeout=op_timeout):
                    locator = self._get_locator(selector, iframe_selector)
                    if locator:
                        return locator.first.text_content(timeout=op_timeout)
            except Exception:
                pass

            if attempt < max_retries - 1:
                self._humanize_delay(0.3, 0.7)

        return None

    def select_option(
        self,
        selector: str,
        value: Optional[str] = None,
        label: Optional[str] = None,
        index: Optional[int] = None,
        iframe_selector: Optional[str] = None,
        retries: Optional[int] = None,
        timeout: Optional[int] = None
    ) -> bool:
        """
        Select an option from a dropdown.

        Args:
            selector: CSS/XPath selector for the select element
            value: Option value to select
            label: Option label to select
            index: Option index to select
            iframe_selector: Optional iframe selector
            retries: Number of retries
            timeout: Timeout in milliseconds

        Returns:
            True if successful, False otherwise
        """
        max_retries = retries if retries is not None else self.default_retries
        op_timeout = timeout if timeout is not None else self.default_timeout

        for attempt in range(max_retries):
            try:
                if not self.check_element_exists(selector, iframe_selector, retries=1, timeout=op_timeout):
                    continue

                locator = self._get_locator(selector, iframe_selector)
                if locator is None:
                    continue

                self._humanize_delay(0.1, 0.3)

                if value is not None:
                    locator.first.select_option(value=value, timeout=op_timeout)
                elif label is not None:
                    locator.first.select_option(label=label, timeout=op_timeout)
                elif index is not None:
                    locator.first.select_option(index=index, timeout=op_timeout)
                else:
                    continue

                self._humanize_delay(0.1, 0.3)
                return True

            except Exception:
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
        """
        Hover over an element.

        Args:
            selector: CSS/XPath selector for the element
            iframe_selector: Optional iframe selector
            retries: Number of retries
            timeout: Timeout in milliseconds

        Returns:
            True if successful, False otherwise
        """
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

    def get_element_content(
        self,
        selector: str,
        content_type: str = "text",
        attribute: Optional[str] = None,
        iframe_selector: Optional[str] = None,
        retries: Optional[int] = None,
        timeout: Optional[int] = None
    ) -> Optional[str]:
        """
        Get content from an element with retry system.
        
        Args:
            selector: CSS/XPath selector for the element
            content_type: Type of content to retrieve:
                - "text": Text content (default)
                - "inner_text": Inner text (visible text only)
                - "inner_html": Inner HTML
                - "outer_html": Outer HTML
                - "value": Input value (for form fields)
                - "attribute": Get specific attribute (requires 'attribute' param)
                - "all_text": All text content including hidden
            attribute: Attribute name when content_type is "attribute"
            iframe_selector: Optional iframe selector if element is inside iframe
            retries: Number of retries (uses default if None)
            timeout: Timeout in milliseconds (uses default if None)
        
        Returns:
            Content string if successful, None otherwise
        
        Example:
            # Get text content
            text = helper.get_element_content("#title", content_type="text")
            
            # Get input value
            value = helper.get_element_content("#email", content_type="value")
            
            # Get href attribute
            href = helper.get_element_content("a.link", content_type="attribute", attribute="href")
            
            # Get inner HTML
            html = helper.get_element_content("#container", content_type="inner_html")
            
            # Get content from element inside iframe
            text = helper.get_element_content(
                "#payment-status",
                content_type="text",
                iframe_selector="iframe#payment-frame"
            )
        """
        max_retries = retries if retries is not None else self.default_retries
        op_timeout = timeout if timeout is not None else self.default_timeout

        for attempt in range(max_retries):
            try:
                # Humanize before action
                self._humanize_delay(0.05, 0.15)

                # First check if element exists
                if not self.check_element_exists(
                    selector,
                    iframe_selector,
                    retries=1,
                    timeout=op_timeout
                ):
                    if attempt < max_retries - 1:
                        self._humanize_delay(0.3, 0.7)
                    continue

                # Get locator
                locator = self._get_locator(selector, iframe_selector)
                if locator is None:
                    continue

                content: Optional[str] = None

                # =================================================================
                # TEXT CONTENT
                # =================================================================
                if content_type == "text":
                    content = locator.first.text_content(timeout=op_timeout)

                # =================================================================
                # INNER TEXT (visible text only)
                # =================================================================
                elif content_type == "inner_text":
                    content = locator.first.inner_text(timeout=op_timeout)

                # =================================================================
                # INNER HTML
                # =================================================================
                elif content_type == "inner_html":
                    content = locator.first.inner_html(timeout=op_timeout)

                # =================================================================
                # OUTER HTML
                # =================================================================
                elif content_type == "outer_html":
                    # Playwright doesn't have outer_html directly, use evaluate
                    content = locator.first.evaluate("el => el.outerHTML")

                # =================================================================
                # INPUT VALUE
                # =================================================================
                elif content_type == "value":
                    content = locator.first.input_value(timeout=op_timeout)

                # =================================================================
                # ATTRIBUTE
                # =================================================================
                elif content_type == "attribute":
                    if attribute is None:
                        return None
                    content = locator.first.get_attribute(attribute, timeout=op_timeout)

                # =================================================================
                # ALL TEXT (including hidden elements)
                # =================================================================
                elif content_type == "all_text":
                    content = locator.first.evaluate("el => el.textContent")

                # =================================================================
                # UNKNOWN CONTENT TYPE
                # =================================================================
                else:
                    # Default to text_content
                    content = locator.first.text_content(timeout=op_timeout)

                return content

            except PlaywrightTimeoutError:
                pass
            except PlaywrightError:
                pass
            except Exception:
                pass

            # Wait before retry
            if attempt < max_retries - 1:
                self._humanize_delay(0.3, 0.7)

        return None


    def get_multiple_elements_content(
        self,
        selector: str,
        content_type: str = "text",
        attribute: Optional[str] = None,
        iframe_selector: Optional[str] = None,
        retries: Optional[int] = None,
        timeout: Optional[int] = None
    ) -> Optional[List[str]]:
        """
        Get content from multiple elements matching the selector.
        
        Args:
            selector: CSS/XPath selector for the elements
            content_type: Type of content to retrieve (same as get_element_content)
            attribute: Attribute name when content_type is "attribute"
            iframe_selector: Optional iframe selector if elements are inside iframe
            retries: Number of retries (uses default if None)
            timeout: Timeout in milliseconds (uses default if None)
        
        Returns:
            List of content strings if successful, None otherwise
        
        Example:
            # Get all list item texts
            items = helper.get_multiple_elements_content("ul.menu li", content_type="text")
            
            # Get all link hrefs
            hrefs = helper.get_multiple_elements_content(
                "a.product-link",
                content_type="attribute",
                attribute="href"
            )
        """
        max_retries = retries if retries is not None else self.default_retries
        op_timeout = timeout if timeout is not None else self.default_timeout

        for attempt in range(max_retries):
            try:
                # Humanize before action
                self._humanize_delay(0.05, 0.15)

                # Get locator
                locator = self._get_locator(selector, iframe_selector)
                if locator is None:
                    continue

                # Check if any elements exist
                count = locator.count()
                if count == 0:
                    if attempt < max_retries - 1:
                        self._humanize_delay(0.3, 0.7)
                    continue

                contents: List[str] = []

                for i in range(count):
                    try:
                        element = locator.nth(i)
                        content: Optional[str] = None

                        if content_type == "text":
                            content = element.text_content(timeout=op_timeout)
                        elif content_type == "inner_text":
                            content = element.inner_text(timeout=op_timeout)
                        elif content_type == "inner_html":
                            content = element.inner_html(timeout=op_timeout)
                        elif content_type == "outer_html":
                            content = element.evaluate("el => el.outerHTML")
                        elif content_type == "value":
                            content = element.input_value(timeout=op_timeout)
                        elif content_type == "attribute" and attribute:
                            content = element.get_attribute(attribute, timeout=op_timeout)
                        elif content_type == "all_text":
                            content = element.evaluate("el => el.textContent")
                        else:
                            content = element.text_content(timeout=op_timeout)

                        if content is not None:
                            contents.append(content)

                    except Exception:
                        # Skip this element but continue with others
                        pass

                if contents:
                    return contents

            except PlaywrightTimeoutError:
                pass
            except PlaywrightError:
                pass
            except Exception:
                pass

            # Wait before retry
            if attempt < max_retries - 1:
                self._humanize_delay(0.3, 0.7)

        return None


    def get_element_attributes(
        self,
        selector: str,
        attributes: List[str],
        iframe_selector: Optional[str] = None,
        retries: Optional[int] = None,
        timeout: Optional[int] = None
    ) -> Optional[Dict[str, Optional[str]]]:
        """
        Get multiple attributes from an element at once.
        
        Args:
            selector: CSS/XPath selector for the element
            attributes: List of attribute names to retrieve
            iframe_selector: Optional iframe selector if element is inside iframe
            retries: Number of retries (uses default if None)
            timeout: Timeout in milliseconds (uses default if None)
        
        Returns:
            Dictionary of attribute names to values, None if failed
        
        Example:
            attrs = helper.get_element_attributes(
                "img.product-image",
                attributes=["src", "alt", "data-id", "class"]
            )
            # Returns: {"src": "...", "alt": "...", "data-id": "...", "class": "..."}
        """
        max_retries = retries if retries is not None else self.default_retries
        op_timeout = timeout if timeout is not None else self.default_timeout

        for attempt in range(max_retries):
            try:
                # Humanize before action
                self._humanize_delay(0.05, 0.15)

                # First check if element exists
                if not self.check_element_exists(
                    selector,
                    iframe_selector,
                    retries=1,
                    timeout=op_timeout
                ):
                    if attempt < max_retries - 1:
                        self._humanize_delay(0.3, 0.7)
                    continue

                # Get locator
                locator = self._get_locator(selector, iframe_selector)
                if locator is None:
                    continue

                result: Dict[str, Optional[str]] = {}

                for attr in attributes:
                    try:
                        value = locator.first.get_attribute(attr, timeout=op_timeout)
                        result[attr] = value
                    except Exception:
                        result[attr] = None

                return result

            except PlaywrightTimeoutError:
                pass
            except PlaywrightError:
                pass
            except Exception:
                pass

            # Wait before retry
            if attempt < max_retries - 1:
                self._humanize_delay(0.3, 0.7)

        return None


    def get_element_info(
        self,
        selector: str,
        iframe_selector: Optional[str] = None,
        retries: Optional[int] = None,
        timeout: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive information about an element.
        
        Args:
            selector: CSS/XPath selector for the element
            iframe_selector: Optional iframe selector if element is inside iframe
            retries: Number of retries (uses default if None)
            timeout: Timeout in milliseconds (uses default if None)
        
        Returns:
            Dictionary with element information, None if failed
        
        Example:
            info = helper.get_element_info("#submit-button")
            # Returns:
            # {
            #     "text_content": "Submit",
            #     "inner_text": "Submit",
            #     "inner_html": "Submit",
            #     "outer_html": "<button id='submit-button'>Submit</button>",
            #     "tag_name": "BUTTON",
            #     "is_visible": True,
            #     "is_enabled": True,
            #     "is_editable": False,
            #     "is_checked": None,
            #     "bounding_box": {"x": 100, "y": 200, "width": 80, "height": 30},
            #     "attributes": {"id": "submit-button", "class": "btn btn-primary"}
            # }
        """
        max_retries = retries if retries is not None else self.default_retries
        op_timeout = timeout if timeout is not None else self.default_timeout

        for attempt in range(max_retries):
            try:
                # Humanize before action
                self._humanize_delay(0.05, 0.15)

                # First check if element exists
                if not self.check_element_exists(
                    selector,
                    iframe_selector,
                    retries=1,
                    timeout=op_timeout
                ):
                    if attempt < max_retries - 1:
                        self._humanize_delay(0.3, 0.7)
                    continue

                # Get locator
                locator = self._get_locator(selector, iframe_selector)
                if locator is None:
                    continue

                element = locator.first
                info: Dict[str, Any] = {}

                # Text content
                try:
                    info["text_content"] = element.text_content(timeout=op_timeout)
                except Exception:
                    info["text_content"] = None

                # Inner text
                try:
                    info["inner_text"] = element.inner_text(timeout=op_timeout)
                except Exception:
                    info["inner_text"] = None

                # Inner HTML
                try:
                    info["inner_html"] = element.inner_html(timeout=op_timeout)
                except Exception:
                    info["inner_html"] = None

                # Outer HTML
                try:
                    info["outer_html"] = element.evaluate("el => el.outerHTML")
                except Exception:
                    info["outer_html"] = None

                # Tag name
                try:
                    info["tag_name"] = element.evaluate("el => el.tagName")
                except Exception:
                    info["tag_name"] = None

                # Visibility
                try:
                    info["is_visible"] = element.is_visible(timeout=op_timeout)
                except Exception:
                    info["is_visible"] = None

                # Enabled state
                try:
                    info["is_enabled"] = element.is_enabled(timeout=op_timeout)
                except Exception:
                    info["is_enabled"] = None

                # Editable state
                try:
                    info["is_editable"] = element.is_editable(timeout=op_timeout)
                except Exception:
                    info["is_editable"] = None

                # Checked state (for checkboxes/radios)
                try:
                    info["is_checked"] = element.is_checked(timeout=op_timeout)
                except Exception:
                    info["is_checked"] = None

                # Bounding box
                try:
                    info["bounding_box"] = element.bounding_box(timeout=op_timeout)
                except Exception:
                    info["bounding_box"] = None

                # Input value (for form elements)
                try:
                    info["input_value"] = element.input_value(timeout=op_timeout)
                except Exception:
                    info["input_value"] = None

                # All attributes
                try:
                    info["attributes"] = element.evaluate("""
                        el => {
                            const attrs = {};
                            for (const attr of el.attributes) {
                                attrs[attr.name] = attr.value;
                            }
                            return attrs;
                        }
                    """)
                except Exception:
                    info["attributes"] = None

                return info

            except PlaywrightTimeoutError:
                pass
            except PlaywrightError:
                pass
            except Exception:
                pass

            # Wait before retry
            if attempt < max_retries - 1:
                self._humanize_delay(0.3, 0.7)

        return None