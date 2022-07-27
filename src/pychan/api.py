import random
from typing import Optional, Generator, Any
from uuid import uuid4

import requests
from bs4 import BeautifulSoup
from ratelimit import sleep_and_retry, limits
from requests import Response

from pychan.logger import PychanLogger, LogLevel
from pychan.models import File
from pychan.models import Post, Thread


def _find_first(selectable_entity: Any, selector: str) -> Optional[Any]:
    ret = selectable_entity.select(selector)
    if ret is not None and len(ret) > 0:
        return ret[0]
    else:
        return None


class FourChan:
    _PAGE_MAX = 10  # Only 10 pages exist for any given board

    def __init__(self, logger: Optional[PychanLogger] = None):
        self._agent = str(uuid4())
        self._line_break_placeholder = str(uuid4())
        self._logger = logger if logger is not None else PychanLogger(LogLevel.OFF)

    @sleep_and_retry
    @limits(calls=1, period=0.75)
    def _request_throttle(self) -> None:
        # This is a separate function primarily to allow us to unit test _request_helper() without
        # doing a lot of work to bypass/mock the rate-limiting annotations
        return

    def _request_helper(self, url: str) -> Optional[Response]:
        self._request_throttle()
        response = requests.get(url, headers={"User-Agent": self._agent})
        if response.status_code == 200:
            return response
        elif response.status_code == 404:
            self._logger.warn(f"Received a 404 status from {url}")
            return None
        else:
            self._logger.error(f"Unexpected status code {response.status_code} when fetching {url}")
            return None

    def get_boards(self) -> list[str]:
        board_blacklist = ["f"]

        ret = []
        self._logger.info("Fetching all boards from 4chan...")

        # Below, we use https://boards.4channel.org/search instead of the homepage of 4chan due to
        # CloudFlare (and at the time of this writing, the VeNoMouS/cloudscraper repository on
        # GitHub does not work and seems to have disabled GitHub issues entirely)
        response = self._request_helper("https://boards.4channel.org/search")
        if response is not None:
            soup = BeautifulSoup(response.text, "html.parser")
            board_list = _find_first(soup, ".boardList")
            if board_list is not None:
                for anchor in board_list.select("a"):
                    board = anchor.text
                    if board not in board_blacklist:
                        ret.append(board)

        self._logger.info(f"Fetched {len(ret)} board(s) from 4chan")
        return ret

    def _get_thread_helper(self, board: str,
                           page_number: int) -> Optional[Generator[Thread, None, None]]:
        self._logger.info(f"Fetching threads for page {page_number} of /{board}/...")
        url = f"https://boards.4channel.org/{board}"
        if page_number > 1:
            url += f"/{page_number}"
        response = self._request_helper(url)
        if response is None:
            return None
        else:
            soup = BeautifulSoup(response.text, "html.parser")
            thread_divs = soup.select("div.board > div.thread")
            if len(thread_divs) == 0:
                self._logger.warn(f"Zero threads discovered on page {page_number} of /{board}/")
            for div in thread_divs:
                title = _find_first(div, "span.subject")
                title = title.text if title is not None and len(title.text.strip()) > 0 else None
                thread_number = int(div["id"][1:])
                yield Thread(board, thread_number, title=title)

    def get_all_threads(self) -> Generator[Thread, None, None]:
        boards = self.get_boards()
        page_numbers = {}
        while len(boards) > 0:
            board = random.choice(boards)
            if board not in page_numbers:
                page_numbers[board] = 1
            else:
                page_numbers[board] += 1

            if page_numbers[board] > self._PAGE_MAX:
                boards.remove(board)
                self._logger.info((
                    f"Reached page {page_numbers[board]} of /{board}/, so /{board}/ will no longer "
                    f"be considered when fetching subsequent threads in this instance of the "
                    f"generator. There are now {len(boards)} boards remaining."
                ))
                continue

            for thread in self._get_thread_helper(board, page_numbers[board]):
                yield thread

    def get_threads_for_board(self, board: str) -> Generator[Thread, None, None]:
        sanitized_board = board.replace("/", "")
        page_number = 0
        while page_number < self._PAGE_MAX:
            page_number += 1
            for thread in self._get_thread_helper(sanitized_board, page_number):
                yield thread

    def get_posts(self, thread: Thread) -> list[Post]:
        self._logger.debug(f"Fetching posts for {thread}...")
        response = self._request_helper(
            f"https://boards.4channel.org/{thread.board}/thread/{thread.number}/"
        )
        if response is None:
            return []
        soup = BeautifulSoup(response.text, "html.parser")
        ret = []
        for post in soup.select("div.post"):
            op = "op" in post["class"]
            uid = _find_first(post, "span.posteruid span")
            uid = uid.text if uid is not None and len(uid.text.strip()) > 0 else None
            file = None
            file_soup = _find_first(post, "a.fileThumb")
            if file_soup is not None:
                href = file_soup["href"]
                href = "https:" + href if href.startswith("//") else href
                file_title = file_soup.get("title", "")
                file_title = file_title if len(file_title.strip()) > 0 else None
                file = File(href, file_title)
            message = _find_first(post, "blockquote.postMessage")

            if message is not None:
                # The following approach to preserve HTML line breaks in the final post text is
                # based on this: https://stackoverflow.com/a/61423104
                for line_break in message.select("br"):
                    line_break.replaceWith(self._line_break_placeholder)

                text = message.text.replace(self._line_break_placeholder, "\n").strip()

                if len(text) > 0:
                    ret.append(
                        Post(
                            thread,
                            int(message["id"][1:]),
                            text,
                            is_original_post=op,
                            poster_id=uid,
                            file=file
                        )
                    )
        return ret
