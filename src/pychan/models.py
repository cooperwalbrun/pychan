import copy
from datetime import datetime
from typing import Any, Optional, Generator


class Thread:
    def __init__(
        self,
        board: str,
        number: int,
        *,
        title: Optional[str] = None,
        is_stickied: bool = False,
        is_closed: bool = False,
        is_archived: bool = False
    ):
        self.board = board
        self.number = number
        self.title = title
        self.is_stickied = is_stickied
        self.is_closed = is_closed
        self.is_archived = is_archived

    def __repr__(self) -> str:
        return f"Thread(https://boards.4channel.org/{self.board}/thread/{self.number})"

    def __str__(self) -> str:
        return repr(self)

    def __hash__(self) -> int:
        return hash((self.board, self.number))

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Thread):
            return self.board == other.board and self.number == other.number
        else:
            return False

    def __iter__(self) -> Generator[Any, None, None]:
        # We implement __iter__ so this class can be serialized as a tuple
        for field in [self.board,
                      self.number,
                      self.title,
                      self.is_stickied,
                      self.is_closed,
                      self.is_archived]:
            yield field

    def __copy__(self):
        return Thread(
            self.board,
            self.number,
            title=self.title,
            is_stickied=self.is_stickied,
            is_closed=self.is_closed,
            is_archived=self.is_archived
        )

    def __deepcopy__(self, memo: dict[Any, Any]):
        return Thread(
            copy.deepcopy(self.board, memo),
            self.number,
            title=copy.deepcopy(self.title, memo),
            is_stickied=self.is_stickied,
            is_closed=self.is_closed,
            is_archived=self.is_archived
        )


class File:
    def __init__(self, url: str, name: str, size: str, dimensions: tuple[int, int]):
        self.url = url
        self.name = name
        self.size = size
        self.dimensions = dimensions

    def __repr__(self) -> str:
        return f"File({self.url})"

    def __str__(self) -> str:
        return repr(self)

    def __hash__(self) -> int:
        return hash(self.url)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, File):
            return self.url == other.url
        else:
            return False

    def __iter__(self) -> Generator[Any, None, None]:
        # We implement __iter__ so this class can be serialized as a tuple
        for field in [self.url, self.name, self.size, self.dimensions]:
            yield field

    def __copy__(self):
        return File(self.url, self.name, self.size, self.dimensions)

    def __deepcopy__(self, memo: dict[Any, Any]):
        return File(
            copy.deepcopy(self.url, memo),
            copy.deepcopy(self.name, memo),
            copy.deepcopy(self.size, memo),
            copy.deepcopy(self.dimensions, memo)
        )


class Poster:
    def __init__(
        self,
        name: str,
        *,
        mod_indicator: bool = False,
        id: Optional[str] = None,
        flag: Optional[str] = None
    ):
        self.name = name
        self._mod_indicator = mod_indicator
        self.id = id
        self.flag = flag

    @property
    def is_moderator(self) -> bool:
        return self._mod_indicator or self.name != "Anonymous"

    def __repr__(self) -> str:
        return "Poster(name={}, is_moderator={}, id={}, flag={})".format(
            self.name, self.is_moderator, self.id, self.flag
        )

    def __str__(self) -> str:
        return repr(self)

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Poster):
            return self.name == other.name and self.id == other.id
        else:
            return False

    def __iter__(self) -> Generator[Any, None, None]:
        # We implement __iter__ so this class can be serialized as a tuple
        for field in [self.name, self._mod_indicator, self.id, self.flag]:
            yield field

    def __copy__(self):
        return Poster(self.name, mod_indicator=self._mod_indicator, id=self.id, flag=self.flag)

    def __deepcopy__(self, memo: dict[Any, Any]):
        return Poster(
            copy.deepcopy(self.name, memo),
            mod_indicator=self._mod_indicator,
            id=copy.deepcopy(self.id, memo),
            flag=copy.deepcopy(self.flag, memo)
        )


class Post:
    def __init__(
        self,
        thread: Thread,
        number: int,
        timestamp: datetime,
        poster: Poster,
        text: str,
        *,
        is_original_post: bool = False,
        file: Optional[File] = None,
        replies: Optional[list] = None
    ):
        self.thread = thread
        self.number = number
        self.timestamp = timestamp
        self.poster = poster
        self.text = text
        self.is_original_post = is_original_post
        self.file = file
        self.replies: list[Post] = replies if replies is not None else []

    def __repr__(self) -> str:
        return "Post(https://boards.4channel.org/{})".format(
            f"{self.thread.board}/thread/{self.thread.number}#p{self.number}"
        )

    def __str__(self) -> str:
        return repr(self)

    def __hash__(self) -> int:
        return hash((self.number, self.thread.number))

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Post):
            return self.number == other.number and self.thread == other.thread
        else:
            return False

    def __iter__(self) -> Generator[Any, None, None]:
        # We implement __iter__ so this class can be serialized as a tuple
        fields = list(self.thread) + [self.number, self.timestamp] + \
                 list(self.poster) + \
                 [
                     self.text,
                     self.is_original_post,
                     None if self.file is None else self.file.url,
                     None if self.file is None else self.file.name,
                     None if self.file is None else self.file.size,
                     None if self.file is None else self.file.dimensions,
                     len(self.replies)
                  ]
        for field in fields:
            yield field

    def __copy__(self):
        return Post(
            self.thread,
            self.number,
            self.timestamp,
            self.poster,
            self.text,
            is_original_post=self.is_original_post,
            file=self.file,
            replies=self.replies
        )

    def __deepcopy__(self, memo: dict[Any, Any]):
        return Post(
            copy.deepcopy(self.thread, memo),
            self.number,
            copy.deepcopy(self.timestamp, memo),
            copy.deepcopy(self.poster, memo),
            copy.deepcopy(self.text, memo),
            is_original_post=self.is_original_post,
            file=copy.deepcopy(self.file, memo),
            replies=copy.deepcopy(self.replies, memo)
        )
